from dataclasses import dataclass, asdict
from urllib.parse import parse_qs, urlsplit, unquote

from app.moderation.urls import canonical_url, domain_matches, extract_urls


@dataclass
class Finding:
    rule: str
    label: str
    severity: str
    reason: str
    action: str


@dataclass
class Analysis:
    status: str
    findings: list[dict]
    urls: list[str]
    recommendation: str


def analyze(content, rules, affiliates, previous, now):
    """Função pura: previous contém apenas mensagens do mesmo participante/grupo."""
    findings = []
    urls = extract_urls(content)
    enabled = rules["enabled"]

    def add(rule, label, severity, reason, action):
        if enabled[rule] and not any(item.rule == rule for item in findings):
            findings.append(Finding(rule, label, severity, reason, action))

    for raw in urls:
        try:
            url = canonical_url(raw)
        except ValueError:
            add("unknown_link", "Link não verificável", "suspeita", "O endereço não pôde ser interpretado com segurança.", "Revisar o endereço manualmente; não abrir automaticamente.")
            continue
        parsed = urlsplit(url)
        host = parsed.hostname
        if domain_matches(host, rules["casino_domains"]):
            add("casino", "Cassino ou apostas", "critica", f"Domínio {host} consta na lista de apostas configurada.", "SIMULAÇÃO: excluir a mensagem e remover o participante da Comunidade.")
            continue
        if domain_matches(host, rules["shortener_domains"]):
            add("unknown_link", "Link encurtado", "suspeita", f"Destino final de {host} desconhecido; nenhum redirecionamento foi acessado.", "Solicitar o endereço completo e revisar manualmente.")
            continue
        query = {key.lower(): values for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
        profile = next((item for item in sorted(affiliates, key=lambda item: len(item["domain"]), reverse=True) if domain_matches(host, [item["domain"]])), None)
        known = domain_matches(host, rules["allowed_domains"]) or url in [canonical_url(link) for link in rules["allowed_links"]]
        if profile:
            own_url = canonical_url(profile["referral_url"]) if profile["referral_url"] else ""
            own_query = {key.lower(): values for key, values in parse_qs(urlsplit(own_url).query, keep_blank_values=True).items()}
            params = set(rules["affiliate_parameters"] + profile["affiliate_parameters"])
            foreign = False
            for key in params:
                if key in query:
                    expected = own_query.get(key) or ([profile["affiliate_code"]] if profile["affiliate_code"] else [])
                    if not expected or any(value not in expected for value in query[key]) or len(set(query[key])) > 1:
                        foreign = True
            prefix = profile.get("affiliate_path_prefix", "")
            if prefix and unquote(parsed.path).startswith(prefix):
                own_path = unquote(urlsplit(own_url).path) if own_url else prefix + profile["affiliate_code"]
                if unquote(parsed.path).rstrip("/") != own_path.rstrip("/"):
                    foreign = True
            if foreign:
                add("affiliate", "Afiliado de terceiros", "suspeita", f"Identificador de indicação diferente do autorizado para {profile['platform']}.", "SIMULAÇÃO: excluir a mensagem e advertir publicamente o participante após revisão.")
            # O domínio da plataforma pode ser discutido sem link de indicação.
            known = True
        else:
            for item in affiliates:
                if domain_matches(host, item["allowed_domains"]) or url in [canonical_url(link) for link in item["allowed_links"]]:
                    known = True
            if any(key in query for key in rules["affiliate_parameters"]):
                add("affiliate", "Possível link de afiliado", "suspeita", "Parâmetro de indicação em plataforma sem um afiliado próprio cadastrado.", "Revisar o link e confirmar a titularidade antes de advertir.")
        if not known and domain_matches(host, rules["marketplace_domains"]):
            add("marketplace", "Possível propaganda comercial", "suspeita", f"Link para marketplace: {host}. O contexto precisa de revisão.", "SIMULAÇÃO: alertar imediatamente o administrador.")
        elif not known:
            add("unknown_link", "Link desconhecido", "suspeita", f"Domínio {host} ainda não está autorizado.", "Revisar manualmente e autorizar apenas se confirmado.")

    normalized = " ".join(content.casefold().split())
    repeats = sum(1 for item in previous if now - item["created_at"] <= rules["repeat_window_seconds"] and " ".join(item["content"].casefold().split()) == normalized)
    if repeats + 1 >= rules["repeat_threshold"]:
        add("repeat", "Mensagem repetida", "suspeita", f"A mesma mensagem atingiu {rules['repeat_threshold']} envios na janela configurada.", "SIMULAÇÃO: alertar imediatamente o administrador.")
    burst = sum(1 for item in previous if now - item["created_at"] <= rules["burst_window_seconds"])
    if burst + 1 >= rules["burst_threshold"]:
        add("burst", "Muitos envios em sequência", "suspeita", "Participante ultrapassou a frequência configurada neste grupo.", "SIMULAÇÃO: alertar imediatamente o administrador.")
    recent_links = sum(item["link_count"] for item in previous if now - item["created_at"] <= rules["link_burst_window_seconds"])
    if urls and recent_links + len(urls) >= rules["link_burst_threshold"]:
        add("link_burst", "Muitos links em sequência", "suspeita", "Quantidade de links atingiu o limite da janela configurada.", "SIMULAÇÃO: alertar imediatamente o administrador.")
    status = "critica" if any(item.severity == "critica" for item in findings) else "suspeita" if findings else "permitida"
    actions = list(dict.fromkeys(item.action for item in sorted(findings, key=lambda item: item.severity != "critica")))
    return Analysis(status, [asdict(item) for item in findings], urls, " ".join(actions) or "Nenhuma ação. Mensagem permitida pelas regras atuais.")
