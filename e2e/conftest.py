"""Fixtures e opções da suíte de navegador (Playwright).

Uso, com o app rodando (dados FICTÍCIOS do projeto Supabase de desenvolvimento):

    .venv\\Scripts\\python.exe -m pytest e2e                       # Chromium desktop
    .venv\\Scripts\\python.exe -m pytest e2e --perfil chromium-desktop --perfil chromium-movel --perfil firefox --perfil webkit
    .venv\\Scripts\\python.exe -m pytest e2e --larguras 320,390 --temas claro --capturas

Variáveis de ambiente: E2E_BASE_URL, E2E_EMAIL, E2E_SENHA, E2E_DADOS (vazio|normal|extremo).
Veja e2e/README.md."""

from dataclasses import dataclass
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from e2e.achados import Achado, Coletor
from e2e.config import (
    ESTADOS_DADOS,
    LARGURA_MAXIMA_MOVEL,
    PERFIL_PADRAO,
    PERFIS,
    TEMAS,
    VIEWPORTS,
    base_url,
    credenciais,
    estado_dados,
)

_HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class Cenario:
    perfil: str
    largura: int
    tema: str

    @property
    def altura(self) -> int:
        return VIEWPORTS[self.largura]

    @property
    def id(self) -> str:
        return f"{self.perfil}-{self.largura}-{self.tema}"


