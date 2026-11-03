"""Unidades do app web: armazém de sessões, limitador, apresentação, serviço e cliente por requisição."""

from unittest.mock import MagicMock, patch

import pytest
from supabase_auth.errors import AuthApiError

from src import db
from src.services import autenticacao as servico_mod
from src.services.autenticacao import (
    CredenciaisInvalidas,
    ServicoAutenticacao,
    SessaoSupabaseInvalida,
)
from src.web.apresentacao import destino_seguro, nome_de_exibicao, tema_do_cookie
from src.web.limitador import LimitadorTentativas
from src.web.navegacao import item_ativo, mais_esta_ativo
from src.web.sessao import ArmazemSessoes
from tests.web.conftest import Relogio


def _criar(armazem: ArmazemSessoes):
    return armazem.criar(
        usuario_id="u1", email="a@b.com", papel="dono",
        access_token="a", refresh_token="r", expira_em=9e9,
    )


# ---------- armazém de sessões ----------

def test_sessao_valida_e_renovada_a_cada_uso():
    relogio = Relogio()
    armazem = ArmazemSessoes(limite_inatividade=100, relogio=relogio)
    sessao = _criar(armazem)
    relogio.avancar(90)
    assert armazem.obter(sessao.id) is sessao
    relogio.avancar(90)
    assert armazem.obter(sessao.id) is sessao  # 90 s desde o último uso


def test_sessao_expira_pelo_limite_de_inatividade():
    relogio = Relogio()
    armazem = ArmazemSessoes(limite_inatividade=100, relogio=relogio)
    sessao = _criar(armazem)
    relogio.avancar(101)
    assert armazem.obter(sessao.id) is None
    assert armazem.quantidade() == 0


def test_identificadores_sao_unicos_e_longos():
    armazem = ArmazemSessoes()
    ids = {_criar(armazem).id for _ in range(50)}
    assert len(ids) == 50
    assert all(len(i) >= 40 for i in ids)


def test_criar_limpa_sessoes_vencidas():
    relogio = Relogio()
    armazem = ArmazemSessoes(limite_inatividade=10, relogio=relogio)
    _criar(armazem)
    relogio.avancar(11)
    _criar(armazem)
    assert armazem.quantidade() == 1


def test_obter_sem_identificador_ou_desconhecido():
    armazem = ArmazemSessoes()
    assert armazem.obter(None) is None
    assert armazem.obter("inexistente") is None
    assert armazem.encerrar("inexistente") is None


def test_csrf_da_sessao_e_diferente_por_sessao():
    armazem = ArmazemSessoes()
    assert _criar(armazem).csrf_token != _criar(armazem).csrf_token


# ---------- limitador ----------

def test_limitador_bloqueia_apos_o_maximo_e_libera_pela_janela():
    relogio = Relogio()
    limitador = LimitadorTentativas(maximo=3, janela=60, relogio=relogio)
    for _ in range(3):
        assert limitador.segundos_de_bloqueio("x") == 0
        limitador.registrar_falha("x")
    assert 0 < limitador.segundos_de_bloqueio("x") <= 61
    relogio.avancar(61)
    assert limitador.segundos_de_bloqueio("x") == 0


def test_limitador_separa_chaves_e_limpa():
    limitador = LimitadorTentativas(maximo=1, janela=60, relogio=Relogio())
    limitador.registrar_falha("a")
    assert limitador.segundos_de_bloqueio("a") > 0
    assert limitador.segundos_de_bloqueio("b") == 0
    limitador.limpar("a")
    assert limitador.segundos_de_bloqueio("a") == 0


# ---------- apresentação e navegação ----------

@pytest.mark.parametrize(
    "destino, esperado",
    [
        ("/motos", "/motos"),
        ("/motos?pagina=2", "/motos?pagina=2"),
        ("//evil.com", "/"),
        ("https://evil.com", "/"),
        ("/\\evil.com", "/"),
        ("/a\nSet-Cookie: x=1", "/"),
        ("", "/"),
        (None, "/"),
        ("motos", "/"),
    ],
)
def test_destino_seguro(destino, esperado):
    assert destino_seguro(destino) == esperado


def test_nome_de_exibicao_nao_mostra_o_cpf_do_locatario():
    assert nome_de_exibicao("12345678909@portal.example.com") == "Locatário"
    assert nome_de_exibicao("ricardo.menezes@exemplo.com") == "Ricardo Menezes"


