"""Heurísticas transparentes, executadas localmente; sem modelos ou downloads."""
import hashlib
import re
import unicodedata

PLATFORMS = {"hub": "HUB", "mimix": "Mimix", "crowtado": "Crowtado", "kgen": "Kgen", "flambra": "Flambra"}
TOPICS = [
    ("saque", "Saque", r"\b(saque\w*|sac(?:ar|o|ando|ou)|retir\w*|withdraw\w*)\b"),
    ("bloqueio", "Bloqueio de conta", r"\b(bloque\w*|banid\w*|baniment\w*|suspens\w*)\b"),
    ("cadastro", "Cadastro", r"\b(cadastr\w*|registr\w*|inscri\w*|convite\w*)\b"),
    ("acesso", "Acesso e senha", r"\b(login|logar|senha\w*|acess\w*|entrar)\b"),
    ("tarefas", "Disponibilidade de tarefas", r"\b(tarefa\w*|task\w*|projeto\w*|demanda\w*)\b"),
    ("pagamento", "Pagamentos", r"\b(pagament\w*|pagou|pagar|receb\w*|remuner\w*|ganho\w*)\b"),
    ("suporte", "Atendimento e suporte", r"\b(suporte|atendimento|ticket\w*|contato)\b"),
    ("avaliacao", "Avaliações e aprovação", r"\b(avali\w*|aprov\w*|reprov\w*|qualifica\w*|teste\w*)\b"),
]
STOP = set("a o as os um uma uns umas e de do da dos das em no na nos nas para por com sem que como qual quais quando quanto onde alguem eu voce voces ele ela isso isto meu minha fazer faco faz consigo conseguiu funciona funcionam funcionar pode poderia tem tenho esta estou ser sera nao sim muito bom dia tarde boa dinheiro plataforma pessoal ajuda duvida preciso saber ainda ja aqui ali sobre algum alguma hoje ontem porfavor pessoa telefone oculto mail documento midia".split())
QUESTION = re.compile(r"^(?:como|qual|quais|quando|onde|quanto|por que|porque|alguem|sera que|voces sabem|posso|consigo|tem como|e possivel|duvida|preciso saber)\b")
COMPLAINT = re.compile(r"\b(?:problema\w*|erro\w*|reclam\w*|atras\w*|trav\w*|nao (?:consigo|funciona|recebi|paga|entra|carrega)|sem (?:tarefas|resposta|pagamento)|bloque\w*|banid\w*|sumiu|falh\w*)\b")
ANSWER = re.compile(r"\b(?:basta|clique|acesse|consegui|resolvi|funcionou|passo a passo|voce pode|para (?:sacar|retirar|entrar|acessar)|sim)\b")


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def tokens(text):
    text = re.sub(r"https?://\S+|pessoa-[a-f0-9]+", " ", fold(text))
    words = re.findall(r"[a-z]{3,}", text)
    return {word[:-1] if len(word) > 4 and word.endswith("s") else word for word in words if word not in STOP}


def describe(content, affiliates=()):
    normalized = fold(content)
    known = dict(PLATFORMS)
    for item in affiliates:
        key = fold(item["platform"]).strip()
        if key:
            known[key] = item["platform"]
    platforms = [label for key, label in known.items() if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", normalized)]
    platforms = list(dict.fromkeys(platforms))
    question = "?" in content or bool(QUESTION.search(normalized.strip()))
    complaint = bool(COMPLAINT.search(normalized))
    topic = next(((key, label) for key, label, pattern in TOPICS if re.search(pattern, normalized)), None)
    if topic:
        topic_slug, label = topic
        if platforms:
            label += " na " + " / ".join(platforms)
        signature = topic_slug + ":" + "+".join(sorted(fold(p) for p in platforms))
    else:
        terms = sorted(tokens(content) - set(known))
        # Assinatura de termos, sem reproduzir o texto da pergunta ou nomes livres.
        signature = "termos:" + "|".join(terms[:8])
        label = " / ".join(platforms) + " · Outros assuntos" if platforms else "Outros assuntos"
    key = hashlib.sha256(signature.encode()).hexdigest()[:24]
    return {"key": key, "label": label, "question": question, "complaint": complaint, "platforms": platforms, "tokens": tokens(content)}


def similar_group(description, candidates):
    """Aproxima perguntas livres por Jaccard; tópicos conhecidos usam sinônimos."""
    if not description["label"].endswith("Outros assuntos"):
        return None
    terms = description["tokens"]
    if len(terms) < 2:
        return None
    for candidate in candidates:
        if set(description["platforms"]) != set(candidate["platforms"]):
            continue
        union = terms | candidate["tokens"]
        if len(terms & candidate["tokens"]) / max(len(union), 1) >= 0.65:
            return candidate
    return None
