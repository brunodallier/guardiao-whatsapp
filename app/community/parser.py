import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

MAX_BYTES = 10 * 1024 * 1024
MAX_MESSAGES = 25000
MAX_MESSAGE_CHARS = 10000
BRASILIA = timezone(timedelta(hours=-3))
INVISIBLE = str.maketrans("", "", "\ufeff\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
DATE = r"(?P<date>\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4})"
CLOCK = r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?\s*(?P<ampm>[APap]\.?\s*[Mm]\.?)?"
HEADER = re.compile(r"^(?:\[)?" + DATE + r",?\s+" + CLOCK + r"(?:\]\s*|\s+-\s+)(?P<body>.*)$")
HEADER_LIKE = re.compile(r"^\[?\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}.*?(?:\]| - )")
MEDIA = re.compile(r"(?i)(?:<\s*(?:m[ií]dia oculta|media omitted|multimedia omitido|arquivo de m[ií]dia oculto)\s*>|\b(?:imagem|v[ií]deo|[aá]udio|figurinha|documento|image|video|audio|sticker|gif)\s+(?:ocult[oa]|omitid[oa]|omitted)\b|<\s*(?:anexado|attached)\s*:[^>]*>|\S+\.(?:jpg|jpeg|png|opus|mp4|pdf)\s*\((?:arquivo anexado|file attached)\))")
SYSTEM = re.compile(r"(?i)^(?:as mensagens e chamadas|messages and calls|voc[eê] (?:criou|alterou|adicionou|removeu|saiu|mudou)|.+? (?:alterou (?:o nome|a descri[cç][aã]o|a imagem|as configura[cç][oõ]es)|changed (?:the subject|this group.s|the group)|adicionou|removeu|saiu do grupo|left the group|added you))\b")


@dataclass
class Record:
    timestamp: float
    author: str
    content: str
    kind: str
    line: int


@dataclass
class Parsed:
    records: list[Record] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    ignored_lines: int = 0
    total_errors: int = 0
    encoding: str = "utf-8"
    warnings: list[str] = field(default_factory=list)

    def error(self, line, reason):
        self.total_errors += 1
        if len(self.errors) < 100:
            self.errors.append({"line": line, "reason": reason})


def decode_export(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Selecione um TXT não vazio de até 10 MiB.")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    if b"\x00" in raw:
        raise ValueError("O arquivo não parece ser uma exportação TXT compatível.")
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252"), "cp1252"
        except UnicodeDecodeError as error:
            raise ValueError("Codificação não reconhecida. Exporte um TXT em UTF-8.") from error


def parse_export(raw, date_order="dmy", utc_offset=-180):
    text, encoding = decode_export(raw)
    result = Parsed(encoding=encoding)
    if encoding == "cp1252":
        result.warnings.append("Arquivo interpretado como Windows-1252. Confira os acentos na prévia.")
    current = None
    chars = 0
    oversized = False

    def finish():
        if current is None or oversized:
            return
        body = "\n".join(current["parts"]).strip()
        if not body:
            result.ignored_lines += 1
            return
        author, separator, content = body.partition(": ")
        if separator and 0 < len(author.strip()) <= 200 and not SYSTEM.search(author):
            kind = "media" if MEDIA.search(content) else "text"
            result.records.append(Record(current["timestamp"], author.strip(), content, kind, current["line"]))
        else:
            result.records.append(Record(current["timestamp"], "", body, "system", current["line"]))
        if len(result.records) > MAX_MESSAGES:
            raise ValueError("Limite de 25.000 mensagens por arquivo. Divida o TXT em arquivos menores.")

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.translate(INVISIBLE).replace("\u202f", " ").replace("\xa0", " ")
        match = HEADER.match(line)
        if match:
            finish()
            current = None
            oversized = False
            chars = 0
            try:
                parts = [int(part) for part in re.split(r"[/.-]", match["date"])]
                if len(re.split(r"[/.-]", match["date"])[0]) == 4:
                    year, month, day = parts
                elif date_order == "mdy":
                    month, day, year = parts
                else:
                    day, month, year = parts
                if year < 100:
                    year += 2000 if year < 70 else 1900
                hour = int(match["hour"])
                ampm = re.sub(r"[.\s]", "", match["ampm"] or "").lower()
                if ampm:
                    if not 1 <= hour <= 12:
                        raise ValueError()
                    hour = hour % 12 + (12 if ampm == "pm" else 0)
                stamp = datetime(year, month, day, hour, int(match["minute"]), int(match["second"] or 0), tzinfo=timezone(timedelta(minutes=utc_offset))).timestamp()
                current = {"timestamp": stamp, "parts": [match["body"]], "line": line_number}
                chars = len(match["body"])
            except (ValueError, OverflowError, OSError):
                result.error(line_number, "Data ou horário inválido. Confira o formato de datas selecionado.")
        elif HEADER_LIKE.match(line):
            finish()
            current = None
            chars = 0
            oversized = False
            result.error(line_number, "Cabeçalho de mensagem não reconhecido.")
        elif current is not None:
            chars += len(line) + 1
            if not oversized and chars <= MAX_MESSAGE_CHARS:
                current["parts"].append(line)
        elif line.strip():
            result.ignored_lines += 1
        if chars > MAX_MESSAGE_CHARS and not oversized:
            oversized = True
            result.error(current["line"], "Mensagem maior que 10.000 caracteres ignorada.")
    finish()
    if not result.records:
        raise ValueError("Nenhuma mensagem válida. Confira se o TXT é uma exportação do WhatsApp e revise o formato das datas.")
    return result
