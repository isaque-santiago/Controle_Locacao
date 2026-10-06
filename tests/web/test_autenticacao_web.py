"""Login, logout, sessão de 30 minutos, papéis, CSRF e limite de tentativas (Fase 1)."""

import re
import threading

from starlette.testclient import TestClient

from src.web.dependencias import COOKIE_SESSAO, _garantir_tokens_validos
from tests.web.conftest import (
    CPF_LOCATARIO,
    VALIDADE_TOKEN,
    csrf_da_sessao,
    entrar,
)

MENSAGEM_CREDENCIAIS = "E-mail, CPF ou senha inválidos."
TRINTA_MINUTOS = 1800


def _cookie_de_sessao(resposta) -> str:
    return next(
        valor.lower()
        for chave, valor in resposta.headers.multi_items()
        if chave == "set-cookie" and valor.startswith(COOKIE_SESSAO + "=")
    )


def _sem_valores(html: str) -> str:
    html = re.sub(r'value="[^"]*"', "", html)
    return re.sub(r"\s+", " ", html)


# ---------- login ----------

def test_login_do_dono_abre_sessao_e_vai_ao_dashboard(cliente):
    resposta = entrar(cliente)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
    assert cliente.get("/").status_code == 200


def test_cookie_de_sessao_e_httponly_samesite_lax_e_sem_token_dentro(cliente):
    cookie = _cookie_de_sessao(entrar(cliente))
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "access-" not in cookie and "refresh-" not in cookie  # só um identificador aleatório


def test_cookie_ganha_secure_quando_a_conexao_e_https(app):
    https = TestClient(app, base_url="https://testserver", follow_redirects=False)
    assert "secure" in _cookie_de_sessao(entrar(https))


def test_locatario_entra_por_cpf_com_pontuacao_e_vai_ao_portal(cliente):
    resposta = entrar(cliente, identificador=CPF_LOCATARIO, senha="senha-locatario")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/portal"
    assert cliente.get("/portal").status_code == 200


def test_credenciais_invalidas_mostram_mensagem_unica(cliente):
    senha_errada = entrar(cliente, senha="errada")
    usuario_inexistente = entrar(cliente, identificador="ninguem@exemplo.com", senha="qualquer")
    for resposta in (senha_errada, usuario_inexistente):
        assert resposta.status_code == 401
        assert MENSAGEM_CREDENCIAIS in resposta.text
    # a resposta não revela se a conta existe: só o e-mail digitado (campo) difere
    assert _sem_valores(senha_errada.text) == _sem_valores(usuario_inexistente.text)


def test_campos_vazios_pedem_preenchimento(cliente):
    resposta = entrar(cliente, identificador="", senha="")
    assert resposta.status_code == 400
    assert "Informe o e-mail ou CPF e a senha." in resposta.text


def test_login_sem_csrf_e_recusado(cliente, servico):
    cliente.get("/login")
    resposta = cliente.post(
        "/login",
        data={"identificador": "dono@exemplo.com", "senha": "senha-dono", "csrf_token": "falso"},
    )
    assert resposta.status_code == 403
    assert servico.entradas == 0


def test_conta_sem_papel_nao_entra_e_a_sessao_do_supabase_e_revogada(cliente, servico):
    resposta = entrar(cliente, identificador="sem-papel@exemplo.com", senha="senha-x")
    assert resposta.status_code == 403
    assert servico.saidas, "o token emitido deveria ter sido revogado"
    assert cliente.get("/").status_code == 303


def test_login_nao_aceita_destino_externo(cliente):
    resposta = entrar(cliente, proximo="//malicioso.example")
    assert resposta.headers["location"] == "/"
    cliente.cookies.clear()
    resposta = entrar(cliente, proximo="/motos")
    assert resposta.headers["location"] == "/motos"


def test_pagina_de_login_com_sessao_ativa_redireciona(cliente):
    entrar(cliente)
    assert cliente.get("/login").status_code == 303


# ---------- sessão ----------

