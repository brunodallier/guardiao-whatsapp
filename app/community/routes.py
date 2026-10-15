import hashlib
import json
import logging
import time
import asyncio
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator

from app.community.analytics import intelligence, where_clause
from app.community.importer import PreviewStore, build_preview, commit_preview
from app.community.parser import MAX_BYTES
from app.community.privacy import privacy_key, digest, minimize
from app.community.reports import render_report
from app.community.storage import policy_from, prune_conversations, clean_topics
from app.community.text import describe
from app.db import connect, rules_from, affiliates_from


class PolicyInput(BaseModel):
    retention_days: int = Field(ge=1, le=365)
    confirm_deletion: bool = False


class Confirmation(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    confirmed: bool


class DeleteInput(BaseModel):
    confirmation: str
    group_id: int | None = Field(default=None, gt=0)
    since: date | None = None
    until: date | None = None


class Correction(BaseModel):
    topic_key: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_-]+$")
    new_topic_label: str | None = Field(default=None, min_length=3, max_length=100)
    reset_topic: bool = False
    answer_state: Literal["auto", "answered", "unanswered"] | None = None

    @model_validator(mode="after")
    def one_topic_action(self):
        if sum([self.topic_key is not None, self.new_topic_label is not None, self.reset_topic]) > 1:
            raise ValueError("Selecione apenas uma forma de corrigir o assunto.")
        return self


class TopicInput(BaseModel):
    label: str = Field(min_length=3, max_length=100)
    reviewed: bool = True


class MergeTopics(BaseModel):
    source: str = Field(max_length=64)
    target: str = Field(max_length=64)


class PrivateAccessFilter(logging.Filter):
    def filter(self, record):
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and args[2].startswith(("/api/conversations", "/api/intelligence")):
            path = args[2].split("?", 1)[0]
            if path.startswith("/api/conversations/preview/"):
                path = "/api/conversations/preview/[oculto]"
            record.args = (*args[:2], path, *args[3:])
        return True


