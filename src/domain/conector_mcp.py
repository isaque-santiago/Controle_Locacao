"""Protocolo MCP do conector (JSON-RPC 2.0 sobre HTTP): só ferramentas, sem estado.

Etapa 1 da seção 24 do plano: uma única ferramenta de teste (`ping`), que não lê nem grava nada. As ferramentas de verdade
(propor pagamento e despesa) entram nas etapas seguintes e **nunca** aprovam, editam ou apagam: o chat só propõe."""

PROTOCOLOS_SUPORTADOS = ("2025-11-25", "2025-06-18", "2025-03-26")
NOME_DO_SERVIDOR = "LA Locadora"
VERSAO_DO_SERVIDOR = "0.1.0"

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602

FERRAMENTAS = (
    {
        "name": "ping",
        "title": "Testar a conexão com o sistema",
        "description": "Confere se o conector está ativo e autorizado. Não lê nem grava dados do sistema.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
)


def escolher_protocolo(pedido) -> str:
    """Versão pedida pelo cliente, se o servidor a conhece; senão, a mais nova que ele suporta."""
    return pedido if pedido in PROTOCOLOS_SUPORTADOS else PROTOCOLOS_SUPORTADOS[0]


def _erro(id_, codigo: int, mensagem: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": mensagem}}


def _resultado(id_, resultado: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": resultado}


def _chamar(nome, argumentos) -> dict:
    if nome == "ping":
        return {"content": [{"type": "text", "text": "pong: o conector da LA Locadora está ativo e autorizado."}], "isError": False}
    raise KeyError(nome)


def responder(mensagem) -> dict | None:
    """Resposta JSON-RPC para uma mensagem, ou None quando é notificação ou resposta (o servidor não responde nada)."""
    if not isinstance(mensagem, dict) or mensagem.get("jsonrpc") != "2.0":
        return _erro(None, INVALID_REQUEST, "Mensagem JSON-RPC inválida.")
    metodo = mensagem.get("method")
    if "id" not in mensagem:
        return None  # notificação (ex.: notifications/initialized) ou resposta
    id_ = mensagem["id"]
    if isinstance(id_, bool) or not isinstance(id_, (str, int)):
        return _erro(None, INVALID_REQUEST, "id inválido.")
    if not isinstance(metodo, str):
        return _erro(id_, INVALID_REQUEST, "Método ausente.")
    params = mensagem.get("params") or {}
    if not isinstance(params, dict):
        return _erro(id_, INVALID_PARAMS, "params precisa ser um objeto.")

    if metodo == "initialize":
        return _resultado(id_, {
            "protocolVersion": escolher_protocolo(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": NOME_DO_SERVIDOR, "version": VERSAO_DO_SERVIDOR},
        })
    if metodo == "ping":
        return _resultado(id_, {})
    if metodo == "tools/list":
        return _resultado(id_, {"tools": list(FERRAMENTAS)})
    if metodo == "tools/call":
        try:
            return _resultado(id_, _chamar(params.get("name"), params.get("arguments") or {}))
        except KeyError:
            return _erro(id_, INVALID_PARAMS, "Ferramenta desconhecida.")
    return _erro(id_, METHOD_NOT_FOUND, "Método não suportado.")
