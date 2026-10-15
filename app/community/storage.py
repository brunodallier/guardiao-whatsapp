import json
import time


def migrate(conn):
    """Migração aditiva: mantém tabelas, regras e registros da Etapa 01."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS conversation_imports(
        id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id),
        created_at REAL NOT NULL, file_fingerprint TEXT NOT NULL, result TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS conversation_topics(
        key TEXT PRIMARY KEY, label TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS conversation_messages(
        id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id),
        import_id INTEGER REFERENCES conversation_imports(id) ON DELETE SET NULL,
        fingerprint TEXT NOT NULL UNIQUE, timestamp REAL NOT NULL,
        participant TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'permitida', analysis TEXT NOT NULL DEFAULT '{}',
        url_analysis TEXT NOT NULL DEFAULT '{}', link_count INTEGER NOT NULL DEFAULT 0,
        repeat_token TEXT NOT NULL DEFAULT '',
        topic_key TEXT REFERENCES conversation_topics(key), question INTEGER NOT NULL DEFAULT 0,
        complaint INTEGER NOT NULL DEFAULT 0, platforms TEXT NOT NULL DEFAULT '[]',
        answer_state TEXT NOT NULL DEFAULT 'auto', topic_manual INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS conversations_time ON conversation_messages(group_id,timestamp);
    CREATE INDEX IF NOT EXISTS conversations_actor ON conversation_messages(group_id,participant,timestamp);
    CREATE INDEX IF NOT EXISTS conversations_topics ON conversation_messages(topic_key,timestamp);
    """)
    conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES ('conversation_policy',?)", (json.dumps({"retention_days": 7}),))


def policy_from(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='conversation_policy'").fetchone()
    return json.loads(row[0]) if row else {"retention_days": 7}


def prune_conversations(conn, now=None):
    # Importação: metadados limitados pela data da operação, textos pela data da conversa.
    now = time.time() if now is None else now
    cutoff = now - policy_from(conn)["retention_days"] * 86400
    deleted = conn.execute("DELETE FROM conversation_messages WHERE timestamp<?", (cutoff,)).rowcount
    conn.execute("DELETE FROM conversation_imports WHERE created_at<?", (cutoff,))
    clean_topics(conn)
    return deleted


def clean_topics(conn):
    conn.execute("DELETE FROM conversation_topics WHERE key NOT IN (SELECT topic_key FROM conversation_messages WHERE topic_key IS NOT NULL)")
