import asyncio
import hmac
import json
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ROOT, Settings
from app.db import connect, initialize, rules_from, affiliates_from, prune
from app.models import Credentials, GroupInput, AffiliateInput, RulesInput, MessageInput, DeleteHistoryInput
from app.security import hash_password, verify_password
from app.services.messages import simulate
from app.community.routes import register_community_routes
from app.community.storage import prune_conversations


def create_app(settings=None):
    settings = settings or Settings()
    attempts = {}
    attempts_lock = threading.Lock()

    def clean_history():
        with connect(settings.database_path) as conn:
            prune(conn)
            prune_conversations(conn)

    async def maintenance():
        last_database_cleanup = time.monotonic()
        while True:
            await asyncio.sleep(5)
            app.state.conversation_previews.cleanup()
            if time.monotonic() - last_database_cleanup >= 3600:
                await asyncio.to_thread(clean_history)
                last_database_cleanup = time.monotonic()

    @asynccontextmanager
    async def lifespan(app):
        initialize(settings.database_path, settings.seed_demo)
        clean_history()
        task = asyncio.create_task(maintenance())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Guardião IA · API local", version="0.2.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret(), session_cookie="guardiao_session", same_site="strict", https_only=settings.cookie_secure, max_age=28800)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith("/api") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exception):
        fields = [".".join(str(part) for part in error["loc"][1:]) for error in exception.errors()]
        return JSONResponse(status_code=422, content={"detail": "Revise os campos informados: " + ", ".join(fields) + "."})

    def csrf(request: Request):
        expected = request.session.get("csrf", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not hmac.compare_digest(expected, supplied):
            raise HTTPException(403, "Sessão de segurança inválida. Recarregue a página.")

    def admin(request: Request):
        user_id = request.session.get("user_id")
        with connect(settings.database_path) as conn:
            user = conn.execute("SELECT id, username FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(401, "Entre com sua conta para continuar.")
        if request.method not in ("GET", "HEAD"):
            csrf(request)
        return dict(user)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "app/static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")

    @app.get("/api/auth/session")
    def session(request: Request):
        if "csrf" not in request.session:
            request.session["csrf"] = secrets.token_urlsafe(32)
        with connect(settings.database_path) as conn:
            setup_required = not bool(conn.execute("SELECT 1 FROM users").fetchone())
            user = conn.execute("SELECT username FROM users WHERE id=?", (request.session.get("user_id"),)).fetchone()
        return {"setup_required": setup_required, "username": user[0] if user else None, "csrf": request.session["csrf"]}

    @app.post("/api/auth/setup", dependencies=[Depends(csrf)])
    def setup(credentials: Credentials, request: Request):
        with connect(settings.database_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM users").fetchone():
                raise HTTPException(409, "O administrador já foi cadastrado.")
            cursor = conn.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)", (credentials.username, hash_password(credentials.password)))
            request.session.clear()
            request.session.update(user_id=cursor.lastrowid, csrf=secrets.token_urlsafe(32))
        return {"username": credentials.username, "csrf": request.session["csrf"]}

    @app.post("/api/auth/login", dependencies=[Depends(csrf)])
    def login(credentials: Credentials, request: Request):
        key = request.client.host if request.client else "local"
        now = time.time()
        with attempts_lock:
            for address in list(attempts):
                attempts[address] = [timestamp for timestamp in attempts[address] if timestamp > now-300]
                if not attempts[address]:
                    del attempts[address]
            recent = attempts.get(key, [])
            if len(recent) >= 5:
                raise HTTPException(429, "Muitas tentativas. Aguarde cinco minutos.")
            attempts[key] = recent + [now]
        with connect(settings.database_path) as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (credentials.username,)).fetchone()
        if not user or not verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(401, "Usuário ou senha inválidos.")
        with attempts_lock:
            attempts.pop(key, None)
        request.session.clear()
        request.session.update(user_id=user["id"], csrf=secrets.token_urlsafe(32))
        return {"username": user["username"], "csrf": request.session["csrf"]}

    @app.post("/api/auth/logout", dependencies=[Depends(admin)])
    def logout(request: Request):
        request.session.clear()
        return {"ok": True}

    @app.get("/api/dashboard", dependencies=[Depends(admin)])
    def dashboard():
        with connect(settings.database_path) as conn:
            prune(conn)
            stats = dict(conn.execute("SELECT COUNT(*) AS analyzed, COALESCE(SUM(status='suspeita'),0) AS suspicious, COALESCE(SUM(status='critica'),0) AS critical, COALESCE(SUM(status='permitida'),0) AS allowed, COALESCE(SUM(status!='permitida' AND reviewed=0),0) AS pending FROM messages").fetchone())
            stats["groups"] = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            groups = [dict(row) for row in conn.execute("SELECT g.*, COUNT(m.id) AS analyzed, COALESCE(SUM(m.status!='permitida' AND m.reviewed=0),0) AS pending FROM groups g LEFT JOIN messages m ON m.group_id=g.id GROUP BY g.id ORDER BY g.id")]
            recent = [serialize_message(row) for row in conn.execute("SELECT m.*, g.name AS group_name FROM messages m JOIN groups g ON g.id=m.group_id WHERE status!='permitida' ORDER BY created_at DESC, m.id DESC LIMIT 5")]
            buckets = []
            now = time.time()
            for index in range(11, -1, -1):
                end = now-index*3600
                start = end-3600
                row = conn.execute("SELECT COUNT(*) AS total, COALESCE(SUM(status!='permitida'),0) AS alerts FROM messages WHERE created_at>=? AND created_at<?", (start, end)).fetchone()
                buckets.append({"end": end, **dict(row)})
            return {"stats": stats, "groups": groups, "recent": recent, "activity": buckets, "retention_days": rules_from(conn)["retention_days"]}

    @app.get("/api/groups", dependencies=[Depends(admin)])
    def groups():
        with connect(settings.database_path) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM groups ORDER BY id")]

    @app.post("/api/groups", dependencies=[Depends(admin)], status_code=201)
    def add_group(payload: GroupInput):
        with connect(settings.database_path) as conn:
            cursor = conn.execute("INSERT INTO groups(name, description, participant_count, active) VALUES (?, ?, ?, ?)", tuple(payload.model_dump().values()))
            return {"id": cursor.lastrowid, **payload.model_dump()}

    @app.put("/api/groups/{group_id}", dependencies=[Depends(admin)])
    def update_group(group_id: int, payload: GroupInput):
        with connect(settings.database_path) as conn:
            changed = conn.execute("UPDATE groups SET name=?, description=?, participant_count=?, active=? WHERE id=?", (*payload.model_dump().values(), group_id)).rowcount
            if not changed:
                raise HTTPException(404, "Grupo não encontrado.")
        return {"id": group_id, **payload.model_dump()}

    @app.get("/api/affiliates", dependencies=[Depends(admin)])
    def affiliates():
        with connect(settings.database_path) as conn:
            return affiliates_from(conn)

    def save_affiliate(payload, affiliate_id=None):
        with connect(settings.database_path) as conn:
            try:
                if affiliate_id is None:
                    affiliate_id = conn.execute("INSERT INTO affiliates(domain, data) VALUES (?, ?)", (payload.domain, payload.model_dump_json())).lastrowid
                else:
                    if not conn.execute("UPDATE affiliates SET domain=?, data=? WHERE id=?", (payload.domain, payload.model_dump_json(), affiliate_id)).rowcount:
                        raise HTTPException(404, "Plataforma não encontrada.")
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Este domínio já possui uma plataforma cadastrada.")
        return {"id": affiliate_id, **payload.model_dump()}

    @app.post("/api/affiliates", dependencies=[Depends(admin)], status_code=201)
    def add_affiliate(payload: AffiliateInput):
        return save_affiliate(payload)

    @app.put("/api/affiliates/{affiliate_id}", dependencies=[Depends(admin)])
    def update_affiliate(affiliate_id: int, payload: AffiliateInput):
        return save_affiliate(payload, affiliate_id)

    @app.delete("/api/affiliates/{affiliate_id}", dependencies=[Depends(admin)])
    def delete_affiliate(affiliate_id: int):
        with connect(settings.database_path) as conn:
            if not conn.execute("DELETE FROM affiliates WHERE id=?", (affiliate_id,)).rowcount:
                raise HTTPException(404, "Plataforma não encontrada.")
        return {"ok": True}

    @app.get("/api/rules", dependencies=[Depends(admin)])
    def get_rules():
        with connect(settings.database_path) as conn:
            return rules_from(conn)

    @app.put("/api/rules", dependencies=[Depends(admin)])
    def update_rules(payload: RulesInput):
        with connect(settings.database_path) as conn:
            conn.execute("UPDATE settings SET value=? WHERE key='rules'", (payload.model_dump_json(),))
            deleted = prune(conn)
        return {"ok": True, "deleted": deleted}

    @app.post("/api/simulate", dependencies=[Depends(admin)], status_code=201)
    def simulate_message(payload: MessageInput):
        with connect(settings.database_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            group = conn.execute("SELECT * FROM groups WHERE id=?", (payload.group_id,)).fetchone()
            if not group:
                raise HTTPException(404, "Grupo não encontrado.")
            if not group["active"]:
                raise HTTPException(409, "Ative o grupo antes de simular uma mensagem.")
            return simulate(conn, payload.group_id, payload.participant, payload.content)

    @app.get("/api/history", dependencies=[Depends(admin)])
    def history(status: str | None = None, group_id: int | None = None, reviewed: bool | None = None, q: str = Query(default="", max_length=200), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
        clauses, values = [], []
        if status:
            if status == "ocorrencias":
                clauses.append("m.status!='permitida'")
            elif status in ("permitida", "suspeita", "critica"):
                clauses.append("m.status=?")
                values.append(status)
            else:
                raise HTTPException(422, "Classificação inválida.")
        if group_id is not None:
            clauses.append("m.group_id=?")
            values.append(group_id)
        if reviewed is not None:
            clauses.append("m.reviewed=? AND m.status!='permitida'")
            values.append(reviewed)
        if q:
            clauses.append("(instr(lower(m.content),lower(?))>0 OR instr(lower(m.participant),lower(?))>0)")
            values.extend([q, q])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with connect(settings.database_path) as conn:
            prune(conn)
            total = conn.execute("SELECT COUNT(*) FROM messages m" + where, values).fetchone()[0]
            rows = conn.execute("SELECT m.*, g.name AS group_name FROM messages m JOIN groups g ON g.id=m.group_id" + where + " ORDER BY m.created_at DESC, m.id DESC LIMIT ? OFFSET ?", (*values, page_size, (page-1)*page_size))
            return {"items": [serialize_message(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    @app.get("/api/history/{message_id}", dependencies=[Depends(admin)])
    def message_detail(message_id: int):
        with connect(settings.database_path) as conn:
            prune(conn)
            row = conn.execute("SELECT m.*, g.name AS group_name FROM messages m JOIN groups g ON g.id=m.group_id WHERE m.id=?", (message_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Mensagem não encontrada ou já expirada.")
            return serialize_message(row)

    @app.post("/api/history/{message_id}/review", dependencies=[Depends(admin)])
    def review(message_id: int):
        with connect(settings.database_path) as conn:
            prune(conn)
            if not conn.execute("UPDATE messages SET reviewed=1, reviewed_at=? WHERE id=? AND status!='permitida'", (time.time(), message_id)).rowcount:
                raise HTTPException(404, "Alerta não encontrado.")
        return {"ok": True}

    @app.delete("/api/history", dependencies=[Depends(admin)])
    def delete_history(payload: DeleteHistoryInput):
        if payload.confirmation != "EXCLUIR":
            raise HTTPException(422, "Digite EXCLUIR para confirmar a exclusão do histórico.")
        with connect(settings.database_path) as conn:
            if payload.group_id is None:
                deleted = conn.execute("DELETE FROM messages").rowcount
            else:
                deleted = conn.execute("DELETE FROM messages WHERE group_id=?", (payload.group_id,)).rowcount
        return {"deleted": deleted}

    register_community_routes(app, settings, admin)
    return app


def serialize_message(row):
    message = dict(row)
    message.update(json.loads(message.pop("analysis")))
    message["reviewed"] = bool(message["reviewed"])
    return message


app = create_app()