def test_tema_do_cookie_so_aceita_valores_conhecidos():
    assert tema_do_cookie("escuro") == "escuro"
    assert tema_do_cookie("claro") == "claro"
    assert tema_do_cookie("<script>") == ""
    assert tema_do_cookie(None) == ""


def test_item_ativo_da_navegacao():
    assert item_ativo("/").chave == "dashboard"
    assert item_ativo("/motos").chave == "motos"
    assert item_ativo("/motos/123").chave == "motos"  # a ficha ativa o item da lista
    assert item_ativo("/motosx") is None
    assert item_ativo("/portal") is None
    assert mais_esta_ativo("/clientes") is True
    assert mais_esta_ativo("/motos") is False


# ---------- serviço de autenticação ----------

def _resposta_supabase(expires_at=5000):
    sessao = MagicMock(access_token="at", refresh_token="rt", expires_at=expires_at)
    usuario = MagicMock(id="uid", email="dono@exemplo.com")
    return MagicMock(session=sessao, user=usuario)


def test_servico_entra_com_cpf_convertido_em_email():
    cliente = MagicMock()
    cliente.auth.sign_in_with_password.return_value = _resposta_supabase()
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        tokens = ServicoAutenticacao().entrar("123.456.789-09", "senha")
    enviado = cliente.auth.sign_in_with_password.call_args.args[0]
    assert enviado["email"] == "12345678909@portal.example.com"
    assert (tokens.access_token, tokens.refresh_token, tokens.expira_em) == ("at", "rt", 5000.0)


@pytest.mark.parametrize("status", [400, 401, 422])
def test_servico_traduz_credencial_recusada(status):
    cliente = MagicMock()
    cliente.auth.sign_in_with_password.side_effect = AuthApiError("recusado", status, None)
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        with pytest.raises(CredenciaisInvalidas):
            ServicoAutenticacao().entrar("dono@exemplo.com", "x")


def test_servico_nao_confunde_falha_do_supabase_com_senha_errada():
    cliente = MagicMock()
    cliente.auth.sign_in_with_password.side_effect = AuthApiError("fora do ar", 503, None)
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        with pytest.raises(AuthApiError):
            ServicoAutenticacao().entrar("dono@exemplo.com", "x")


def test_servico_renova_e_traduz_refresh_invalido():
    cliente = MagicMock()
    cliente.auth.refresh_session.return_value = _resposta_supabase()
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        assert ServicoAutenticacao().renovar("rt").access_token == "at"
    cliente.auth.refresh_session.side_effect = AuthApiError("usado", 400, None)
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        with pytest.raises(SessaoSupabaseInvalida):
            ServicoAutenticacao().renovar("rt")


def test_servico_sair_revoga_so_esta_sessao_e_ignora_falhas():
    cliente = MagicMock()
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        ServicoAutenticacao().sair("token")
    cliente.auth.admin.sign_out.assert_called_once_with("token", "local")
    cliente.auth.admin.sign_out.side_effect = RuntimeError("rede")
    with patch.object(db, "criar_cliente_anonimo", return_value=cliente):
        ServicoAutenticacao().sair("token")  # não levanta


def test_papel_usa_o_cliente_do_usuario_nos_repositorios():
    cliente = MagicMock()
    visto = {}

    def meu_papel():
        visto["cliente"] = db.get_client()
        return "dono"

    with patch.object(servico_mod.portal_locatario, "meu_papel", meu_papel):
        assert ServicoAutenticacao().papel(cliente) == "dono"
    assert visto["cliente"] is cliente


# ---------- cliente por requisição (src/db.py) ----------

def test_get_client_prefere_o_cliente_da_requisicao():
    cliente = MagicMock()
    with db.usar_cliente(cliente):
        assert db.get_client() is cliente


def test_cliente_da_requisicao_nao_vaza_para_fora_do_bloco():
    with db.usar_cliente(MagicMock()):
        pass
    assert db._CLIENTE_REQUISICAO.get() is None


def test_cliente_autenticado_leva_o_token_do_usuario_e_usa_a_anon_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://projeto.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-publica")
    capturado = {}

    def falso_create_client(url, chave, opcoes):
        capturado.update(url=url, chave=chave, opcoes=opcoes)
        return MagicMock()

    with patch.object(db, "create_client", falso_create_client):
        db.criar_cliente_autenticado("jwt-do-usuario")
    assert capturado["chave"] == "anon-publica"
    assert capturado["opcoes"].headers["Authorization"] == "Bearer jwt-do-usuario"
    assert capturado["opcoes"].auto_refresh_token is False
