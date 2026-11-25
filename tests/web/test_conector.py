"""Conector do claude.ai (etapa 1): OAuth com DCR e PKCE, e MCP sobre HTTP com uma ferramenta de teste."""

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from starlette.testclient import TestClient

from src.web.app import criar_app
from src.web.selos_conector import Conector
from tests.web.conftest import CPF_LOCATARIO, csrf_da_sessao, entrar

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
BASE = "https://locadora.exemplo.com"
VERIFICADOR = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
DESAFIO = base64.urlsafe_b64encode(hashlib.sha256(VERIFICADOR.encode()).digest()).rstrip(b"=").decode()
CHAVE = Fernet.generate_key().decode()


def _app(servico, relogio, chave=CHAVE, loopback=False):
    conector = Conector(chave, relogio, BASE, loopback)
    return criar_app(servico=servico, relogio=relogio, desenvolvimento=False, conector=conector)


class ExecutorFalso:
    """Imita o serviço do conector: guarda as chamadas e devolve o que o teste mandar."""

    def __init__(self):
        self.chamadas = []
        self.resposta = {"texto": "Gravado: teste.", "erro": False}
        self.levantar = None

    def executar(self, nome, argumentos):
        self.chamadas.append((nome, argumentos))
        if self.levantar:
            raise self.levantar
        return self.resposta


@pytest.fixture
def executor():
    return ExecutorFalso()


@pytest.fixture
def cli(servico, relogio):
    return TestClient(_app(servico, relogio), follow_redirects=False, raise_server_exceptions=False)


@pytest.fixture
def cli_com_banco(servico, relogio, executor):
    """O mesmo app, com as ferramentas do chat ligadas a um executor falso (no lugar do usuário de serviço do Supabase)."""
    app = criar_app(servico=servico, relogio=relogio, desenvolvimento=False, conector=Conector(CHAVE, relogio, BASE, False), servico_conector=executor)
    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


def _registrar(cli, redirect=CALLBACK):
    r = cli.post("/oauth/register", json={"redirect_uris": [redirect], "client_name": "Claude"})
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


def _consulta(client_id, **extra):
    base = {"response_type": "code", "client_id": client_id, "redirect_uri": CALLBACK, "code_challenge": DESAFIO,
            "code_challenge_method": "S256", "state": "estado-1", "scope": "propor_lancamentos offline_access"}
    return {**base, **extra}


def _autorizar(cli, client_id, decisao="autorizar", **extra):
    """O dono (já logado em `cli`) abre a tela de consentimento e responde; devolve a resposta do POST."""
    pagina = cli.get("/oauth/authorize", params=_consulta(client_id, **extra))
    assert pagina.status_code == 200, pagina.text
    campos = {**_consulta(client_id, **extra), "csrf_token": csrf_da_sessao(cli), "decisao": decisao}
    return cli.post("/oauth/authorize", data=campos)


def _codigo(resposta):
    destino = urlsplit(resposta.headers["location"])
    return parse_qs(destino.query)


def _trocar(cli, client_id, codigo, **extra):
    dados = {"grant_type": "authorization_code", "code": codigo, "client_id": client_id, "redirect_uri": CALLBACK, "code_verifier": VERIFICADOR}
    return cli.post("/oauth/token", data={**dados, **extra})


@pytest.fixture
def tokens(cli):
    """Fluxo completo: o dono entra, autoriza, e o Claude troca o código por tokens."""
    entrar(cli)
    client_id = _registrar(cli)
    resposta = _autorizar(cli, client_id)
    codigo = _codigo(resposta)["code"][0]
    token = _trocar(cli, client_id, codigo)
    assert token.status_code == 200, token.text
    return {"client_id": client_id, **token.json()}


def _mcp(cli, corpo, token=None, **cabecalhos):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **cabecalhos}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return cli.post("/mcp", content=json.dumps(corpo), headers=h)


# ---------- desligado e descoberta ----------

def test_sem_chave_o_conector_esta_desligado(servico, relogio):
    cli = TestClient(_app(servico, relogio, chave=None), follow_redirects=False)
    for metodo, caminho in [("get", "/.well-known/oauth-protected-resource"), ("get", "/.well-known/oauth-authorization-server"),
                            ("post", "/oauth/register"), ("get", "/oauth/authorize"), ("post", "/oauth/token"), ("post", "/mcp"), ("get", "/mcp")]:
        assert getattr(cli, metodo)(caminho).status_code == 404, caminho