def test_f5_mantem_a_sessao(cliente):
    entrar(cliente)
    for _ in range(3):
        assert cliente.get("/").status_code == 200


def test_sessao_expira_apos_30_minutos_de_inatividade(cliente, relogio):
    entrar(cliente)
    relogio.avancar(TRINTA_MINUTOS + 1)
    resposta = cliente.get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login?expirou=1"
    assert "sessão expirou" in cliente.get("/login?expirou=1").text


def test_atividade_renova_o_prazo(cliente, relogio):
    entrar(cliente)
    relogio.avancar(20 * 60)
    assert cliente.get("/").status_code == 200
    relogio.avancar(20 * 60)  # 40 min desde o login, 20 desde a última atividade
    assert cliente.get("/").status_code == 200


def test_ate_29_minutos_a_sessao_vale(cliente, relogio):
    entrar(cliente)
    relogio.avancar(29 * 60)
    assert cliente.get("/").status_code == 200


def test_sem_login_vai_ao_login_guardando_o_destino(cliente):
    resposta = cliente.get("/motos")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login?proximo=%2Fmotos"


def test_requisicao_htmx_sem_sessao_recebe_hx_redirect(cliente):
    resposta = cliente.get("/motos", headers={"HX-Request": "true"})
    assert resposta.status_code == 401
    assert resposta.headers["HX-Redirect"].startswith("/login")


def _passar_o_tempo_com_atividade(cliente, relogio, segundos, passo=1190):
    """Avança o relógio em etapas menores que 30 min, navegando entre elas (sessão não expira)."""
    restante = segundos
    while restante > 0:
        relogio.avancar(min(passo, restante))
        restante -= passo
        ultima = cliente.get("/motos")
    return ultima


def test_access_token_perto_de_vencer_e_renovado(cliente, relogio, servico):
    entrar(cliente)
    _passar_o_tempo_com_atividade(cliente, relogio, VALIDADE_TOKEN - 30)  # dentro da margem
    assert servico.renovacoes == 1
    cliente.get("/motos")  # token novo, vale por mais uma hora
    assert servico.renovacoes == 1


def test_renovacao_recusada_encerra_a_sessao(cliente, relogio, servico):
    entrar(cliente)
    servico.renovacao_recusada = True
    resposta = _passar_o_tempo_com_atividade(cliente, relogio, VALIDADE_TOKEN - 30)
    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/login")
    assert cliente.get("/").status_code == 303


