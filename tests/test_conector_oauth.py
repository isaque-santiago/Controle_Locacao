"""Testes de src/domain/conector_oauth.py e src/domain/conector_mcp.py (regras puras do conector)."""

import pytest

from src.domain.conector_mcp import FERRAMENTAS, PROTOCOLOS_SUPORTADOS, escolher_protocolo, responder
from src.domain.conector_oauth import (
    ErroOAuth,
    desafio_pkce_valido,
    escopos_pedidos,
    origem_da_url,
    pkce_confere,
    redirect_permitido,
    url_com_parametros,
    validar_registro,
)

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
# Vetor do apêndice B da RFC 7636.
VERIFICADOR = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
DESAFIO = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class TestRedirect:
    def test_callback_do_claude(self):
        assert redirect_permitido(CALLBACK) and redirect_permitido("https://claude.com/api/mcp/auth_callback")

    @pytest.mark.parametrize("uri", ["", None, "https://evil.example/cb", CALLBACK + "/x", "http://claude.ai/api/mcp/auth_callback",
                                     "https://claude.ai.evil.com/api/mcp/auth_callback", "http://localhost:3118/callback"])
    def test_recusa_o_resto(self, uri):
        assert not redirect_permitido(uri)

    def test_loopback_so_quando_liberado(self):
        assert redirect_permitido("http://localhost:3118/callback", permitir_loopback=True)
        assert redirect_permitido("http://127.0.0.1:6274/oauth/callback", permitir_loopback=True)
        assert not redirect_permitido("http://evil.example:3118/callback", permitir_loopback=True)
        assert not redirect_permitido("https://localhost/callback", permitir_loopback=True)


class TestRegistro:
    def test_registro_valido(self):
        r = validar_registro({"redirect_uris": [CALLBACK, CALLBACK], "client_name": "  Claude  "})
        assert r == {"nome": "Claude", "redirect_uris": [CALLBACK]}

    @pytest.mark.parametrize("corpo,codigo", [
        (None, "invalid_client_metadata"), ([], "invalid_client_metadata"),
        ({}, "invalid_redirect_uri"), ({"redirect_uris": []}, "invalid_redirect_uri"),
        ({"redirect_uris": "x"}, "invalid_redirect_uri"), ({"redirect_uris": [1]}, "invalid_redirect_uri"),
        ({"redirect_uris": ["https://evil.example/cb"]}, "invalid_redirect_uri"),
        ({"redirect_uris": [CALLBACK] * 6}, "invalid_redirect_uri"),
        ({"redirect_uris": [CALLBACK], "token_endpoint_auth_method": "client_secret_basic"}, "invalid_client_metadata"),
    ])
    def test_recusa(self, corpo, codigo):
        with pytest.raises(ErroOAuth) as erro:
            validar_registro(corpo)
        assert erro.value.codigo == codigo

    def test_nome_vazio_vira_claude_e_e_cortado(self):
        assert validar_registro({"redirect_uris": [CALLBACK], "client_name": "  "})["nome"] == "Claude"
        assert len(validar_registro({"redirect_uris": [CALLBACK], "client_name": "x" * 500})["nome"]) == 80


class TestPkce:
    def test_vetor_da_rfc(self):
        assert pkce_confere(VERIFICADOR, DESAFIO)

    @pytest.mark.parametrize("verificador,desafio", [(VERIFICADOR, "outro"), ("curto", DESAFIO), ("", DESAFIO), (VERIFICADOR, ""), (None, None)])
    def test_recusa(self, verificador, desafio):
        assert not pkce_confere(verificador, desafio)

    def test_desafio_exige_s256(self):
        assert desafio_pkce_valido(DESAFIO, "S256")
        assert not desafio_pkce_valido(DESAFIO, "plain") and not desafio_pkce_valido("curto", "S256") and not desafio_pkce_valido(None, "S256")


def test_escopos():
    assert escopos_pedidos("offline_access propor_lancamentos offline_access x") == "offline_access propor_lancamentos"
    assert escopos_pedidos("admin") == "propor_lancamentos" and escopos_pedidos(None) == "propor_lancamentos"


def test_url_com_parametros():
    assert url_com_parametros(CALLBACK, code="abc", state="s 1", vazio=None) == CALLBACK + "?code=abc&state=s+1"
    assert url_com_parametros(CALLBACK + "?a=1", b="2") == CALLBACK + "?a=1&b=2"
    assert origem_da_url(CALLBACK) == "https://claude.ai"


class TestMcp:
    def _req(self, metodo, id_=1, **params):
        return {"jsonrpc": "2.0", "id": id_, "method": metodo, **({"params": params} if params else {})}

    def test_initialize_negocia_o_protocolo(self):
        r = responder(self._req("initialize", protocolVersion="2025-06-18"))
        assert r["result"]["protocolVersion"] == "2025-06-18" and r["result"]["serverInfo"]["name"] == "LA Locadora"
        assert r["result"]["capabilities"] == {"tools": {"listChanged": False}}
        assert responder(self._req("initialize", protocolVersion="1999-01-01"))["result"]["protocolVersion"] == PROTOCOLOS_SUPORTADOS[0]
        assert escolher_protocolo(None) == PROTOCOLOS_SUPORTADOS[0]

    def test_notificacao_nao_tem_resposta(self):
        assert responder({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    def test_ferramentas_so_de_leitura_nesta_etapa(self):
        r = responder(self._req("tools/list"))
        nomes = [f["name"] for f in r["result"]["tools"]]
        assert nomes == ["ping"] and all(f["annotations"]["readOnlyHint"] for f in FERRAMENTAS)

    def test_chamar_ping(self):
        r = responder(self._req("tools/call", name="ping"))
        assert r["result"]["isError"] is False and "pong" in r["result"]["content"][0]["text"]

    @pytest.mark.parametrize("mensagem,codigo", [
        ({"jsonrpc": "2.0", "id": 1, "method": "nao/existe"}, -32601),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "apagar_tudo"}}, -32602),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "x"}, -32602),
        ({"jsonrpc": "2.0", "id": 1}, -32600),
        ({"jsonrpc": "1.0", "id": 1, "method": "ping"}, -32600),
        ({"jsonrpc": "2.0", "id": True, "method": "ping"}, -32600),
        ("texto", -32600),
    ])
    def test_erros(self, mensagem, codigo):
        assert responder(mensagem)["error"]["code"] == codigo

    def test_ping_do_protocolo(self):
        assert responder(self._req("ping")) == {"jsonrpc": "2.0", "id": 1, "result": {}}