def register_community_routes(app, settings, admin):
    router = APIRouter(prefix="/api", dependencies=[Depends(admin)])
    previews = PreviewStore()
    app.state.conversation_previews = previews
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, PrivateAccessFilter) for item in logger.filters):
        logger.addFilter(PrivateAccessFilter())

    def owner(request):
        # Revoga acesso à prévia depois do logout, mesmo para o mesmo administrador.
        return str(request.session.get("user_id")) + ":" + request.session.get("csrf", "")

    def require_group(conn, group_id):
        if not conn.execute("SELECT 1 FROM groups WHERE id=?", (group_id,)).fetchone():
            raise HTTPException(404, "Grupo não encontrado.")

    def query_where(group_id=None, since=None, until=None, days=None):
        try:
            return where_clause(group_id, since, until, days)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/conversations/policy")
    def get_policy():
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            return policy_from(conn)

    @router.put("/conversations/policy")
    def set_policy(payload: PolicyInput):
        with connect(settings.database_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = policy_from(conn)
            if payload.retention_days < current["retention_days"] and not payload.confirm_deletion:
                raise HTTPException(409, "Reduzir a retenção pode excluir conversas vencidas. Confirme explicitamente a exclusão.")
            conn.execute("UPDATE settings SET value=? WHERE key='conversation_policy'", (json.dumps({"retention_days": payload.retention_days}),))
            deleted = prune_conversations(conn)
        return {"retention_days": payload.retention_days, "deleted": deleted}

    @router.post("/conversations/preview")
    async def preview(request: Request, group_id: int = Query(gt=0), date_order: Literal["dmy", "mdy"] = "dmy", utc_offset: int = Query(default=-180, ge=-720, le=840)):
        with connect(settings.database_path) as conn:
            require_group(conn, group_id)
        # Leitura limitada em memória. Não usa spool de UploadFile nem salva originais.
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "Arquivo maior que 10 MiB. Divida a exportação.")
            raw.extend(chunk)
        try:
            def process():
                key = privacy_key(settings.database_path)
                with connect(settings.database_path) as conn:
                    prune_conversations(conn)
                    return build_preview(bytes(raw), group_id, key, conn, date_order, utc_offset)
            data = await asyncio.to_thread(process)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            raw.clear()
        token = previews.put(owner(request), data)
        samples = [{key: item[key] for key in ("timestamp", "participant", "content", "kind")} for item in data["messages"][:20]]
        return {"token": token, "expires_in": 600, "summary": data["summary"], "samples": samples,
                "retention_days": data["retention_days"], "errors": data["errors"], "warnings": data["warnings"], "encoding": data["encoding"], "range": data["range"],
                "notice": "Prévia minimizada. O TXT original não foi salvo. Nenhuma conversa é persistida antes de confirmar."}

    @router.post("/conversations/import", status_code=201)
    def confirm_import(payload: Confirmation, request: Request):
        if not payload.confirmed:
            raise HTTPException(422, "Revise a prévia e confirme a importação.")
        data = previews.get(owner(request), payload.token)
        if data is None:
            raise HTTPException(404, "Prévia expirada ou indisponível. Selecione o TXT novamente.")
        try:
            with connect(settings.database_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                require_group(conn, data["group_id"])
                key = privacy_key(settings.database_path)
                version = digest(key, json.dumps([rules_from(conn), affiliates_from(conn)], sort_keys=True))
                if version != data["rules_version"]:
                    raise HTTPException(409, "As regras ou os afiliados mudaram. Gere uma nova prévia.")
                result = commit_preview(data, conn)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        previews.discard(owner(request), payload.token)
        return result

    @router.delete("/conversations/preview/{token}")
    def discard_preview(token: str, request: Request):
        previews.discard(owner(request), token)
        return {"ok": True}

    @router.get("/conversations/imports")
    def import_history(group_id: int | None = None):
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            where, values = (" WHERE i.group_id=?", (group_id,)) if group_id is not None else ("", ())
            return [{"id": row["id"], "group_id": row["group_id"], "group_name": row["name"], "created_at": row["created_at"], "result": json.loads(row["result"])} for row in conn.execute("SELECT i.*,g.name FROM conversation_imports i JOIN groups g ON g.id=i.group_id" + where + " ORDER BY i.created_at DESC,i.id DESC LIMIT 50", values)]

    @router.get("/conversations/messages")
    def messages(group_id: int | None = None, since: date | None = None, until: date | None = None,
                 q: str = Query(default="", max_length=200), kind: Literal["text", "media", "system"] | None = None,
                 status: Literal["permitida", "suspeita", "critica"] | None = None, topic_key: str | None = Query(default=None, max_length=64),
                 page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
        where, values, _, _ = query_where(group_id, since, until)
        if q:
            where += " AND instr(search_fold(m.content),search_fold(?))>0"
            values.append(q)
        for field, value in (("kind", kind), ("status", status), ("topic_key", topic_key)):
            if value is not None:
                where += f" AND m.{field}=?"
                values.append(value)
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            total = conn.execute("SELECT COUNT(*) FROM conversation_messages m WHERE " + where, values).fetchone()[0]
            rows = conn.execute("SELECT m.id,m.group_id,g.name AS group_name,m.timestamp,m.participant,m.content,m.kind,m.status,m.analysis,m.topic_key,t.label AS topic_label,m.question,m.complaint,m.answer_state,m.topic_manual FROM conversation_messages m JOIN groups g ON g.id=m.group_id LEFT JOIN conversation_topics t ON t.key=m.topic_key WHERE " + where + " ORDER BY m.timestamp DESC,m.id DESC LIMIT ? OFFSET ?", (*values, page_size, (page-1)*page_size))
            items = []
            for row in rows:
                item = dict(row)
                item["analysis"] = json.loads(item["analysis"])
                items.append(item)
            return {"items": items, "total": total, "page": page, "page_size": page_size}

    @router.get("/conversations/messages/{message_id}")
    def message_detail(message_id: int):
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            row = conn.execute("SELECT m.id,m.group_id,g.name AS group_name,m.timestamp,m.participant,m.content,m.kind,m.status,m.analysis,m.topic_key,t.label AS topic_label,m.question,m.complaint,m.answer_state,m.topic_manual FROM conversation_messages m JOIN groups g ON g.id=m.group_id LEFT JOIN conversation_topics t ON t.key=m.topic_key WHERE m.id=?", (message_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Registro não encontrado ou expirado.")
            item = dict(row)
            item["analysis"] = json.loads(item["analysis"])
            return item

    @router.delete("/conversations/messages/{message_id}")
    def delete_message(message_id: int, payload: DeleteInput):
        if payload.confirmation != "EXCLUIR":
            raise HTTPException(422, "Digite EXCLUIR para confirmar.")
        with connect(settings.database_path) as conn:
            if not conn.execute("DELETE FROM conversation_messages WHERE id=?", (message_id,)).rowcount:
                raise HTTPException(404, "Registro não encontrado.")
            clean_topics(conn)
        return {"deleted": 1}

    @router.delete("/conversations/messages")
    def delete_period(payload: DeleteInput):
        if payload.confirmation != "EXCLUIR":
            raise HTTPException(422, "Digite EXCLUIR para confirmar.")
        where, values, _, _ = query_where(payload.group_id, payload.since, payload.until)
        with connect(settings.database_path) as conn:
            ids = [row[0] for row in conn.execute("SELECT m.id FROM conversation_messages m WHERE " + where, values)]
            conn.execute("DELETE FROM conversation_messages WHERE id IN (SELECT m.id FROM conversation_messages m WHERE " + where + ")", values)
            # Logs agregados são mantidos na exclusão por período. Na exclusão completa,
            # também são removidos para permitir uma limpeza integral do módulo.
            if payload.since is None and payload.until is None:
                if payload.group_id is None:
                    conn.execute("DELETE FROM conversation_imports")
                else:
                    conn.execute("DELETE FROM conversation_imports WHERE group_id=?", (payload.group_id,))
            clean_topics(conn)
        return {"deleted": len(ids)}

    @router.get("/conversations/topics")
    def topics():
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            return [dict(row) for row in conn.execute("SELECT t.*,COUNT(m.id) AS count FROM conversation_topics t JOIN conversation_messages m ON m.topic_key=t.key GROUP BY t.key ORDER BY count DESC,t.label")]

    @router.put("/conversations/topics/{topic_key}")
    def rename_topic(topic_key: str, payload: TopicInput):
        label = minimize(payload.label.strip())
        if len(label) < 3:
            raise HTTPException(422, "Informe um nome de assunto com ao menos três caracteres.")
        with connect(settings.database_path) as conn:
            prune_conversations(conn)
            if not conn.execute("UPDATE conversation_topics SET label=?,reviewed=? WHERE key=?", (label, payload.reviewed, topic_key)).rowcount:
                raise HTTPException(404, "Agrupamento não encontrado.")
        return {"ok": True}

    @router.post("/conversations/topics/merge")
    def merge_topics(payload: MergeTopics):
        if payload.source == payload.target:
            raise HTTPException(422, "Escolha dois agrupamentos diferentes.")
        with connect(settings.database_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            prune_conversations(conn)
            if conn.execute("SELECT COUNT(*) FROM conversation_topics WHERE key IN (?,?)", (payload.source, payload.target)).fetchone()[0] != 2:
                raise HTTPException(404, "Agrupamento não encontrado.")
            changed = conn.execute("UPDATE conversation_messages SET topic_key=?,topic_manual=1 WHERE topic_key=?", (payload.target, payload.source)).rowcount
            conn.execute("UPDATE conversation_topics SET reviewed=1 WHERE key=?", (payload.target,))
            clean_topics(conn)
        return {"updated": changed}

    @router.put("/conversations/messages/{message_id}/correction")
    def correct_message(message_id: int, payload: Correction):
        with connect(settings.database_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            prune_conversations(conn)
            row = conn.execute("SELECT * FROM conversation_messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Registro não encontrado ou expirado.")
            if row["kind"] == "system":
                raise HTTPException(422, "Mensagens de sistema não recebem agrupamento.")
            topic_key = payload.topic_key
            if payload.new_topic_label is not None:
                label = minimize(payload.new_topic_label.strip())
                if len(label) < 3:
                    raise HTTPException(422, "Informe um nome de assunto com ao menos três caracteres.")
                topic_key = "manual_" + hashlib.sha256(label.casefold().encode()).hexdigest()[:24]
                conn.execute("INSERT OR IGNORE INTO conversation_topics(key,label,reviewed) VALUES (?,?,1)", (topic_key, label))
            if payload.reset_topic:
                description = describe(row["content"], affiliates_from(conn))
                topic_key = description["key"]
                conn.execute("INSERT OR IGNORE INTO conversation_topics(key,label) VALUES (?,?)", (topic_key, minimize(description["label"])))
            if topic_key:
                if not conn.execute("SELECT 1 FROM conversation_topics WHERE key=?", (topic_key,)).fetchone():
                    raise HTTPException(404, "Assunto de destino não encontrado.")
                conn.execute("UPDATE conversation_messages SET topic_key=?,topic_manual=? WHERE id=?", (topic_key, not payload.reset_topic, message_id))
            if payload.answer_state:
                conn.execute("UPDATE conversation_messages SET answer_state=? WHERE id=?", (payload.answer_state, message_id))
            clean_topics(conn)
        return {"ok": True}

    @router.get("/intelligence")
    def get_intelligence(group_id: int | None = None, since: date | None = None, until: date | None = None, days: Literal["7", "15", "30"] = "7"):
        days = int(days)
        query_where(group_id, since, until, days)
        with connect(settings.database_path) as conn:
            return intelligence(conn, group_id, since, until, days)

    @router.get("/intelligence/report")
    def export_report(format: Literal["md", "jsonl", "csv"] = "md", group_id: int | None = None, since: date | None = None, until: date | None = None, days: Literal["7", "15", "30"] = "7"):
        days = int(days)
        query_where(group_id, since, until, days)
        with connect(settings.database_path) as conn:
            result = intelligence(conn, group_id, since, until, days)
        content, content_type = render_report(result, format)
        return Response(content, headers={"Content-Type": content_type, "Content-Disposition": f'attachment; filename="guardiao-relatorio-{days}dias.{format}"', "Cache-Control": "no-store"})

    app.include_router(router)