def test_requisicoes_simultaneas_renovam_o_token_uma_so_vez(app, relogio, servico):
    cliente = TestClient(app, follow_redirects=False)
    entrar(cliente)
    relogio.avancar(VALIDADE_TOKEN - 30)
    sessao = next(iter(app.state.armazem._sessoes.values()))
    sessao.ultima_atividade = relogio()
    threads = [
        threading.Thread(target=_garantir_tokens_validos, args=(app.state, sessao))
        for _ in range(8)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert servico.renovacoes == 1


# ---------- logout ----------

def test_logout_encerra_a_sessao_e_revoga_o_token(cliente, servico):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/logout", data={"csrf_token": token})
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"
    assert servico.saidas
    assert cliente.get("/").status_code == 303


def test_logout_sem_csrf_e_recusado_e_a_sessao_continua(cliente):
    entrar(cliente)
    resposta = cliente.post("/logout", data={"csrf_token": "falso"})
    assert resposta.status_code == 403
    assert cliente.get("/").status_code == 200


def test_csrf_tambem_vale_pelo_cabecalho_do_htmx(cliente):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    resposta = cliente.post("/logout", headers={"X-CSRF-Token": token})
    assert resposta.status_code == 303


def test_sessao_antiga_nao_vale_depois_do_logout(cliente):
    entrar(cliente)
    cookie_antigo = cliente.cookies.get(COOKIE_SESSAO)
    cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    cliente.cookies.set(COOKIE_SESSAO, cookie_antigo)
    assert cliente.get("/").status_code == 303


def test_cada_login_gera_um_identificador_novo(cliente):
    entrar(cliente)
    primeiro = cliente.cookies.get(COOKIE_SESSAO)
    cliente.cookies.clear()
    entrar(cliente)
    assert cliente.cookies.get(COOKIE_SESSAO) != primeiro


# ---------- papéis ----------

def test_locatario_nao_acessa_as_areas_do_dono(cliente):
    entrar(cliente, identificador=CPF_LOCATARIO, senha="senha-locatario")
    for caminho in ("/motos", "/contratos", "/configuracoes"):
        assert cliente.get(caminho).status_code == 403
    assert cliente.get("/").headers["location"] == "/portal"


def test_dono_nao_acessa_o_portal(cliente):
    entrar(cliente)
    resposta = cliente.get("/portal")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_paginas_do_menu_existem_para_o_dono(cliente):
    entrar(cliente)
    for caminho in ("/contratos", "/cobrancas", "/motos", "/clientes", "/manutencao",
                    "/documentos", "/vistorias", "/relatorios", "/configuracoes"):
        resposta = cliente.get(caminho)
        assert resposta.status_code == 200, caminho
        assert 'aria-current="page"' in resposta.text


# ---------- limite de tentativas ----------

def test_apos_5_falhas_o_login_e_bloqueado_mesmo_com_a_senha_certa(cliente, servico):
    for _ in range(5):
        assert entrar(cliente, senha="errada").status_code == 401
    entradas = servico.entradas
    bloqueada = entrar(cliente)  # senha certa
    assert bloqueada.status_code == 429
    assert "Muitas tentativas" in bloqueada.text
    assert int(bloqueada.headers["Retry-After"]) > 0
    assert servico.entradas == entradas  # nem chegou ao Supabase


def test_bloqueio_acaba_depois_de_15_minutos(cliente, relogio):
    for _ in range(5):
        entrar(cliente, senha="errada")
    relogio.avancar(15 * 60 + 1)
    assert entrar(cliente).status_code == 303


def test_bloqueio_de_um_usuario_nao_trava_os_outros(cliente):
    for _ in range(5):
        entrar(cliente, senha="errada")
    assert entrar(cliente, identificador=CPF_LOCATARIO, senha="senha-locatario").status_code == 303


# ---------- erros e cabeçalhos ----------

def test_saude_nao_exige_login(cliente):
    resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_pagina_inexistente_mostra_erro_amigavel(cliente):
    resposta = cliente.get("/nao-existe")
    assert resposta.status_code == 404
    assert "Página não encontrada" in resposta.text


def test_erro_inesperado_vira_pagina_de_erro_sem_vazar_detalhes(app, cliente):
    @app.get("/quebra")
    def quebra():
        raise RuntimeError("segredo interno")

    resposta = cliente.get("/quebra")
    assert resposta.status_code in (500, 503)
    assert "segredo interno" not in resposta.text


def test_erro_em_requisicao_htmx_vira_aviso_no_lugar_certo(app, cliente):
    @app.get("/quebra-htmx")
    def quebra():
        raise ValueError("Confira os dados informados.")

    resposta = cliente.get("/quebra-htmx", headers={"HX-Request": "true"})
    assert resposta.headers["HX-Retarget"] == "#avisos"
    assert 'role="alert"' in resposta.text


def test_cabecalhos_de_seguranca(cliente):
    resposta = cliente.get("/login")
    assert "'unsafe-inline'" not in resposta.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in resposta.headers["Content-Security-Policy"]
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in resposta.headers  # só em HTTPS


def test_hsts_so_em_https(app):
    https = TestClient(app, base_url="https://testserver")
    assert "max-age=31536000" in https.get("/login").headers["Strict-Transport-Security"]


def test_catalogo_de_componentes_so_existe_em_desenvolvimento(servico, relogio):
    from src.web.app import criar_app

    producao = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=False))
    desenvolvimento = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=True))
    assert producao.get("/componentes").status_code == 404
    assert desenvolvimento.get("/componentes").status_code == 200
