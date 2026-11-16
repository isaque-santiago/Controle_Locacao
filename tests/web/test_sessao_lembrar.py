"""Sessão longa: o cookie `lembrar` (token de renovação criptografado) refaz a sessão depois de um deploy ou reinício."""

from types import SimpleNamespace

from cryptography.fernet import Fernet
from starlette.testclient import TestClient

from src.domain.sessao_longa import INATIVIDADE_MAXIMA_SEGUNDOS, VIDA_MAXIMA_SEGUNDOS
from src.web.app import criar_app
from src.web.lacre import COOKIE_LEMBRAR, COOKIE_SESSAO, Lacre
from tests.web.conftest import VALIDADE_TOKEN, csrf_da_sessao, entrar

CHAVE = Fernet.generate_key().decode()


def _app(servico, relogio, chave=CHAVE):
    return criar_app(servico=servico, relogio=relogio, desenvolvimento=False, lacre=Lacre(chave, relogio))


def _cliente(app):
    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


def _reiniciar(servico, relogio, antigo, chave=CHAVE):
    """Servidor novo (memória vazia) e o mesmo navegador: leva os cookies do cliente antigo."""
    novo = _cliente(_app(servico, relogio, chave))
    for c in antigo.cookies.jar:
        novo.cookies.set(c.name, c.value)
    return novo


def _cookies_emitidos(resposta):
    return {c.split("=", 1)[0]: c for c in resposta.headers.get_list("set-cookie")}


def test_login_emite_cookies_com_validade_de_90_dias(servico, relogio):
    cliente = _cliente(_app(servico, relogio))
    resposta = entrar(cliente)
    emitidos = _cookies_emitidos(resposta)
    for nome in (COOKIE_SESSAO, COOKIE_LEMBRAR):
        assert f"Max-Age={INATIVIDADE_MAXIMA_SEGUNDOS}" in emitidos[nome] and "HttpOnly" in emitidos[nome]
        assert "SameSite=lax" in emitidos[nome]


def test_cookie_lembrar_nao_expoe_o_token_de_renovacao(servico, relogio):
    cliente = _cliente(_app(servico, relogio))
    entrar(cliente)
    valor = cliente.cookies.get(COOKIE_LEMBRAR)
    assert valor and "refresh-" not in valor and "dono@exemplo.com" not in valor


def test_sem_chave_so_ha_o_cookie_da_sessao_e_o_reinicio_derruba_o_login(servico, relogio):
    cliente = _cliente(_app(servico, relogio, chave=None))
    resposta = entrar(cliente)
    assert COOKIE_LEMBRAR not in _cookies_emitidos(resposta) and COOKIE_SESSAO in _cookies_emitidos(resposta)
    depois = _reiniciar(servico, relogio, cliente, chave=None)
    assert depois.get("/").status_code == 303


