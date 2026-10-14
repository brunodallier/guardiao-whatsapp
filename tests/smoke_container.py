"""Smoke test local de uma imagem descartavel; nao conecta servicos externos."""
import json
import os
import sqlite3
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen


assert os.getuid() != 0, "O servidor precisa executar sem privilegios de root."
process = subprocess.Popen([
    "python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"
])
try:
    for _ in range(100):
        try:
            with urlopen("http://127.0.0.1:8000/api/auth/session", timeout=1) as response:
                session = json.load(response)
            break
        except URLError:
            if process.poll() is not None:
                raise RuntimeError("O servidor encerrou durante a inicializacao.")
            time.sleep(0.1)
    else:
        raise RuntimeError("O servidor nao iniciou a tempo.")
    assert session["setup_required"] is True
    assert session["username"] is None
    assert session["csrf"]
    with urlopen("http://127.0.0.1:8000", timeout=2) as response:
        assert response.status == 200
    with sqlite3.connect("/app/data/guardiao.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 8
    print("Container OK: usuario sem privilegios, servidor, sessao e SQLite demo.")
finally:
    process.terminate()
    process.wait(timeout=5)
