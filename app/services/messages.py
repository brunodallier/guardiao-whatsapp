import json
import time
from dataclasses import asdict

from app.db import rules_from, affiliates_from, prune
from app.moderation.engine import analyze
from app.services.notifications import LocalNotificationSink


def simulate(conn, group_id, participant, content, now=None, source="simulator", notifier=None):
    now = time.time() if now is None else now
    rules = rules_from(conn)
    prune(conn)
    window = max(rules["repeat_window_seconds"], rules["burst_window_seconds"], rules["link_burst_window_seconds"])
    previous = [dict(row) for row in conn.execute("SELECT content, created_at, link_count FROM messages WHERE group_id=? AND participant=? AND created_at BETWEEN ? AND ?", (group_id, participant, now-window, now))]
    result = asdict(analyze(content, rules, affiliates_from(conn), previous, now))
    cursor = conn.execute("INSERT INTO messages(group_id, participant, content, created_at, status, analysis, link_count, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (group_id, participant, content, now, result["status"], json.dumps(result, ensure_ascii=False), len(result["urls"]), source))
    message = {"id": cursor.lastrowid, "group_id": group_id, "participant": participant, "content": content, "created_at": now, "reviewed": False, "source": source, **result}
    if result["status"] != "permitida":
        (notifier or LocalNotificationSink()).emit(message)
    return message
