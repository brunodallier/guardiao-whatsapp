"""Valida os bloqueios Git em repositórios temporários, sem acessar o remoto."""
from pathlib import Path
import shutil
import subprocess

import pytest

from app.config import ROOT


@pytest.fixture
def git_repo(tmp_path):
    if not shutil.which("git"):
        pytest.skip("Git não está instalado neste ambiente.")

    def git(*args, input=None):
        return subprocess.run(["git", *args], cwd=tmp_path, input=input,
                              capture_output=True, text=True, encoding="utf-8")

    assert git("init", "-b", "main").returncode == 0
    assert git("config", "user.name", "Teste fictício").returncode == 0
    assert git("config", "user.email", "teste@example.com").returncode == 0
    assert git("config", "commit.gpgsign", "false").returncode == 0
    assert git("config", "core.hooksPath", str(ROOT / ".githooks")).returncode == 0
    (tmp_path / "demo.txt").write_text("dado fictício\n", encoding="utf-8")
    assert git("add", "demo.txt").returncode == 0
    assert git("commit", "-m", "Marco fictício inicial").returncode == 0
    return git


def test_main_commit_is_blocked_but_feature_is_allowed(git_repo, tmp_path):
    (tmp_path / "demo.txt").write_text("alteração fictícia\n", encoding="utf-8")
    assert git_repo("add", "demo.txt").returncode == 0
    result = git_repo("commit", "-m", "Não deve entrar na main")
    assert result.returncode != 0
    assert "commits na main" in result.stderr
    assert git_repo("switch", "-c", "feat/teste").returncode == 0
    assert git_repo("commit", "-m", "Commit na feature").returncode == 0


def run_push_hook(input, cwd):
    # Git for Windows inclui sh.exe; em Linux, usa o shell do sistema.
    shell = shutil.which("sh")
    if not shell:
        candidate = Path(shutil.which("git")).resolve().parent.parent / "bin/sh.exe"
        if not candidate.exists():
            pytest.skip("Shell POSIX do Git não disponível.")
        shell = str(candidate)
    return subprocess.run([shell, str(ROOT / ".githooks/pre-push"), "origin", "local-test"],
                          cwd=cwd, input=input, capture_output=True, text=True, encoding="utf-8")


def test_push_main_update_and_deletion_are_blocked(git_repo, tmp_path):
    sha = git_repo("rev-parse", "HEAD").stdout.strip()
    zero = "0" * 40
    initial = run_push_hook(f"refs/heads/main {sha} refs/heads/main {zero}\n", tmp_path)
    assert initial.returncode == 0
    update = run_push_hook(f"refs/heads/main {sha} refs/heads/main {sha}\n", tmp_path)
    assert update.returncode != 0
    assert "atualizacoes diretas da main" in update.stderr
    deletion = run_push_hook(f"(delete) {zero} refs/heads/feat/teste {sha}\n", tmp_path)
    assert deletion.returncode != 0
    assert "exclusao de refs" in deletion.stderr


def test_feature_push_preserves_history(git_repo, tmp_path):
    base = git_repo("rev-parse", "HEAD").stdout.strip()
    assert git_repo("switch", "-c", "feat/teste").returncode == 0
    (tmp_path / "demo.txt").write_text("novo dado fictício\n", encoding="utf-8")
    assert git_repo("add", "demo.txt").returncode == 0
    assert git_repo("commit", "-m", "Avanço fictício").returncode == 0
    head = git_repo("rev-parse", "HEAD").stdout.strip()
    forward = run_push_hook(f"refs/heads/feat/teste {head} refs/heads/feat/teste {base}\n", tmp_path)
    assert forward.returncode == 0
    backwards = run_push_hook(f"refs/heads/feat/teste {base} refs/heads/feat/teste {head}\n", tmp_path)
    assert backwards.returncode != 0
    assert "sem avanco de historico" in backwards.stderr