def test_chave_invalida_desliga_o_conector(servico, relogio):
    assert not Conector("curta-demais", relogio).ativo
    cli = TestClient(_app(servico, relogio, chave="curta-demais"), follow_redirects=False)
    assert cli.post("/mcp").status_code == 404


def test_metadados_do_recurso_e_do_servidor_de_autorizacao(cli):
    recurso = cli.get("/.well-known/oauth-protected-resource").json()
    assert recurso["resource"] == f"{BASE}/mcp" and recurso["authorization_servers"] == [BASE]
    assert cli.get("/.well-known/oauth-protected-resource/mcp").json() == recurso
    servidor = cli.get("/.well-known/oauth-authorization-server").json()
    assert servidor["issuer"] == BASE and servidor["registration_endpoint"] == f"{BASE}/oauth/register"
    assert servidor["code_challenge_methods_supported"] == ["S256"] and servidor["token_endpoint_auth_methods_supported"] == ["none"]
    assert "offline_access" in servidor["scopes_supported"]


# ---------- registro ----------

def test_registro_aceita_o_callback_do_claude(cli):
    r = cli.post("/oauth/register", json={"redirect_uris": [CALLBACK], "client_name": "Claude"})
    assert r.status_code == 201 and r.json()["client_id"] and r.json()["token_endpoint_auth_method"] == "none"
    assert "no-store" in r.headers["cache-control"]


@pytest.mark.parametrize("corpo", [{"redirect_uris": ["https://evil.example/cb"]}, {"redirect_uris": []}, {}, {"redirect_uris": [CALLBACK], "token_endpoint_auth_method": "client_secret_post"}])
def test_registro_recusa_o_que_nao_e_do_claude(cli, corpo):
    r = cli.post("/oauth/register", json=corpo)
    assert r.status_code == 400 and r.json()["error"] in ("invalid_redirect_uri", "invalid_client_metadata")


def test_registro_com_corpo_que_nao_e_json(cli):
    assert cli.post("/oauth/register", content=b"x=1", headers={"Content-Type": "application/json"}).status_code == 400


def test_loopback_so_com_a_liberacao_explicita(servico, relogio):
    fechado = TestClient(_app(servico, relogio), follow_redirects=False)
    assert fechado.post("/oauth/register", json={"redirect_uris": ["http://localhost:3118/callback"]}).status_code == 400
    aberto = TestClient(_app(servico, relogio, loopback=True), follow_redirects=False)
    assert aberto.post("/oauth/register", json={"redirect_uris": ["http://localhost:3118/callback"]}).status_code == 201


def test_registro_tem_limite_de_uso(cli):
    codigos = {cli.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).status_code for _ in range(35)}
    assert 429 in codigos


# ---------- autorização ----------

def test_sem_login_manda_para_o_login_e_volta(cli):
    client_id = _registrar(cli)
    r = cli.get("/oauth/authorize", params=_consulta(client_id))
    assert r.status_code == 303 and r.headers["location"].startswith("/login?proximo=%2Foauth%2Fauthorize%3F")


def test_cliente_ou_redirect_invalidos_nao_redirecionam(cli):
    entrar(cli)
    client_id = _registrar(cli)
    assert cli.get("/oauth/authorize", params=_consulta("lixo")).status_code == 400
    r = cli.get("/oauth/authorize", params=_consulta(client_id, redirect_uri="https://evil.example/cb"))
    assert r.status_code == 400 and "location" not in r.headers


def test_so_dono_autoriza(cli):
    client_id = _registrar(cli)
    entrar(cli, identificador=CPF_LOCATARIO, senha="senha-locatario")
    assert cli.get("/oauth/authorize", params=_consulta(client_id)).status_code == 403


def test_tela_de_consentimento_explica_e_libera_so_o_destino_do_claude(cli):
    entrar(cli)
    r = cli.get("/oauth/authorize", params=_consulta(_registrar(cli)))
    assert r.status_code == 200 and "só propõe" in r.text and "https://claude.ai" in r.text and "Autorizar" in r.text
    assert "form-action 'self' https://claude.ai;" in r.headers["content-security-policy"]
    assert "form-action 'self';" in cli.get("/login").headers["content-security-policy"]  # as outras páginas não mudam


@pytest.mark.parametrize("mudanca,erro", [({"code_challenge_method": "plain"}, "invalid_request"), ({"code_challenge": ""}, "invalid_request"),
                                          ({"response_type": "token"}, "unsupported_response_type")])
