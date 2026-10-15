import json
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from app.config import ROOT


@contextmanager
def connect(path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.create_function("search_fold", 1, lambda value: "".join(c for c in unicodedata.normalize("NFKD", (value or "").casefold()) if not unicodedata.combining(c)))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize(path, seed_demo=True):
    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, participant_count INTEGER NOT NULL, active INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS affiliates(id INTEGER PRIMARY KEY, domain TEXT UNIQUE NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id), participant TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, status TEXT NOT NULL, analysis TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0, reviewed_at REAL, link_count INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'simulator');
        CREATE INDEX IF NOT EXISTS messages_window ON messages(group_id, participant, created_at);
        CREATE INDEX IF NOT EXISTS messages_time ON messages(created_at);
        """)
        defaults = (ROOT / "config/rules.json").read_text(encoding="utf-8")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('rules', ?)", (defaults,))
        from app.community.storage import migrate
        migrate(conn)
        if seed_demo and not conn.execute("SELECT 1 FROM settings WHERE key='demo_seeded'").fetchone():
            from app.services.messages import simulate
            for name, description, count in [("IA · Primeiros passos", "Dúvidas iniciais e boas-vindas · grupo fictício", 240), ("IA · Plataformas", "Trocas sobre plataformas de treinamento · grupo fictício", 235), ("IA · Comunidade", "Experiências, novidades e suporte · grupo fictício", 225)]:
                conn.execute("INSERT INTO groups(name, description, participant_count, active) VALUES (?, ?, ?, 1)", (name, description, count))
            ids = [row[0] for row in conn.execute("SELECT id FROM groups ORDER BY id LIMIT 3")]
            samples = [(0, "Ana · fictícia", "Como começo a treinar IA?"), (1, "Bruno · fictício", "Alguém tem novidades sobre o HUB?"), (2, "Perfil demo 01", "Oferta em https://cassino-demo.example/bonus"), (1, "Perfil demo 02", "Promoção https://shopee.com.br/oferta-demo"), (0, "Carla · fictícia", "Vi uma notícia sobre cassino e BET. Isso não é link."), (2, "Perfil demo 03", "Veja https://bit.ly/demo-guardiao"), (1, "Daniel · fictício", "Estou com dificuldade no cadastro do Mimix."), (0, "Perfil demo 04", "Acesse https://plataforma-demo.example/?ref=TERCEIRO-DEMO")]
            for i, (index, participant, content) in enumerate(samples):
                simulate(conn, ids[index], participant, content, now=time.time() - (len(samples)-i)*180, source="demo")
            conn.execute("INSERT INTO settings VALUES ('demo_seeded', 'true')")


def rules_from(conn):
    return json.loads(conn.execute("SELECT value FROM settings WHERE key='rules'").fetchone()[0])


def affiliates_from(conn):
    return [dict(id=row["id"], **json.loads(row["data"])) for row in conn.execute("SELECT * FROM affiliates ORDER BY id")]


def prune(conn):
    cutoff = time.time() - rules_from(conn)["retention_days"] * 86400
    return conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,)).rowcount
