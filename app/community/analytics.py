import json
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.community.parser import BRASILIA
from app.community.privacy import minimize
from app.community.text import fold, ANSWER, tokens
from app.community.storage import prune_conversations, policy_from

LIMITATIONS = [
    "Agrupamentos usam vocabulário, sinônimos e similaridade de termos locais; revise os resultados.",
    "Pergunta sem resposta é uma hipótese: buscamos resposta do mesmo assunto por outro autor em até seis horas. Não há vínculo de resposta do WhatsApp no TXT.",
    "Autores são pseudonimizados. A minimização automática não reconhece todos os dados pessoais dentro de texto livre.",
    "Mensagens classificadas como suspeitas ou críticas não alimentam a lista de dúvidas e sugestões de suporte.",
]


def time_range(since=None, until=None, days=None, now=None):
    now = time.time() if now is None else now
    end = datetime.combine(until + timedelta(days=1), datetime.min.time(), BRASILIA).timestamp() if until else now + 1
    first_day = since or ((until or datetime.fromtimestamp(now, BRASILIA).date()) - timedelta(days=days-1) if days else None)
    start = datetime.combine(first_day, datetime.min.time(), BRASILIA).timestamp() if first_day else None
    if start is not None and start >= end:
        raise ValueError("O início do período deve ser anterior ou igual ao fim.")
    return start, end


def where_clause(group_id=None, since=None, until=None, days=None, now=None):
    start, end = time_range(since, until, days, now)
    clauses, values = ["m.timestamp<?"], [end]
    if start is not None:
        clauses.append("m.timestamp>=?")
        values.append(start)
    if group_id is not None:
        clauses.append("m.group_id=?")
        values.append(group_id)
    return " AND ".join(clauses), values, start, end


def unanswered_ids(rows):
    pending = set()
    candidates = defaultdict(list)
    stamps = defaultdict(list)
    for row in rows:
        if row["kind"] != "system" and row["status"] == "permitida" and not row["question"] and ANSWER.search(fold(row["content"])):
            key = (row["group_id"], row["topic_key"])
            candidates[key].append(row)
            stamps[key].append((row["timestamp"], row["id"]))
    for question in rows:
        if not question["question"] or question["status"] != "permitida" or question["answer_state"] == "answered":
            continue
        if question["answer_state"] == "unanswered":
            pending.add(question["id"])
            continue
        key = (question["group_id"], question["topic_key"])
        index = bisect_right(stamps[key], (question["timestamp"], question["id"]))
        answered = False
        for reply in candidates[key][index:]:
            if reply["timestamp"] - question["timestamp"] > 6 * 3600:
                break
            if reply["participant"] != question["participant"]:
                answered = True
                break
        if not answered:
            pending.add(question["id"])
    return pending


