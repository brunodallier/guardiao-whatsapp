import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect
from app.main import create_app


def send(client, group, content="Conversa de teste", participant="Pessoa fictícia"):
    return client.post("/api/simulate", json={"group_id": group["id"], "participant": participant, "content": content})


@pytest.mark.parametrize("path", ["/api/dashboard", "/api/groups", "/api/affiliates", "/api/rules", "/api/history", "/api/history/1"])
def test_private_endpoints(client, path):
    assert client.get(path).status_code == 401


def test_setup_csrf_password_and_duplicate(client):
    credentials = {"username": "admin", "password": "senha-ficticia-segura"}
    assert client.post("/api/auth/setup", json=credentials).status_code == 403
    token = client.get("/api/auth/session").json()["csrf"]
    result = client.post("/api/auth/setup", json=credentials, headers={"X-CSRF-Token": token})
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf"]
    assert client.post("/api/auth/setup", json=credentials).status_code == 409
    with connect(client.settings.database_path) as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("pbkdf2_sha256$")
    assert credentials["password"] not in stored
    assert "httponly" in result.headers["set-cookie"].lower()
    assert "samesite=strict" in result.headers["set-cookie"].lower()


def test_login_logout_and_csrf_rotation(admin):
    old_token = admin.headers["X-CSRF-Token"]
    assert admin.post("/api/auth/logout").status_code == 200
    assert admin.get("/api/dashboard").status_code == 401
    session = admin.get("/api/auth/session").json()
    admin.headers["X-CSRF-Token"] = session["csrf"]
    credentials = {"username": "admin_teste", "password": "senha-ficticia-12345"}
    result = admin.post("/api/auth/login", json=credentials)
    assert result.status_code == 200
    assert result.json()["csrf"] != old_token
    admin.headers["X-CSRF-Token"] = result.json()["csrf"]
    assert admin.get("/api/dashboard").status_code == 200


def test_login_rate_limit(admin):
    admin.post("/api/auth/logout")
    admin.headers["X-CSRF-Token"] = admin.get("/api/auth/session").json()["csrf"]
    for _ in range(5):
        assert admin.post("/api/auth/login", json={"username": "admin", "password": "senha-errada-demo"}).status_code == 401
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "senha-errada-demo"}).status_code == 429


def test_group_edit_and_inactive(admin, group):
    result = admin.put('/api/groups/'+str(group["id"]), json={"name": "Nome atualizado", "active": False})
    assert result.status_code == 200
    assert admin.get('/api/groups').json()[0]["name"] == "Nome atualizado"
    assert send(admin, group).status_code == 409


def test_affiliate_crud_and_comparison(admin, group):
    payload = {"platform": "Plataforma de teste", "domain": "teste.example", "referral_url": "https://teste.example/?ref=MEU-DEMO", "affiliate_code": "MEU-DEMO", "affiliate_parameters": ["ref"]}
    result = admin.post('/api/affiliates', json=payload)
    assert result.status_code == 201
    item = result.json()
    assert admin.post('/api/affiliates', json=payload).status_code == 409
    assert send(admin, group, "https://teste.example/?ref=MEU-DEMO").json()["status"] == "permitida"
    assert send(admin, group, "https://teste.example/?ref=OUTRO-DEMO").json()["findings"][0]["rule"] == "affiliate"
    payload["platform"] = "Nome alterado"
    assert admin.put(f'/api/affiliates/{item["id"]}', json=payload).status_code == 200
    assert admin.delete(f'/api/affiliates/{item["id"]}').status_code == 200
    assert admin.get('/api/affiliates').json() == []


@pytest.mark.parametrize("change", [{"domain":"https://teste.example"}, {"referral_url":"https://outro.example/?ref=x"}, {"allowed_links":["javascript://teste.example"]}, {"affiliate_path_prefix":"ref/"}, {"platform":"  "}, {"affiliate_parameters":[" "]}])
def test_affiliate_validation(admin, change):
    payload = {"platform":"Teste", "domain":"teste.example", **change}
    assert admin.post('/api/affiliates', json=payload).status_code == 422


