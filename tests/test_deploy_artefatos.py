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


def test_dockerfile_comando_de_producao():
    d = _ler("Dockerfile")
    cmd = d[d.index("CMD ["):]
    assert "--workers 1" in cmd
    assert "--proxy-headers" in cmd
    assert "--forwarded-allow-ips" in cmd
    assert "--reload" not in cmd
    assert "--forwarded-allow-ips '*'" not in cmd and "--forwarded-allow-ips=*" not in cmd


def test_dockerfile_ambiente_de_producao_e_proxy_sem_curinga():
    d = _ler("Dockerfile")
    assert re.search(r"LOCACAO_AMBIENTE=producao", d)
    assert not re.search(r"LOCACAO_AMBIENTE=dev", d)
    padrao = re.search(r'FORWARDED_ALLOW_IPS="([^"]*)"', d).group(1)
    assert padrao and "*" not in padrao


def test_proxy_confiavel_padrao_cobre_o_docker_e_exclui_a_internet():
    from uvicorn.middleware.proxy_headers import _TrustedHosts

    padrao = re.search(r'FORWARDED_ALLOW_IPS="([^"]*)"', _ler("Dockerfile")).group(1)
    confiaveis = _TrustedHosts(padrao)
    assert "172.18.0.4" in confiaveis and "10.0.1.5" in confiaveis
    assert "203.0.113.9" not in confiaveis


def _app_atras_do_proxy(monkeypatch, ip_do_proxy: str):
    from starlette.testclient import TestClient
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    from src.web.app import criar_app

    monkeypatch.setenv("SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "chave-anonima-ficticia")
    padrao = re.search(r'FORWARDED_ALLOW_IPS="([^"]*)"', _ler("Dockerfile")).group(1)
    app = ProxyHeadersMiddleware(criar_app(desenvolvimento=False), trusted_hosts=padrao)
    return TestClient(app, client=(ip_do_proxy, 50000))


def test_atras_do_proxy_confiavel_o_app_percebe_https_e_hsts(monkeypatch):
    cliente = _app_atras_do_proxy(monkeypatch, "172.18.0.4")
    r = cliente.get("/saude", headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "203.0.113.9"})
    assert r.status_code == 200
    assert "max-age" in r.headers.get("strict-transport-security", "")
    assert "content-security-policy" in r.headers


def test_cabecalhos_de_origem_nao_confiavel_sao_ignorados(monkeypatch):
    cliente = _app_atras_do_proxy(monkeypatch, "203.0.113.50")
    r = cliente.get("/saude", headers={"X-Forwarded-Proto": "https"})
    assert "strict-transport-security" not in r.headers


def test_em_producao_componentes_nao_existe(monkeypatch):
    cliente = _app_atras_do_proxy(monkeypatch, "172.18.0.4")
    assert cliente.get("/componentes").status_code == 404


def _job_deploy() -> str:
    ci = _ler(".github/workflows/ci.yml")
    return ci[ci.index("\n  deploy:"):]


def test_ci_deploy_so_na_main_e_depois_do_pytest():
    job = _job_deploy()
    assert "needs: testes-python" in job
    assert "github.event_name == 'push'" in job and "refs/heads/main" in job
    assert "pull_request" not in job


def test_ci_deploy_usa_segredos_do_github_sem_valores_no_arquivo():
    job = _job_deploy()
    for nome in ("COOLIFY_URL", "COOLIFY_TOKEN", "COOLIFY_APP_UUID"):
        assert f"${{{{ secrets.{nome} }}}}" in job
    assert not re.search(r"Bearer [A-Za-z0-9]{10,}", job)


def test_ci_testa_na_versao_da_imagem():
    ci = _ler(".github/workflows/ci.yml")
    versao = re.search(r"^FROM python:(\d+\.\d+)", _ler("Dockerfile"), re.M).group(1)
    assert f'"{versao}"' in ci[: ci.index("navegador-login:")]