def intelligence(conn, group_id=None, since=None, until=None, days=7, now=None):
    prune_conversations(conn, now)
    where, values, start, end = where_clause(group_id, since, until, days, now)
    rows = [dict(row) for row in conn.execute("SELECT m.*,g.name AS group_name,t.label AS topic_label,t.reviewed AS topic_reviewed FROM conversation_messages m JOIN groups g ON g.id=m.group_id LEFT JOIN conversation_topics t ON t.key=m.topic_key WHERE " + where + " ORDER BY m.timestamp,m.id", values)]
    pending = unanswered_ids(rows)
    activity, platforms, topics, questions, complaints, spam = {}, Counter(), {}, {}, {}, Counter()
    platform_problems = Counter()
    hours, weekdays, dates = Counter(), Counter(), Counter()
    status_counts = Counter(row["status"] for row in rows if row["kind"] != "system")
    for row in rows:
        group = activity.setdefault(row["group_id"], {"group_id": row["group_id"], "name": minimize(row["group_name"]), "total": 0, "spam": 0})
        group["total"] += 1
        stamp = datetime.fromtimestamp(row["timestamp"], BRASILIA)
        hours[stamp.hour] += 1
        weekdays[stamp.weekday()] += 1
        dates[stamp.date().isoformat()] += 1
        if row["kind"] == "system":
            continue
        for label in json.loads(row["platforms"]):
            platforms[minimize(label)] += 1
            if row["complaint"] and row["status"] == "permitida":
                platform_problems[minimize(label)] += 1
        if row["status"] != "permitida":
            group["spam"] += 1
            for finding in json.loads(row["analysis"]).get("findings", []):
                spam[finding["label"]] += 1
            continue
        if row["topic_key"]:
            topic = topics.setdefault(row["topic_key"], {"key": row["topic_key"], "label": row["topic_label"], "count": 0, "reviewed": bool(row["topic_reviewed"]), "questions": 0, "complaints": 0, "unanswered": 0})
            topic["count"] += 1
            topic["questions"] += bool(row["question"])
            topic["complaints"] += bool(row["complaint"])
            topic["unanswered"] += row["id"] in pending
        if row["question"]:
            entry = questions.setdefault(row["topic_key"], {"key": row["topic_key"], "label": row["topic_label"], "count": 0, "unanswered": 0})
            entry["count"] += 1
            entry["unanswered"] += row["id"] in pending
        if row["complaint"]:
            entry = complaints.setdefault(row["topic_key"], {"key": row["topic_key"], "label": row["topic_label"], "count": 0})
            entry["count"] += 1
    rank = lambda values: sorted(values, key=lambda item: (-item["count"], item.get("label", "")))
    sorted_topics = rank(list(topics.values()))
    suggestions = []
    for topic in sorted(topics.values(), key=lambda item: (-item["unanswered"], -item["questions"], -item["complaints"], -item["count"]))[:8]:
        if topic["questions"] or topic["complaints"]:
            suggestions.append({"topic": topic["label"], "priority": topic["unanswered"] * 3 + topic["questions"] + topic["complaints"],
                                "tutorial": "Criar um passo a passo sobre " + topic["label"],
                                "pinned_message": "Fixar orientações e canais de suporte para " + topic["label"],
                                "future_bot_response": "Preparar uma resposta revisada sobre " + topic["label"]})
    return {
        "period": {"from": start, "to": end, "timezone": "UTC-03:00 (Brasília)", "requested_days": days,
                   "available_from": min((row["timestamp"] for row in rows), default=None), "available_to": max((row["timestamp"] for row in rows), default=None)},
        "retention_days": policy_from(conn)["retention_days"],
        "totals": {"messages": len(rows), "analyzed": sum(row["kind"] != "system" for row in rows),
                   "system": sum(row["kind"] == "system" for row in rows), "media": sum(row["kind"] == "media" for row in rows),
                   "suspect": status_counts["suspeita"], "critical": status_counts["critica"], "allowed": status_counts["permitida"],
                   "questions": sum(item["count"] for item in questions.values()), "complaints": sum(item["count"] for item in complaints.values()), "unanswered": len(pending)},
        "activity": list(activity.values()), "hours": [{"hour": hour, "count": hours[hour]} for hour in range(24)],
        "weekdays": [{"day": day, "label": label, "count": weekdays[day]} for day, label in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"])],
        "dates": [{"date": day, "count": count} for day, count in sorted(dates.items())],
        "platforms": [{"label": label, "count": count, "complaints": platform_problems[label]} for label, count in platforms.most_common()],
        "topics": sorted_topics[:100], "questions": rank(list(questions.values()))[:50], "complaints": rank(list(complaints.values()))[:50],
        "unanswered": [{"id": row["id"], "topic": row["topic_label"], "content": row["content"], "group": minimize(row["group_name"]), "timestamp": row["timestamp"], "manual": row["answer_state"] == "unanswered"} for row in rows if row["id"] in pending][:50],
        "spam": [{"label": label, "count": count} for label, count in spam.most_common()],
        "suggestions": suggestions, "limitations": LIMITATIONS,
    }
