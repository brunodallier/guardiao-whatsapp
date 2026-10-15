"""Smoke test local de uma imagem descartavel; nao conecta servicos externos."""
import json
import os
import sqlite3
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen
from urllib.request import Request,build_opener,HTTPCookieProcessor
from http.cookiejar import CookieJar
from datetime import datetime,timedelta,timezone


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
        assert conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0] == 0
    client=build_opener(HTTPCookieProcessor(CookieJar()))
    with client.open('http://127.0.0.1:8000/api/auth/session') as response:
        csrf=json.load(response)['csrf']
    request=Request('http://127.0.0.1:8000/api/auth/setup',data=json.dumps({'username':'demo_container','password':'senha-ficticia-container'}).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
    with client.open(request) as response:
        csrf=json.load(response)['csrf']
    stamp=datetime.now(timezone(timedelta(hours=-3)))-timedelta(days=1)
    raw=f'{stamp:%d/%m/%Y, %H:%M} - Pessoa Ficticia: Como sacar na HUB?'.encode()
    request=Request('http://127.0.0.1:8000/api/conversations/preview?group_id=1',data=raw,headers={'Content-Type':'text/plain','X-CSRF-Token':csrf})
    with client.open(request) as response:
        preview=json.load(response)
    assert preview['summary']['ready']==1
    request=Request('http://127.0.0.1:8000/api/conversations/import',data=json.dumps({'token':preview['token'],'confirmed':True}).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
    with client.open(request) as response:
        assert json.load(response)['inserted']==1
    with client.open('http://127.0.0.1:8000/api/intelligence?days=30') as response:
        assert json.load(response)['totals']['questions']==1
    with client.open('http://127.0.0.1:8000/api/intelligence/report?format=csv') as response:
        assert response.status==200
    print("Container OK: usuario sem privilegios, Etapa 01, importacao, inteligencia e relatorio CSV.")
finally:
    process.terminate()
    process.wait(timeout=5)
