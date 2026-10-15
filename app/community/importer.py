import json
import threading
import time
import secrets
from collections import Counter, defaultdict, deque
from dataclasses import asdict

from app.community.parser import parse_export, MEDIA
from app.community.privacy import digest, pseudonym, author_identity, minimize
from app.community.storage import policy_from, prune_conversations
from app.community.text import describe, similar_group
from app.db import rules_from, affiliates_from
from app.moderation.engine import analyze


class PreviewStore:
    """Somente mensagens minimizadas em RAM, por dez minutos, vinculadas à sessão."""
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def _prune(self):
        now = time.time()
        self.items = {key: item for key, item in self.items.items() if item["expires"] > now}

    def put(self, owner, value):
        with self.lock:
            self._prune()
            own = [key for key, item in self.items.items() if item["owner"] == owner]
            for key in own[:-1]:
                del self.items[key]
            if len(self.items) >= 5:
                del self.items[next(iter(self.items))]
            token = secrets.token_urlsafe(32)
            self.items[token] = {"owner": owner, "expires": time.time() + 600, "value": value}
            return token

    def get(self, owner, token):
        with self.lock:
            self._prune()
            item = self.items.get(token)
            return item["value"] if item and item["owner"] == owner else None

    def cleanup(self):
        with self.lock:
            self._prune()

    def discard(self, owner, token):
        with self.lock:
            if self.items.get(token, {}).get("owner") == owner:
                del self.items[token]


def build_preview(raw, group_id, key, conn, date_order="dmy", utc_offset=-180, now=None):
    now = time.time() if now is None else now
    parsed = parse_export(raw, date_order, utc_offset)
    policy = policy_from(conn)
    cutoff = now - policy["retention_days"] * 86400
    aliases = {row.author: pseudonym(key, row.author) for row in parsed.records if row.author}
    seen = set()
    existing = {row[0] for row in conn.execute("SELECT fingerprint FROM conversation_messages WHERE group_id=?", (group_id,))}
    counters = Counter(total=len(parsed.records), expired=0, future=0, duplicates=0, errors=parsed.total_errors, ignored_lines=parsed.ignored_lines, system=0, media=0)
    messages = []
    url_rules = {**rules_from(conn), "enabled": {**rules_from(conn)["enabled"], "repeat": False, "burst": False, "link_burst": False}}
    affiliates = affiliates_from(conn)
    for record in parsed.records:
        counters[record.kind] += 1
        if record.timestamp < cutoff:
            counters["expired"] += 1
            continue
        if record.timestamp > now + 300:
            counters["future"] += 1
            continue
        fingerprint = digest(key, json.dumps([group_id, record.timestamp, author_identity(record.author), record.kind, record.content.strip()], ensure_ascii=False))
        if fingerprint in existing or fingerprint in seen:
            counters["duplicates"] += 1
            continue
        seen.add(fingerprint)
        content = "[Mensagem de sistema omitida por privacidade]" if record.kind == "system" else MEDIA.sub("[Mídia omitida]", record.content)
        url_content = MEDIA.sub("", record.content)
        url_result = asdict(analyze(url_content, url_rules, affiliates, [], record.timestamp)) if record.kind != "system" else {"status": "permitida", "findings": [], "urls": []}
        link_count = len(url_result.pop("urls", []))
        url_result.pop("recommendation", None)
        for finding in url_result["findings"]:
            finding["reason"] = minimize(finding["reason"], aliases)
            finding["action"] = "Análise histórica apenas; sem notificações ou punições."
        # O original permanece apenas no escopo do processamento desta requisição.
        messages.append({"fingerprint": fingerprint, "timestamp": record.timestamp,
                         "participant": aliases.get(record.author, "Sistema"),
                         "content": minimize(content, aliases), "kind": record.kind,
                         "url_analysis": json.dumps(url_result, ensure_ascii=False), "link_count": link_count,
                         "repeat_token": digest(key, "repeticao:" + (fingerprint if record.kind == "media" and content.strip() == "[Mídia omitida]" else " ".join(record.content.casefold().split())))})
    messages.sort(key=lambda item: item["timestamp"])
    counters["ready"] = len(messages)
    return {"group_id": group_id, "retention_days": policy["retention_days"],
            "file_fingerprint": digest(key, raw.hex()), "messages": messages,
            "summary": dict(counters), "errors": parsed.errors, "warnings": parsed.warnings,
            "encoding": parsed.encoding, "date_order": date_order, "utc_offset": utc_offset,
            "rules_version": digest(key, json.dumps([rules_from(conn), affiliates], sort_keys=True)),
            "range": {"from": min(row.timestamp for row in parsed.records), "to": max(row.timestamp for row in parsed.records)}}