# --------------------------------------------------------------------------
# Opções de linha de comando
# --------------------------------------------------------------------------
def pytest_addoption(parser):
    grupo = parser.getgroup("e2e", "Testes de navegador (UI/UX)")
    grupo.addoption("--perfil", action="append", choices=sorted(PERFIS), help="Perfil de navegador (repetível).")
    grupo.addoption("--larguras", default=",".join(map(str, VIEWPORTS)), help="Larguras em px, separadas por vírgula.")
    grupo.addoption("--temas", default=",".join(TEMAS), help="Temas: claro, escuro.")
    grupo.addoption("--capturas", action="store_true", help="Salva capturas de tela em e2e/capturas/.")
    grupo.addoption("--e2e-estrito", action="store_true", help="Reprova o teste quando houver achado P0.")
    grupo.addoption("--visivel", action="store_true", help="Abre o navegador com janela.")
    grupo.addoption(
        "--atualizar-referencia",
        action="store_true",
        help="Grava as capturas atuais como referência da regressão visual (e2e/referencia/).",
    )
    grupo.addoption(
        "--tolerancia-visual",
        type=float,
        default=0.3,
        help="Percentual de pixels que pode diferir da referência (padrão 0,3).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "autenticado: exige E2E_EMAIL e E2E_SENHA (projeto de desenvolvimento).")


def _cenarios(config) -> list[Cenario]:
    perfis = config.getoption("--perfil") or [PERFIL_PADRAO]
    larguras = [int(x) for x in config.getoption("--larguras").split(",") if x.strip()]
    temas = [x.strip() for x in config.getoption("--temas").split(",") if x.strip()]
    for largura in larguras:
        if largura not in VIEWPORTS:
            raise pytest.UsageError(f"Largura {largura} fora da matriz {sorted(VIEWPORTS)}.")
    for tema in temas:
        if tema not in TEMAS:
            raise pytest.UsageError(f"Tema inválido: {tema}.")
    lista = []
    for perfil in perfis:
        for largura in larguras:
            if PERFIS[perfil].movel and largura > LARGURA_MAXIMA_MOVEL:
                continue  # perfil móvel só faz sentido em larguras de celular/tablet
            for tema in temas:
                lista.append(Cenario(perfil, largura, tema))
    return lista


def pytest_generate_tests(metafunc):
    if "cenario" in metafunc.fixturenames:
        cenarios = _cenarios(metafunc.config)
        # scope="session": o cenário (e a página autenticada que ele resolve) é reaproveitado
        # entre módulos. O login por senha em si é feito uma vez por PERFIL, não por cenário
        # (ver pagina_logada / _contextos_autenticados).
        metafunc.parametrize("cenario", cenarios, ids=[c.id for c in cenarios], scope="session")


def pytest_collection_modifyitems(config, items):
    if credenciais() is None:
        pular = pytest.mark.skip(reason="defina E2E_EMAIL e E2E_SENHA (usuário do projeto de DESENVOLVIMENTO)")
        for item in items:
            if "autenticado" in item.keywords:
                item.add_marker(pular)


# --------------------------------------------------------------------------
# Segurança: só roda contra ambiente local e com dados fictícios
# --------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _ambiente_seguro():
    host = urlparse(base_url()).hostname
    if host not in _HOSTS_LOCAIS:
        pytest.exit(
            f"E2E_BASE_URL aponta para '{host}'. A suíte só roda em localhost, contra o projeto "
            "Supabase de DESENVOLVIMENTO (dados fictícios): as capturas não podem conter dados reais.",
            returncode=2,
        )
    if estado_dados() not in ESTADOS_DADOS:
        pytest.exit(f"E2E_DADOS deve ser um de {ESTADOS_DADOS}.", returncode=2)


# --------------------------------------------------------------------------
# Achados
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def coletor():
    c = Coletor()
    yield c
    c.gravar()


@pytest.fixture(scope="session")
def registrar(coletor):
    """Devolve uma função que registra achados já com o contexto do cenário."""

    def _fabrica(cenario: Cenario, fluxo: str = ""):
        def _registrar(severidade, tipo, pagina, descricao, elemento="", detalhe=""):
            coletor.registrar(
                Achado(
                    severidade=severidade,
                    tipo=tipo,
                    pagina=pagina,
                    descricao=descricao,
                    elemento=elemento,
                    detalhe=detalhe,
                    perfil=cenario.perfil,
                    largura=cenario.largura,
                    altura=cenario.altura,
                    tema=cenario.tema,
                    dados=estado_dados(),
                    fluxo=fluxo,
                )
            )

        return _registrar

    return _fabrica


def pytest_terminal_summary(terminalreporter):
    from e2e.achados import PASTA_RESULTADOS

    arquivo = PASTA_RESULTADOS / "achados.md"
    if arquivo.exists():
        terminalreporter.write_line(f"Achados de UI/UX registrados em {arquivo}")


# --------------------------------------------------------------------------
# Navegadores
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def playwright_sessao():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def navegador(playwright_sessao: Playwright, cenario: Cenario, request):
    perfil = PERFIS[cenario.perfil]
    lancador = getattr(playwright_sessao, perfil.navegador)
    browser = lancador.launch(headless=not request.config.getoption("--visivel"))
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def _contextos_autenticados(playwright_sessao: Playwright, request):
    """Um único contexto (e login) por PERFIL, reaproveitado entre larguras e temas.

    O login por senha do Supabase Auth tem limite de taxa bem mais apertado que o de
    renovar sessão (poucas dezenas a cada poucos minutos): um contexto novo por cenário
    faria até 40 logins por execução da matriz e estoura esse limite. Em vez disso, cada
    perfil (chromium-desktop, chromium-movel, firefox, webkit) loga uma única vez; a
    largura e o tema mudam depois, no mesmo contexto (viewport, emulação de tema e o
    cookie `tema`), com um reload: a sessão do app vive no cookie de sessão do contexto."""
    cache: dict[str, tuple[Browser, "playwright.sync_api.BrowserContext", Page]] = {}
    yield cache
    for guardado in cache.values():
        if isinstance(guardado, Exception):
            continue  # login que falhou: contexto e navegador já foram fechados
        browser, contexto, _pagina = guardado
        contexto.close()
        browser.close()


def _cookie_tema(cenario: Cenario) -> dict:
    """O servidor lê o cookie `tema` ("escuro" ou "claro") e já envia o tema certo na página."""
    return {"name": "tema", "value": cenario.tema, "url": base_url()}


def _novo_contexto(playwright: Playwright, navegador: Browser, cenario: Cenario):
    perfil = PERFIS[cenario.perfil]
    opcoes = {
        "viewport": {"width": cenario.largura, "height": cenario.altura},
        "color_scheme": "dark" if cenario.tema == "escuro" else "light",
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
    }
    if perfil.movel:
        opcoes.update(playwright.devices["Pixel 7"])
        opcoes["viewport"] = {"width": cenario.largura, "height": cenario.altura}
        opcoes["locale"] = "pt-BR"
    contexto = navegador.new_context(**opcoes)
    contexto.set_default_timeout(20_000)
    contexto.add_cookies([_cookie_tema(cenario)])
    return contexto


def _onde(mensagem) -> str:
    """Arquivo e linha de onde veio a mensagem do console (ajuda a achar a origem de um erro)."""
    local = mensagem.location or {}
    return f"{urlparse(local.get('url', '')).path}:{local.get('lineNumber', '?')}"


def _pagina_com_console(contexto) -> Page:
    page = contexto.new_page()
    page.erros_console = []  # type: ignore[attr-defined]
    page.falhas_http = []  # type: ignore[attr-defined]
    page.on(
        "response",
        lambda r: page.falhas_http.append(f"{r.status} {urlparse(r.url).path}") if r.status >= 500 else None,
    )
    page.on("pageerror", lambda e: page.erros_console.append(f"pageerror: {e}"))
    # O WebKit, ao tirar foto de página inteira, injeta uma folha de estilo que a CSP do app (style-src 'self') recusa e
    # escreve isso no console. Conferido na tela de acesso: o erro aparece só com o screenshot, nunca pelo app.
    page.on(
        "console",
        lambda m: None if "Refused to apply a stylesheet because" in m.text else page.erros_console.append(f"console.{m.type}: {m.text[:160]} @ {_onde(m)}") if m.type == "error" else None,
    )
    return page


@pytest.fixture
def pagina_anonima(playwright_sessao, navegador, cenario):
    """Página sem login (tela de acesso)."""
    contexto = _novo_contexto(playwright_sessao, navegador, cenario)
    yield _pagina_com_console(contexto)
    contexto.close()


@pytest.fixture(scope="session")
def pagina_logada(playwright_sessao: Playwright, _contextos_autenticados, cenario: Cenario, request):
    """Página autenticada no perfil do cenário; loga por senha só na primeira vez."""
    from e2e.ajudas import aguardar_app, entrar

    cred = credenciais()
    if cred is None:
        pytest.skip("sem credenciais de teste")

    if cenario.perfil not in _contextos_autenticados:
        perfil = PERFIS[cenario.perfil]
        lancador = getattr(playwright_sessao, perfil.navegador)
        browser = lancador.launch(headless=not request.config.getoption("--visivel"))
        opcoes = {"locale": "pt-BR", "timezone_id": "America/Sao_Paulo"}
        if perfil.movel:
            opcoes.update(playwright_sessao.devices["Pixel 7"])
        contexto = browser.new_context(**opcoes)
        contexto.set_default_timeout(20_000)
        page = _pagina_com_console(contexto)
        try:
            entrar(page, *cred)  # único login por senha deste perfil na execução inteira
        except Exception as erro:
            # Cacheia a FALHA também: sem isso, cada cenário deste perfil tentaria logar
            # de novo, insistindo contra um limite de taxa do Supabase Auth já estourado
            # e piorando a situação em vez de só reportar o problema uma vez.
            contexto.close()
            browser.close()
            _contextos_autenticados[cenario.perfil] = erro
            raise
        _contextos_autenticados[cenario.perfil] = (browser, contexto, page)

    guardado = _contextos_autenticados[cenario.perfil]
    if isinstance(guardado, Exception):
        pytest.fail(f"login do perfil {cenario.perfil} já tinha falhado nesta execução: {guardado}")
    _browser, contexto, page = guardado
    contexto.add_cookies([_cookie_tema(cenario)])
    page.emulate_media(color_scheme="dark" if cenario.tema == "escuro" else "light")
    page.set_viewport_size({"width": cenario.largura, "height": cenario.altura})
    page.reload()
    aguardar_app(page)
    yield page


@pytest.fixture
def pagina_nova_sessao(playwright_sessao, navegador, cenario):
    """Página com um login próprio (para testar o logout sem derrubar a sessão compartilhada do perfil)."""
    from e2e.ajudas import entrar
    from e2e.roteiro import grava_neste_cenario

    cred = credenciais()
    if cred is None:
        pytest.skip("sem credenciais de teste")
    if not grava_neste_cenario(cenario):
        pytest.skip("um login extra por perfil basta (evita logins desnecessários)")
    contexto = _novo_contexto(playwright_sessao, navegador, cenario)
    page = _pagina_com_console(contexto)
    entrar(page, *cred)
    yield page
    contexto.close()
