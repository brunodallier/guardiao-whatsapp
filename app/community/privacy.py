import hashlib
import hmac
import re
import secrets
import unicodedata
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
PHONE = re.compile(r"(?<![\w])\+?\d[\d ()\-.]{6,}\d(?![\w])")
PRIVATE_QUERY = re.compile(r"(?i)([?&](?:token|access_token|auth|password|senha|email|phone|telefone|cpf)=)[^&#\s]+")


def privacy_key(database_path):
    path = Path(database_path).resolve().parent / "privacy.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="ascii") as file:
            file.write(secrets.token_hex(32))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except FileExistsError:
        pass
    value = path.read_text(encoding="ascii").strip()
    if len(value) != 64:
        raise RuntimeError("A chave local de pseudonimização precisa ser verificada.")
    return bytes.fromhex(value)


def digest(key, text):
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()


def author_identity(author):
    value = " ".join(unicodedata.normalize("NFKC", author).casefold().split())
    if re.fullmatch(r"[+\d ().-]+", value) and len(re.sub(r"\D", "", value)) >= 8:
        value = "telefone:" + re.sub(r"\D", "", value)
    return value


def pseudonym(key, author):
    return "Pessoa-" + digest(key, "autor:" + author_identity(author))[:12]


def minimize(text, aliases=None):
    """Reduz PII reconhecível; não equivale a anonimização semântica perfeita."""
    text = PRIVATE_QUERY.sub(lambda m: m[1] + "[oculto]", text)
    text = EMAIL.sub("[e-mail oculto]", text)
    text = CPF.sub("[documento oculto]", text)
    text = PHONE.sub(lambda m: "[telefone oculto]" if 8 <= len(re.sub(r"\D", "", m[0])) <= 15 else m[0], text)
    if aliases:
        # Uma expressão única evita substituições em cascata e custo autores × texto.
        mapping = {name.casefold(): value for name, value in aliases.items() if len(name.strip()) >= 3 and not re.fullmatch(r"[+\d ().-]+", name)}
        if mapping:
            pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in sorted(mapping, key=len, reverse=True)) + r")(?!\w)", re.I)
            text = pattern.sub(lambda m: mapping.get(m[0].casefold(), "[autor oculto]"), text)
    return text
