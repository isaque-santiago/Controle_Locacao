"""Artefatos de deploy (Fase 5): Dockerfile, .dockerignore e dependências de produção."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _ler(nome: str) -> str:
    return (RAIZ / nome).read_text(encoding="utf-8")


def _pacotes(nome: str) -> set[str]:
    return {
        re.split(r"[=<>\[]", linha.strip(), maxsplit=1)[0].lower()
        for linha in _ler(nome).splitlines()
        if linha.strip() and not linha.lstrip().startswith(("#", "-"))
    }


def test_requirements_de_producao_nao_traz_ferramentas_de_teste():
    pacotes = _pacotes("requirements.txt")
    assert {"fastapi", "uvicorn", "supabase", "jinja2"} <= pacotes
    assert not pacotes & {"pytest", "playwright", "axe-playwright-python"}


def test_requirements_dev_inclui_producao_e_pytest():
    texto = _ler("requirements-dev.txt")
    assert "-r requirements.txt" in texto
    assert "pytest" in _pacotes("requirements-dev.txt")


def test_dependencias_de_producao_estao_fixadas():
    for linha in _ler("requirements.txt").splitlines():
        if linha.strip() and not linha.startswith("#"):
            assert "==" in linha, f"versão não fixada: {linha}"


def test_dockerfile_usa_python_312_slim_e_usuario_sem_privilegios():
    d = _ler("Dockerfile")
    assert re.search(r"^FROM python:3\.12-slim\s*$", d, re.M)
    usuarios = re.findall(r"^USER (\S+)", d, re.M)
    assert usuarios and usuarios[-1] not in ("root", "0")


def test_dockerfile_tem_healthcheck_em_saude():
    d = _ler("Dockerfile")
    assert "HEALTHCHECK" in d
    assert "/saude" in d


def test_dockerfile_nao_instala_dev_nem_leva_segredos():
    d = _ler("Dockerfile")
    assert "requirements-dev" not in d and "e2e" not in d
    assert not re.search(r"^(ENV|ARG)\s+\S*(KEY|SECRET|TOKEN|PASSWORD|SENHA)", d, re.M | re.I)
    assert "COPY . " not in d  # só src e static entram na imagem


def test_dockerignore_exclui_segredos_testes_e_ambiente_local():
    linhas = {l.strip() for l in _ler(".dockerignore").splitlines()}
    assert {".env", ".git", ".venv", "tests", "e2e"} <= linhas
    assert ".sessoes_dev.json*" in linhas
