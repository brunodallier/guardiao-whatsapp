import json

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app


@pytest.fixture
def rules():
    return json.loads((ROOT / "config/rules.json").read_text(encoding="utf-8"))


@pytest.fixture
def profile():
    return {"platform": "Plataforma fictícia", "domain": "plataforma.example", "referral_url": "https://plataforma.example/convite/MEU-DEMO?ref=MEU-DEMO", "affiliate_code": "MEU-DEMO", "affiliate_parameters": ["ref"], "affiliate_path_prefix": "/convite/", "allowed_links": [], "allowed_domains": []}


@pytest.fixture
def client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "test.sqlite3"), session_secret="segredo-exclusivo-de-teste", seed_demo=False)
    with TestClient(create_app(settings)) as client:
        client.settings = settings
        yield client


@pytest.fixture
def admin(client):
    session = client.get("/api/auth/session").json()
    client.headers["X-CSRF-Token"] = session["csrf"]
    response = client.post("/api/auth/setup", json={"username": "admin_teste", "password": "senha-ficticia-12345"})
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return client


@pytest.fixture
def group(admin):
    return admin.post("/api/groups", json={"name": "Grupo fictício", "description": "Teste", "participant_count": 10}).json()