def test_pedido_sem_pkce_s256_volta_com_erro(cli, mudanca, erro):
    entrar(cli)
    r = cli.get("/oauth/authorize", params=_consulta(_registrar(cli), **mudanca))
    assert r.status_code == 303 and parse_qs(urlsplit(r.headers["location"]).query)["error"] == [erro]


def test_negar_volta_com_access_denied_e_o_state(cli):
    entrar(cli)
    r = _autorizar(cli, _registrar(cli), decisao="negar")
    consulta = _codigo(r)
    assert r.status_code == 303 and r.headers["location"].startswith(CALLBACK) and consulta["error"] == ["access_denied"] and consulta["state"] == ["estado-1"]


def test_confirmar_sem_csrf_e_recusado(cli):
    entrar(cli)
    client_id = _registrar(cli)
    r = cli.post("/oauth/authorize", data={**_consulta(client_id), "decisao": "autorizar"})
    assert r.status_code == 403


def test_confirmar_reconfere_os_campos_escondidos(cli):
    entrar(cli)
    client_id = _registrar(cli)
    r = cli.post("/oauth/authorize", data={**_consulta(client_id, redirect_uri="https://evil.example/cb"), "csrf_token": csrf_da_sessao(cli), "decisao": "autorizar"})
    assert r.status_code == 400 and "location" not in r.headers


# ---------- tokens ----------

def test_fluxo_completo_entrega_tokens(tokens):
    assert tokens["token_type"] == "Bearer" and tokens["expires_in"] == 3600 and tokens["access_token"] and tokens["refresh_token"]
    assert tokens["scope"] == "propor_lancamentos offline_access"


def test_codigo_vale_uma_vez(cli):
    entrar(cli)
    client_id = _registrar(cli)
    codigo = _codigo(_autorizar(cli, client_id))["code"][0]
    assert _trocar(cli, client_id, codigo).status_code == 200
    r = _trocar(cli, client_id, codigo)
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


@pytest.mark.parametrize("troca", [{"code_verifier": "x" * 43}, {"redirect_uri": "https://claude.com/api/mcp/auth_callback"}, {"code": "lixo"}])
def test_troca_recusada(cli, troca):
    entrar(cli)
    client_id = _registrar(cli)
    codigo = _codigo(_autorizar(cli, client_id))["code"][0]
    r = _trocar(cli, client_id, codigo, **troca)
    assert r.status_code == 400 and r.json()["error"] == "invalid_grant"


def test_codigo_de_outro_cliente_nao_vale(cli):
    entrar(cli)
    a, b = _registrar(cli), _registrar(cli)
    codigo = _codigo(_autorizar(cli, a))["code"][0]
    assert _trocar(cli, b, codigo).json()["error"] == "invalid_grant"


def test_codigo_vence_em_dois_minutos(cli, relogio):
    entrar(cli)
    client_id = _registrar(cli)
    codigo = _codigo(_autorizar(cli, client_id))["code"][0]
    relogio.avancar(121)
    assert _trocar(cli, client_id, codigo).json()["error"] == "invalid_grant"


def test_token_exige_form_urlencoded_e_cliente_conhecido(cli):
    assert cli.post("/oauth/token", json={"grant_type": "refresh_token"}).json()["error"] == "invalid_request"
    r = cli.post("/oauth/token", data={"grant_type": "refresh_token", "client_id": "lixo"})
    assert r.status_code == 401 and r.json()["error"] == "invalid_client"


def test_tipo_de_concessao_desconhecido(cli):
    client_id = _registrar(cli)
    assert cli.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": client_id}).json()["error"] == "unsupported_grant_type"


def test_renovacao_gira_o_token_e_o_antigo_deixa_de_valer(cli, tokens):
    dados = {"grant_type": "refresh_token", "client_id": tokens["client_id"], "refresh_token": tokens["refresh_token"]}
    novo = cli.post("/oauth/token", data=dados)
    assert novo.status_code == 200 and novo.json()["refresh_token"] != tokens["refresh_token"]
    reuso = cli.post("/oauth/token", data=dados)
    assert reuso.status_code == 400 and reuso.json()["error"] == "invalid_grant"
    assert _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, novo.json()["access_token"]).status_code == 200


def test_token_de_acesso_nao_serve_como_renovacao(cli, tokens):
    r = cli.post("/oauth/token", data={"grant_type": "refresh_token", "client_id": tokens["client_id"], "refresh_token": tokens["access_token"]})
    assert r.json()["error"] == "invalid_grant"


