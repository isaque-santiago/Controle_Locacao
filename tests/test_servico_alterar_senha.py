"""ServicoAutenticacao.alterar_senha: PUT /auth/v1/user com a anon key e o token do próprio usuário."""

import httpx
import pytest

from src.services import autenticacao
from src.services.autenticacao import SenhaNaoAlterada, ServicoAutenticacao, SessaoSupabaseInvalida


class Chamadas(list):
    """Lista das chamadas feitas ao `httpx.put`; `responder` define a resposta (ou o erro) das próximas."""


@pytest.fixture
def chamadas(monkeypatch):
    registro = Chamadas()
    monkeypatch.setattr(autenticacao, "get_supabase_url", lambda: "https://projeto.supabase.co")
    monkeypatch.setattr(autenticacao, "get_supabase_anon_key", lambda: "anon-key")

    def responder(status=200, corpo=None, erro=None):
        def put(url, headers, json, timeout):
            registro.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            if erro:
                raise erro
            return httpx.Response(status, json=corpo if corpo is not None else {}, request=httpx.Request("PUT", url))

        monkeypatch.setattr(autenticacao.httpx, "put", put)

    registro.responder = responder
    return registro


def test_envia_a_nova_senha_com_o_token_do_usuario_e_a_anon_key(chamadas):
    chamadas.responder(200, {"id": "u1"})
    ServicoAutenticacao().alterar_senha("token-do-usuario", "novaSenha2026")
    (chamada,) = chamadas
    assert chamada["url"] == "https://projeto.supabase.co/auth/v1/user"
    assert chamada["headers"] == {"apikey": "anon-key", "Authorization": "Bearer token-do-usuario"}
    assert chamada["json"] == {"password": "novaSenha2026"} and chamada["timeout"] > 0


def test_mesma_senha_da_atual_tem_mensagem_propria(chamadas):
    chamadas.responder(422, {"error_code": "same_password", "msg": "New password should be different"})
    with pytest.raises(SenhaNaoAlterada, match="diferente da atual"):
        ServicoAutenticacao().alterar_senha("t", "abc12345")


def test_outra_recusa_422_pede_outra_senha_sem_vazar_o_texto_do_servidor(chamadas):
    chamadas.responder(422, {"error_code": "weak_password", "msg": "Password is known to be weak"})
    with pytest.raises(SenhaNaoAlterada) as erro:
        ServicoAutenticacao().alterar_senha("t", "abc12345")
    assert "Escolha outra" in str(erro.value) and "weak" not in str(erro.value)


def test_corpo_que_nao_e_json_no_422_tambem_vira_mensagem_amigavel(monkeypatch, chamadas):
    monkeypatch.setattr(autenticacao.httpx, "put", lambda url, headers, json, timeout: httpx.Response(422, text="erro", request=httpx.Request("PUT", url)))
    with pytest.raises(SenhaNaoAlterada, match="Escolha outra"):
        ServicoAutenticacao().alterar_senha("t", "abc12345")


@pytest.mark.parametrize("status", [401, 403])
def test_token_recusado_pede_novo_login(chamadas, status):
    chamadas.responder(status, {})
    with pytest.raises(SessaoSupabaseInvalida):
        ServicoAutenticacao().alterar_senha("t", "abc12345")


def test_falha_do_servidor_e_da_rede_viram_mensagem_para_tentar_de_novo(chamadas):
    chamadas.responder(500, {})
    with pytest.raises(SenhaNaoAlterada, match="Tente de novo"):
        ServicoAutenticacao().alterar_senha("t", "abc12345")
    chamadas.responder(erro=httpx.ConnectTimeout("lento"))
    with pytest.raises(SenhaNaoAlterada, match="Tente de novo"):
        ServicoAutenticacao().alterar_senha("t", "abc12345")


def test_a_senha_nao_aparece_na_mensagem_de_erro(chamadas):
    chamadas.responder(500, {})
    with pytest.raises(SenhaNaoAlterada) as erro:
        ServicoAutenticacao().alterar_senha("t", "segredo-12345")
    assert "segredo-12345" not in str(erro.value)
