import html
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Reconhece URLs e domínios em texto. Nunca resolve DNS nem acessa a rede.
URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"']+|(?<![\w@/])(?:[\w-]+\.)+[a-zA-Z]{2,63}(?::\d+)?(?:/[^\s<>\"']*)?(?:\?[^\s<>\"']*)?", re.I)


def normalize_domain(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if not value or any(char in value for char in "/:@?# "):
        raise ValueError("Informe apenas um domínio, sem protocolo ou caminho.")
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Domínio inválido.") from error
    if len(value) > 253 or "." not in value or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in value.split(".")):
        raise ValueError("Domínio inválido.")
    return value


def canonical_url(value: str) -> str:
    value = html.unescape(value.strip())
    if not value.lower().startswith(("http://", "https://")):
        if "://" in value:
            raise ValueError("Use um link HTTP ou HTTPS.")
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Links com credenciais ou sem domínio não são aceitos.")
    host = normalize_domain(parsed.hostname)
    port = parsed.port
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    return urlunsplit(("https", netloc, parsed.path or "/", urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True))), ""))


def extract_urls(content: str) -> list[str]:
    return [match.group().rstrip(".,;:!?)]}") for match in URL_PATTERN.finditer(html.unescape(content))]


def domain_matches(host: str, domains: list[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)