def test_tentativas_erradas_no_token_sao_limitadas(cli):
    client_id = _registrar(cli)
    codigos = {cli.post("/oauth/token", data={"grant_type": "authorization_code", "client_id": client_id, "code": "x"}).status_code for _ in range(35)}
    assert 429 in codigos


# ---------- MCP ----------

def test_mcp_sem_token_responde_401_com_o_endereco_dos_metadados(cli):
    r = _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401
    assert f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"' in r.headers["www-authenticate"]


@pytest.mark.parametrize("token", ["lixo", "Bearer"])
def test_mcp_com_token_invalido(cli, token):
    r = _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token)
    assert r.status_code == 401 and 'error="invalid_token"' in r.headers["www-authenticate"]


def test_token_de_renovacao_nao_abre_o_mcp(cli, tokens):
    assert _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, tokens["refresh_token"]).status_code == 401


def test_token_de_acesso_vence_em_uma_hora(cli, tokens, relogio):
    relogio.avancar(3601)
    assert _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, tokens["access_token"]).status_code == 401


def test_mcp_initialize_listar_e_chamar_a_ferramenta(cli, tokens):
    t = tokens["access_token"]
    ini = _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, t).json()
    assert ini["result"]["protocolVersion"] == "2025-06-18" and ini["result"]["serverInfo"]["name"] == "LA Locadora"
    assert _mcp(cli, {"jsonrpc": "2.0", "method": "notifications/initialized"}, t).status_code == 202
    lista = _mcp(cli, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, t).json()["result"]["tools"]
    assert lista[0]["name"] == "ping" and lista[0]["annotations"]["readOnlyHint"] is True and "registrar_pagamento" in [f["name"] for f in lista]
    chamada = _mcp(cli, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}, t).json()
    assert "pong" in chamada["result"]["content"][0]["text"]


def test_mcp_nao_tem_ferramenta_que_apague_edite_ou_aprove(cli, tokens):
    t = tokens["access_token"]
    for nome in ("aprovar_pendencia", "apagar_pagamento", "editar_cliente", "desfazer_lancamento", "ler_tabela"):
        r = _mcp(cli, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": nome, "arguments": {}}}, t).json()
        assert r["error"]["code"] == -32602, nome


def test_mcp_lote_e_erros_de_formato(cli, tokens):
    t = tokens["access_token"]
    lote = _mcp(cli, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "method": "notifications/initialized"}], t).json()
    assert lote == [{"jsonrpc": "2.0", "id": 1, "result": {}}]
    assert _mcp(cli, [], t).status_code == 400
    ruim = cli.post("/mcp", content=b"{nao e json", headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"})
    assert ruim.status_code == 400 and ruim.json()["error"]["code"] == -32700


def test_mcp_so_aceita_post(cli, tokens):
    assert cli.get("/mcp").status_code == 405 and cli.get("/mcp").headers["allow"] == "POST"
    assert cli.delete("/mcp").status_code == 405


def test_mcp_recusa_origem_de_terceiros(cli, tokens):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert _mcp(cli, msg, tokens["access_token"], Origin="https://evil.example").status_code == 403
    assert _mcp(cli, msg, tokens["access_token"], Origin="https://claude.ai").status_code == 200


def test_trocar_a_chave_revoga_todos_os_tokens(servico, relogio, tokens, cli):
    outra = TestClient(_app(servico, relogio, chave=Fernet.generate_key().decode()), follow_redirects=False)
    assert _mcp(outra, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, tokens["access_token"]).status_code == 401


def test_nada_do_conector_exige_cookie_de_sessao(servico, relogio, tokens):
    """O Claude fala com o servidor por token, sem cookies: o MCP funciona num cliente sem sessão nenhuma."""
    sem_cookie = TestClient(_app(servico, relogio), follow_redirects=False)
    # outra instância de app tem a mesma chave? não: cada _app() gera o Conector com a CHAVE do módulo, então os tokens valem.
    assert _mcp(sem_cookie, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, tokens["access_token"]).status_code == 200


# ---------- ferramentas do chat (etapa 4) ----------

def _tokens_de(cliente):
    entrar(cliente)
    client_id = _registrar(cliente)
    codigo = _codigo(_autorizar(cliente, client_id))["code"][0]
    return _trocar(cliente, client_id, codigo).json()


def _chamar_ferramenta(cliente, token, nome, argumentos, id_=1):
    return _mcp(cliente, {"jsonrpc": "2.0", "id": id_, "method": "tools/call", "params": {"name": nome, "arguments": argumentos}}, token).json()


def test_ferramenta_executa_pelo_servico_depois_do_login(cli_com_banco, executor):
    token = _tokens_de(cli_com_banco)["access_token"]
    r = _chamar_ferramenta(cli_com_banco, token, "registrar_pagamento", {"cobranca_id": "c", "valor": 275})["result"]
    assert r == {"content": [{"type": "text", "text": "Gravado: teste."}], "isError": False}
    assert executor.chamadas == [("registrar_pagamento", {"cobranca_id": "c", "valor": 275})]


def test_erro_do_servico_chega_como_isError(cli_com_banco, executor):
    executor.resposta = {"texto": "NÃO GRAVADO (duvida): Pagamento parcial.", "erro": True}
    token = _tokens_de(cli_com_banco)["access_token"]
    r = _chamar_ferramenta(cli_com_banco, token, "registrar_pagamento", {"cobranca_id": "c", "valor": 100})["result"]
    assert r["isError"] is True and r["content"][0]["text"].startswith("NÃO GRAVADO")


def test_sem_token_nenhuma_ferramenta_executa(cli_com_banco, executor):
    r = _mcp(cli_com_banco, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "registrar_pagamento", "arguments": {"cobranca_id": "c", "valor": 1}}})
    assert r.status_code == 401 and executor.chamadas == []
    r = _mcp(cli_com_banco, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "cadastrar_cliente", "arguments": {"nome": "A B"}}}, "lixo")
    assert r.status_code == 401 and executor.chamadas == []