def test_history_review_filters_and_deletion(admin, group):
    item = send(admin, group, "https://cassino-demo.example").json()
    send(admin, group, "Mensagem permitida")
    assert admin.get('/api/dashboard').json()["stats"]["pending"] == 1
    results = admin.get('/api/history', params={"status":"critica", "reviewed":"false", "group_id":group["id"], "q":"cassino", "page_size":1}).json()
    assert results["total"] == 1
    assert admin.get(f'/api/history/{item["id"]}').json()["status"] == "critica"
    assert admin.post(f'/api/history/{item["id"]}/review').status_code == 200
    assert admin.get('/api/dashboard').json()["stats"]["pending"] == 0
    assert admin.get('/api/history?reviewed=true').json()["total"] == 1
    assert admin.request('DELETE','/api/history',json={"confirmation":"errado"}).status_code == 422
    assert admin.request('DELETE','/api/history',json={"confirmation":"EXCLUIR","group_id":group["id"]}).json()["deleted"] == 2
    assert len(admin.get('/api/groups').json()) == 1


def test_repeat_is_scoped_to_group_and_participant(admin, group):
    another = admin.post('/api/groups', json={"name":"Outro grupo"}).json()
    send(admin, group)
    send(admin, another)
    send(admin, group, participant="Outra pessoa")
    assert send(admin, group).json()["status"] == "permitida"
    assert send(admin, group).json()["findings"][0]["rule"] == "repeat"


def test_concurrent_messages_are_counted(admin, group):
    # TestClient compartilha apenas cookies já estabelecidos; API serializa a análise/gravação.
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda _: send(admin, group).json(), range(3)))
    assert sum(result["status"] == "suspeita" for result in results) == 1


def test_rules_validation_and_retention(admin, group):
    item = send(admin, group).json()
    with connect(admin.settings.database_path) as conn:
        conn.execute("UPDATE messages SET created_at=? WHERE id=?", (time.time()-3*86400,item["id"]))
    rules = admin.get('/api/rules').json()
    rules["retention_days"] = 1
    response = admin.put('/api/rules',json=rules)
    assert response.json()["deleted"] == 1
    assert admin.get('/api/history').json()["total"] == 0
    rules["repeat_threshold"] = 0
    assert admin.put('/api/rules',json=rules).status_code == 422


def test_csrf_required_on_mutations(admin):
    admin.headers.pop("X-CSRF-Token")
    assert admin.post('/api/groups',json={"name":"Teste"}).status_code == 403
    assert admin.get('/api/groups').status_code == 200


def test_bad_group_empty_message_and_invalid_filter(admin, group):
    assert send(admin, {"id":999}).status_code == 404
    assert send(admin, group, content="   ").status_code == 422
    assert admin.get('/api/history?status=invalid').status_code == 422
    assert admin.get('/api/history?page=0').status_code == 422


def test_seed_is_idempotent_and_has_no_affiliates(tmp_path):
    settings = Settings(database_path=str(tmp_path/'demo.sqlite3'),session_secret='teste-demo',seed_demo=True)
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            assert client.get('/').status_code == 200
    with connect(settings.database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM groups').fetchone()[0] == 3
        assert conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 8
        assert conn.execute('SELECT COUNT(*) FROM affiliates').fetchone()[0] == 0


def test_static_and_security_headers(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'script-src' in response.headers['content-security-policy']
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/api/auth/session', headers={"Host":"evil.example"}).status_code == 400


def test_global_parameter_normalization(admin, group):
    rules = admin.get('/api/rules').json()
    rules['affiliate_parameters'] = [' REF ', 'ref']
    assert admin.put('/api/rules', json=rules).status_code == 200
    assert admin.get('/api/rules').json()['affiliate_parameters'] == ['ref']
    assert send(admin, group, 'https://desconhecida.example/?ref=TESTE').json()['findings'][0]['rule'] == 'affiliate'
    rules['affiliate_parameters'] = [' ']
    assert admin.put('/api/rules', json=rules).status_code == 422