def reanalyze_group(conn, group_id, now):
    """Reutiliza o motor puro da Etapa 01, sem o serviço que emite notificações."""
    rules = rules_from(conn)
    rules = {**rules, "enabled": {**rules["enabled"], "casino": False, "affiliate": False, "marketplace": False, "unknown_link": False}}
    affiliates = affiliates_from(conn)
    window = max(rules["repeat_window_seconds"], rules["burst_window_seconds"], rules["link_burst_window_seconds"])
    previous = defaultdict(deque)
    free_topics = []
    rows = conn.execute("SELECT * FROM conversation_messages WHERE group_id=? ORDER BY timestamp,id", (group_id,)).fetchall()
    for row in rows:
        if row["kind"] == "system":
            continue
        actor = previous[row["participant"]]
        while actor and actor[0]["created_at"] < row["timestamp"] - window:
            actor.popleft()
        synthetic = row["repeat_token"] + " https://historico.invalid/link" * row["link_count"]
        result = asdict(analyze(synthetic, rules, affiliates, list(actor), row["timestamp"]))
        base = json.loads(row["url_analysis"])
        result["findings"] = base.get("findings", []) + result["findings"]
        result["status"] = "critica" if any(f["severity"] == "critica" for f in result["findings"]) else "suspeita" if result["findings"] else "permitida"
        # Nunca conserva URLs completas nem recomenda punições para dados históricos.
        link_count = row["link_count"]
        result["urls"] = []
        result["recommendation"] = "Registro histórico: revisar o contexto. Nenhum alerta de emergência ou punição."
        for finding in result["findings"]:
            finding["reason"] = minimize(finding["reason"])
            finding["action"] = "Análise histórica apenas; sem notificações ou punições."
        actor.append({"content": synthetic, "created_at": row["timestamp"], "link_count": link_count})
        topic = describe(row["content"], affiliates)
        media_only = row["kind"] == "media" and row["content"].strip() == "[Mídia omitida]"
        candidate = similar_group(topic, free_topics)
        if candidate:
            topic["key"], topic["label"] = candidate["key"], candidate["label"]
        elif topic["label"].endswith("Outros assuntos"):
            free_topics.append(topic)
        # Preserva correções humanas em reimportações e no recálculo temporal.
        topic_key = row["topic_key"] if row["topic_manual"] else None if media_only else topic["key"]
        if not row["topic_manual"] and topic_key:
            conn.execute("INSERT OR IGNORE INTO conversation_topics(key,label) VALUES (?,?)", (topic_key, minimize(topic["label"])))
        conn.execute("UPDATE conversation_messages SET status=?,analysis=?,topic_key=?,question=?,complaint=?,platforms=? WHERE id=?",
                     (result["status"], json.dumps(result, ensure_ascii=False), topic_key, topic["question"], topic["complaint"], json.dumps(topic["platforms"], ensure_ascii=False), row["id"]))


def commit_preview(preview, conn, now=None):
    now = time.time() if now is None else now
    policy = policy_from(conn)
    if policy["retention_days"] != preview["retention_days"]:
        raise ValueError("A retenção mudou. Gere uma nova prévia antes de confirmar.")
    prune_conversations(conn, now)
    cutoff = now - policy["retention_days"] * 86400
    result = {**preview["summary"], "inserted": 0, "duplicates_at_confirmation": 0, "expired_at_confirmation": 0,
              "errors_detail": preview["errors"], "warnings": preview["warnings"], "date_order": preview["date_order"], "utc_offset": preview["utc_offset"]}
    batch_id = conn.execute("INSERT INTO conversation_imports(group_id,created_at,file_fingerprint,result) VALUES (?,?,?,?)", (preview["group_id"], now, preview["file_fingerprint"], "{}")).lastrowid
    for item in preview["messages"]:
        if item["timestamp"] < cutoff:
            result["expired_at_confirmation"] += 1
            continue
        inserted = conn.execute("INSERT OR IGNORE INTO conversation_messages(group_id,import_id,fingerprint,timestamp,participant,content,kind,url_analysis,link_count,repeat_token) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (preview["group_id"], batch_id, item["fingerprint"], item["timestamp"], item["participant"], item["content"], item["kind"], item["url_analysis"], item["link_count"], item["repeat_token"])).rowcount
        result["inserted" if inserted else "duplicates_at_confirmation"] += 1
    reanalyze_group(conn, preview["group_id"], now)
    conn.execute("UPDATE conversation_imports SET result=? WHERE id=?", (json.dumps(result, ensure_ascii=False), batch_id))
    return {"id": batch_id, "group_id": preview["group_id"], **result}