def test_argumentos_errados_nao_chegam_ao_servico(cli_com_banco, executor):
    token = _tokens_de(cli_com_banco)["access_token"]
    r = _chamar_ferramenta(cli_com_banco, token, "registrar_pagamento", {"valor": 1})["result"]
    assert r["isError"] and "Faltam argumentos obrigatórios: cobranca_id" in r["content"][0]["text"]
    r = _chamar_ferramenta(cli_com_banco, token, "registrar_pagamento", {"cobranca_id": "c", "valor": 1, "status": "paga"})["result"]
    assert r["isError"] and "Argumento desconhecido: status" in r["content"][0]["text"]
    assert executor.chamadas == []


def test_falha_inesperada_do_servico_vira_erro_generico_sem_detalhe(cli_com_banco, executor):
    executor.levantar = RuntimeError("senha-do-banco-123")
    token = _tokens_de(cli_com_banco)["access_token"]
    resposta = _mcp(cli_com_banco, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "buscar_veiculos", "arguments": {"busca": "ABC"}}}, token)
    assert resposta.status_code == 200 and "senha-do-banco-123" not in resposta.text
    assert resposta.json()["result"]["isError"] is True and "Nada foi gravado" in resposta.json()["result"]["content"][0]["text"]


def test_lote_com_varias_ferramentas(cli_com_banco, executor):
    token = _tokens_de(cli_com_banco)["access_token"]
    lote = [{"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "buscar_veiculos", "arguments": {"busca": f"ABC{i}"}}} for i in (1, 2)]
    respostas = _mcp(cli_com_banco, lote, token).json()
    assert [r["id"] for r in respostas] == [1, 2] and [c[1]["busca"] for c in executor.chamadas] == ["ABC1", "ABC2"]


def test_sem_servico_do_banco_so_o_ping_funciona(cli, tokens):
    t = tokens["access_token"]
    r = _chamar_ferramenta(cli, t, "registrar_pagamento", {"cobranca_id": "c", "valor": 1})["result"]
    assert r["isError"] and "não está ligado ao banco" in r["content"][0]["text"]
    assert "pong" in _chamar_ferramenta(cli, t, "ping", {})["result"]["content"][0]["text"]


def test_todas_as_ferramentas_aparecem_no_tools_list(cli_com_banco):
    token = _tokens_de(cli_com_banco)["access_token"]
    lista = _mcp(cli_com_banco, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token).json()["result"]["tools"]
    nomes = {f["name"] for f in lista}
    assert {"registrar_pagamento", "registrar_despesa", "cadastrar_cliente", "cadastrar_veiculo", "consultar_cobrancas_abertas",
            "buscar_veiculos", "listar_ultimos_lancamentos", "ping", "entregar_lote_historico", "resumo_do_historico",
            "listar_historico_a_conferir"} == nomes
