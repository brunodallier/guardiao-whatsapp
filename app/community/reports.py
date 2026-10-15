import csv
import io
import json
from datetime import datetime

from app.community.parser import BRASILIA
from app.community.privacy import minimize


def safe_cell(value):
    value = str(value)
    # Evita fórmulas ao abrir CSV em planilhas, inclusive após espaços/controles.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value


def report_records(data):
    """Somente agregados: nunca inclui mensagens, pseudônimos, URLs ou IDs de mensagens."""
    yield {"section": "period", **data["period"], "retention_days": data["retention_days"]}
    yield {"section": "totals", **data["totals"]}
    for section in ("activity", "hours", "weekdays", "platforms", "topics", "questions", "complaints", "spam", "suggestions"):
        for entry in data[section]:
            yield {"section": section, **{key: minimize(value) if isinstance(value, str) else value for key, value in entry.items() if key not in ("key", "group_id")}}
    for limitation in data["limitations"]:
        yield {"section": "limitation", "label": limitation}


def render_report(data, format):
    records = list(report_records(data))
    if format == "jsonl":
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n", "application/x-ndjson"
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["seção", "indicador", "valor", "detalhes"])
        for row in records:
            label = row.get("label", row.get("name", row.get("topic", "")))
            number = row.get("count", row.get("total", ""))
            details = {k: v for k, v in row.items() if k not in ("section", "label", "name", "topic", "count", "total")}
            writer.writerow([safe_cell(row["section"]), safe_cell(label), safe_cell(number), safe_cell(json.dumps(details, ensure_ascii=False))])
        return "\ufeff" + output.getvalue(), "text/csv; charset=utf-8"
    def stamp(value):
        return datetime.fromtimestamp(value, BRASILIA).strftime("%d/%m/%Y %H:%M") if value is not None else "sem dados"
    def md(value):
        return minimize(str(value)).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")
    lines = ["# Guardião IA — Inteligência da comunidade", "", f"Período: {stamp(data['period']['from'])} a {stamp(data['period']['to'])} · UTC−03.",
             f"Dados disponíveis: {stamp(data['period']['available_from'])} a {stamp(data['period']['available_to'])}.",
             f"Retenção configurada: {data['retention_days']} dias. Um período solicitado maior que os dados retidos não recupera mensagens excluídas.", "", "## Indicadores", ""]
    labels = {"messages": "Mensagens no histórico", "analyzed": "Analisadas", "system": "De sistema", "media": "Com mídia omitida", "suspect": "Suspeitas", "critical": "Críticas", "allowed": "Permitidas", "questions": "Dúvidas", "complaints": "Reclamações", "unanswered": "Possivelmente sem resposta"}
    lines += [f"- {label}: {data['totals'][key]}" for key, label in labels.items()]
    for section, title in (("activity", "Atividade por grupo"), ("platforms", "Plataformas"), ("topics", "Assuntos recorrentes"), ("questions", "Principais dúvidas"), ("complaints", "Principais reclamações"), ("spam", "Ocorrências de spam")):
        lines += ["", "## " + title, "", "| Assunto | Quantidade |", "| --- | ---: |"]
        lines += [f"| {md(row.get('label', row.get('name', '')))} | {row.get('count', row.get('total', 0))} |" for row in data[section]] or ["| Sem dados | 0 |"]
    lines += ["", "## Horários e dias de maior atividade", ""]
    lines += [f"- {row['hour']:02d}h: {row['count']} mensagens" for row in sorted(data["hours"], key=lambda row: -row["count"])[:3]]
    lines += [f"- {row['label']}: {row['count']} mensagens" for row in sorted(data["weekdays"], key=lambda row: -row["count"])[:3]]
    lines += ["", "## Sugestões para suporte", ""]
    for item in data["suggestions"]:
        lines += [f"- **{md(item['topic'])}**: {md(item['tutorial'])}. {md(item['pinned_message'])}. {md(item['future_bot_response'])}."]
    lines += ["", "## Limitações", ""] + ["- " + md(item) for item in data["limitations"]]
    return "\n".join(lines) + "\n", "text/markdown; charset=utf-8"