def test_reinicio_do_servidor_nao_derruba_o_login(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    csrf = csrf_da_sessao(antes)
    renovacoes = servico.renovacoes

    depois = _reiniciar(servico, relogio, antes)
    resposta = depois.get("/")
    assert resposta.status_code == 200
    assert servico.renovacoes == renovacoes + 1
    assert csrf_da_sessao(depois) == csrf  # páginas abertas antes do reinício continuam válidas
    emitidos = _cookies_emitidos(resposta)  # o token de renovação mudou: os cookies são reemitidos
    assert COOKIE_SESSAO in emitidos and COOKIE_LEMBRAR in emitidos
    assert depois.get("/").status_code == 200 and servico.renovacoes == renovacoes + 1  # a segunda não renova de novo


def test_pagina_de_login_depois_do_reinicio_ja_entra(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    assert _reiniciar(servico, relogio, antes).get("/login").status_code == 303


def test_cookie_adulterado_ou_de_outra_chave_nao_refaz_a_sessao(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    adulterado = _reiniciar(servico, relogio, antes)
    adulterado.cookies.set(COOKIE_LEMBRAR, antes.cookies.get(COOKIE_LEMBRAR)[:-4] + "AAAA")
    assert adulterado.get("/").status_code == 303
    outra_chave = _reiniciar(servico, relogio, antes, chave=Fernet.generate_key().decode())
    assert outra_chave.get("/").status_code == 303


def test_token_revogado_no_supabase_nao_refaz_a_sessao(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    servico.renovacao_recusada = True  # "Sair de todos os dispositivos" ou senha trocada
    depois = _reiniciar(servico, relogio, antes)
    assert depois.get("/").status_code == 303


def test_vida_maxima_vale_desde_o_login_original(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    relogio.avancar(VIDA_MAXIMA_SEGUNDOS + 60)
    assert _reiniciar(servico, relogio, antes).get("/").status_code == 303


def test_cookie_de_outro_usuario_e_recusado(servico, relogio):
    """O cookie diz u=outro, mas o Supabase devolve a conta do dono: não mistura as contas."""
    lacre = Lacre(CHAVE, relogio)
    falsa = SimpleNamespace(usuario_id="id-outro@exemplo.com", email="outro@exemplo.com", papel="dono",
                            refresh_token="refresh-x", criada_em=relogio(), csrf_token="t")
    cliente = _cliente(_app(servico, relogio))
    cliente.cookies.set(COOKIE_SESSAO, "inexistente")
    cliente.cookies.set(COOKIE_LEMBRAR, lacre.selar(falsa))
    assert cliente.get("/").status_code == 303


def test_renovacao_do_token_reemite_o_cookie_lembrar(servico, relogio):
    cliente = _cliente(_app(servico, relogio))
    entrar(cliente)
    antigo = cliente.cookies.get(COOKIE_LEMBRAR)
    relogio.avancar(VALIDADE_TOKEN + 10)
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert COOKIE_LEMBRAR in _cookies_emitidos(resposta) and cliente.cookies.get(COOKIE_LEMBRAR) != antigo


def test_cookies_sao_reemitidos_depois_de_um_dia_para_renovar_a_validade(servico, relogio):
    cliente = _cliente(_app(servico, relogio))
    entrar(cliente)
    assert COOKIE_SESSAO not in _cookies_emitidos(cliente.get("/"))
    relogio.avancar(86400 + 60)
    assert COOKIE_SESSAO in _cookies_emitidos(cliente.get("/"))


def test_logout_apaga_os_dois_cookies_e_nao_os_reemite(servico, relogio):
    cliente = _cliente(_app(servico, relogio))
    entrar(cliente)
    resposta = cliente.post("/logout", data={"csrf_token": csrf_da_sessao(cliente)})
    emitidos = _cookies_emitidos(resposta)
    assert "Max-Age=0" in emitidos[COOKIE_SESSAO] and "Max-Age=0" in emitidos[COOKIE_LEMBRAR]
    assert COOKIE_LEMBRAR not in cliente.cookies and cliente.get("/").status_code == 303


def test_requisicoes_simultaneas_refazem_uma_so_sessao(servico, relogio):
    antes = _cliente(_app(servico, relogio))
    entrar(antes)
    app = _app(servico, relogio)
    primeiro, segundo = _cliente(app), _cliente(app)
    for c in (primeiro, segundo):
        for k in antes.cookies.jar:
            c.cookies.set(k.name, k.value)
    renovacoes = servico.renovacoes
    assert primeiro.get("/").status_code == 200
    assert segundo.get("/").status_code == 200  # o mesmo token já foi usado: aproveita a sessão refeita
    assert servico.renovacoes == renovacoes + 1 and app.state.armazem.quantidade() == 1


class TestLacre:
    def _sessao(self, relogio):
        return SimpleNamespace(usuario_id="u1", email="a@b.c", papel="locatario", refresh_token="r1",
                               criada_em=relogio(), csrf_token="tk")

    def test_ida_e_volta(self, relogio):
        lacre = Lacre(CHAVE, relogio)
        dados = lacre.abrir(lacre.selar(self._sessao(relogio)))
        assert dados["u"] == "u1" and dados["r"] == "r1" and dados["p"] == "locatario" and dados["t"] == "tk"

    def test_lixo_ausente_e_chave_errada(self, relogio):
        lacre = Lacre(CHAVE, relogio)
        selo = lacre.selar(self._sessao(relogio))
        assert lacre.abrir(None) is None and lacre.abrir("") is None and lacre.abrir("lixo") is None
        assert Lacre(Fernet.generate_key().decode(), relogio).abrir(selo) is None

    def test_velho_demais(self, relogio):
        lacre = Lacre(CHAVE, relogio)
        selo = lacre.selar(self._sessao(relogio))
        relogio.avancar(VIDA_MAXIMA_SEGUNDOS + 5)
        assert lacre.abrir(selo) is None

    def test_sem_chave_ou_chave_invalida_fica_desligado(self, relogio):
        assert not Lacre(None, relogio).ativo and not Lacre("curta-demais", relogio).ativo
        assert Lacre(None, relogio).abrir("qualquer") is None
