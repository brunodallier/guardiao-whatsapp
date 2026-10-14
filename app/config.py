import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    database_path: str = os.getenv("DATABASE_PATH", str(ROOT / "data/guardiao.sqlite3"))
    session_secret: str = os.getenv("SESSION_SECRET", "")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    seed_demo: bool = os.getenv("SEED_DEMO", "true").lower() == "true"
    allowed_hosts: tuple = tuple(os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(","))

    def secret(self):
        if self.session_secret:
            return self.session_secret
        path = Path(self.database_path).resolve().parent / "session.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        return path.read_text(encoding="utf-8").strip()
