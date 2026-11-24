"""Protocolo MCP do conector (JSON-RPC 2.0 sobre HTTP) e a lista de ferramentas do chat (seção 24 do plano).

Modelo de 24/11/2026: o chat **grava direto** o que está limpo (cadastro de cliente e de veículo, pagamento e despesa sem aviso e
abaixo do teto) e, na dúvida, a ferramenta **não grava** e devolve o motivo para o Claude perguntar ao usuário na conversa. Editar,
apagar e aprovar **não existem** como ferramentas. Este módulo é puro: descreve as ferramentas, confere os argumentos e monta as
respostas; quem executa uma ferramenta (`executar`) é o serviço `src/services/conector.py`, injetado por quem chama `responder`."""

PROTOCOLOS_SUPORTADOS = ("2025-11-25", "2025-06-18", "2025-03-26")
NOME_DO_SERVIDOR = "LA Locadora"
VERSAO_DO_SERVIDOR = "0.2.0"

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602

_LEITURA = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
# Grava, mas nunca apaga nem altera o que já existe; repetir com a mesma `chave_operacao` não duplica.
_GRAVA = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

_TEXTO = {"type": "string"}
_CHAVE = {"type": "string", "description": "Opcional. Chave para repetir o envio sem duplicar; se faltar, o sistema cria uma a partir dos dados. "
                                          "Se o dono desfez o lançamento e pedir para registrar de novo, use uma chave nova."}
_TRECHO = {"type": "string", "description": "Opcional. Trecho curto da conversa que originou o lançamento (fica no histórico)."}
_AVISO_DUVIDA = (" Se a resposta disser que NÃO gravou, explique o motivo ao usuário, pergunte o que falta na conversa e chame de novo "
                 "com a resposta; não invente dados.")


def _objeto(propriedades: dict, obrigatorios: tuple = ()) -> dict:
    return {"type": "object", "properties": propriedades, "required": list(obrigatorios), "additionalProperties": False}


FERRAMENTAS = (
    {
        "name": "ping", "title": "Testar a conexão com o sistema",
        "description": "Confere se o conector está ativo e autorizado. Não lê nem grava dados do sistema.",
        "inputSchema": _objeto({}), "annotations": _LEITURA,
    },
    {
        "name": "consultar_cobrancas_abertas", "title": "Consultar cobranças em aberto",
        "description": "Busca as cobranças em aberto de um cliente por nome, CPF parcial (4 dígitos ou mais) e/ou placa; pode combinar. "
                       "Devolve o id de cada cobrança, o vencimento, o valor, o saldo, o nome do cliente, os 4 últimos dígitos do CPF e a placa. "
                       "Use ANTES de registrar_pagamento para obter o cobranca_id. Se aparecer mais de um cliente, pergunte qual é.",
        "inputSchema": _objeto({"busca": {"type": "string", "description": "Nome, CPF parcial e/ou placa (ex.: 'Jhonatan ABC1D23')."}}, ("busca",)),
        "annotations": _LEITURA,
    },
    {
        "name": "buscar_veiculos", "title": "Buscar veículos",
        "description": "Busca veículos por placa ou modelo e devolve o id (moto_id), a placa e a descrição. Use para obter o moto_id de uma despesa.",
        "inputSchema": _objeto({"busca": {"type": "string", "description": "Placa ou parte do modelo."}}, ("busca",)), "annotations": _LEITURA,
    },
    {
        "name": "registrar_pagamento", "title": "Registrar pagamento",
        "description": "Registra o pagamento de uma cobrança. Grava na hora se a cobrança foi identificada, o valor é igual ao saldo, não há "
                       "pagamento igual e a data não é futura (até R$ 10.000,00). Pagamento parcial, valor acima do saldo, cobrança paga ou "
                       "cancelada e valores acima do teto NÃO são gravados: a resposta explica o motivo." + _AVISO_DUVIDA,
        "inputSchema": _objeto({
            "cobranca_id": {"type": "string", "description": "Id da cobrança, obtido em consultar_cobrancas_abertas."},
            "valor": {"type": ["number", "string"], "description": "Valor pago em reais (ex.: 275 ou '275,00')."},
            "data_pagamento": {"type": "string", "description": "Data do pagamento (aaaa-mm-dd ou dd/mm/aaaa). Padrão: hoje."},
            "forma": {"type": "string", "enum": ["pix", "dinheiro", "cartao", "transferencia", "outro"], "description": "Padrão: pix."},
            "multa_juros": {"type": ["number", "string"], "description": "Opcional. Encargos de atraso pagos junto."},
            "observacoes": _TEXTO, "trecho_origem": _TRECHO, "chave_operacao": _CHAVE,
        }, ("cobranca_id", "valor")),
        "annotations": _GRAVA,
    },
    {
        "name": "registrar_despesa", "title": "Registrar despesa",
        "description": "Registra uma despesa do negócio. Grava na hora se há veículo (moto_id ou descricao_veiculo), não há despesa igual e o valor "
                       "é de até R$ 5.000,00. Sem veículo, duplicada ou acima do teto NÃO é gravada: a resposta explica o motivo." + _AVISO_DUVIDA,
        "inputSchema": _objeto({
            "valor": {"type": ["number", "string"], "description": "Valor em reais."},
            "descricao": {"type": "string", "description": "O que foi comprado ou pago."},
            "categoria": {"type": "string", "enum": ["manutencao", "documentacao", "seguro_rastreador", "multas", "combustivel", "outros"],
                          "description": "Padrão: outros."},
            "data": {"type": "string", "description": "Data da despesa (aaaa-mm-dd ou dd/mm/aaaa). Padrão: hoje."},
            "moto_id": {"type": "string", "description": "Id do veículo, obtido em buscar_veiculos."},
            "descricao_veiculo": {"type": "string", "description": "Quando não há placa cadastrada (ex.: 'Biz Yangry')."},
            "repassar_locatario": {"type": "boolean", "description": "Se a despesa deve ser repassada ao locatário."},
            "trecho_origem": _TRECHO, "chave_operacao": _CHAVE,
        }, ("valor", "descricao")),
        "annotations": _GRAVA,
    },
    {
        "name": "cadastrar_cliente", "title": "Cadastrar cliente",
        "description": "Cadastra um cliente (locatário). Exige nome completo e CPF válido; sem CPF, use cpf_provisorio=true (o CPF real é completado "
                       "depois). Não grava se o CPF já existe ou se já há cliente com o mesmo nome (se for outra pessoa, repita com "
                       "confirmar_homonimo=true depois de perguntar ao usuário)." + _AVISO_DUVIDA,
        "inputSchema": _objeto({
            "nome": {"type": "string", "description": "Nome completo."},
            "cpf": {"type": "string", "description": "CPF com ou sem pontuação."},
            "cpf_provisorio": {"type": "boolean", "description": "Verdadeiro quando ainda não há CPF; não informe cpf junto."},
            "telefone": _TEXTO, "whatsapp": _TEXTO, "email": _TEXTO, "endereco": _TEXTO, "observacoes": _TEXTO,
            "confirmar_homonimo": {"type": "boolean", "description": "Só depois de o usuário confirmar que é outra pessoa com o mesmo nome."},
            "trecho_origem": _TRECHO, "chave_operacao": _CHAVE,
        }, ("nome",)),
        "annotations": _GRAVA,
    },
    {
        "name": "cadastrar_veiculo", "title": "Cadastrar veículo",
        "description": "Cadastra um veículo (moto ou carro). Exige placa válida (ABC1234 ou ABC1D23), marca e modelo. Não grava se a placa já existe."
                       + _AVISO_DUVIDA,
        "inputSchema": _objeto({
            "placa": _TEXTO, "marca": _TEXTO, "modelo": _TEXTO,
            "tipo": {"type": "string", "enum": ["moto", "carro"], "description": "Padrão: moto."},
            "km_atual": {"type": ["integer", "string"]}, "ano_fabricacao": {"type": ["integer", "string"]},
            "ano_modelo": {"type": ["integer", "string"]}, "cor": _TEXTO, "observacoes": _TEXTO,
            "trecho_origem": _TRECHO, "chave_operacao": _CHAVE,
        }, ("placa", "marca", "modelo")),
        "annotations": _GRAVA,
    },
    {
        "name": "listar_ultimos_lancamentos", "title": "Listar os últimos lançamentos do chat",
        "description": "Lista o que o chat gravou por último (pagamentos, despesas, clientes e veículos), com o resumo e o estado de cada um "
                       "(gravado, desfeito pelo dono). Use para conferir o que já foi registrado antes de registrar de novo.",
        "inputSchema": _objeto({"limite": {"type": "integer", "description": "Quantos listar (1 a 50). Padrão: 10."}}), "annotations": _LEITURA,
    },
)
_POR_NOME = {f["name"]: f for f in FERRAMENTAS}
FERRAMENTAS_DE_BANCO = tuple(n for n in _POR_NOME if n != "ping")
FERRAMENTAS_QUE_GRAVAM = tuple(f["name"] for f in FERRAMENTAS if not f["annotations"]["readOnlyHint"])


def escolher_protocolo(pedido) -> str:
    """Versão pedida pelo cliente, se o servidor a conhece; senão, a mais nova que ele suporta."""
    return pedido if pedido in PROTOCOLOS_SUPORTADOS else PROTOCOLOS_SUPORTADOS[0]


def conferir_argumentos(nome: str, argumentos) -> None:
    """Levanta ValueError (em português) se faltar argumento obrigatório ou vier um argumento que a ferramenta não conhece."""
    esquema = _POR_NOME[nome]["inputSchema"]
    if not isinstance(argumentos, dict):
        raise ValueError("Os argumentos precisam ser um objeto.")
    desconhecidos = sorted(set(argumentos) - set(esquema["properties"]))
    if desconhecidos:
        raise ValueError("Argumento desconhecido: " + ", ".join(desconhecidos) + ".")
    faltando = [c for c in esquema["required"] if argumentos.get(c) in (None, "")]
    if faltando:
        raise ValueError("Faltam argumentos obrigatórios: " + ", ".join(faltando) + ".")


def _erro(id_, codigo: int, mensagem: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": mensagem}}


def _resultado(id_, resultado: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": resultado}


def _texto(texto: str, erro: bool = False) -> dict:
    return {"content": [{"type": "text", "text": texto}], "isError": erro}


def _chamar(nome: str, argumentos, executar) -> dict:
    if nome not in _POR_NOME:
        raise KeyError(nome)
    if nome == "ping":
        return _texto("pong: o conector da LA Locadora está ativo e autorizado.")
    try:
        conferir_argumentos(nome, argumentos)
    except ValueError as erro:
        return _texto(str(erro), erro=True)
    if executar is None:
        return _texto("O conector ainda não está ligado ao banco de dados do sistema.", erro=True)
    resultado = executar(nome, argumentos)  # {"texto": str, "erro": bool}
    return _texto(resultado["texto"], bool(resultado.get("erro")))


def responder(mensagem, executar=None) -> dict | None:
    """Resposta JSON-RPC para uma mensagem, ou None quando é notificação ou resposta (o servidor não responde nada).

    `executar(nome, argumentos) -> {"texto", "erro"}` roda as ferramentas que falam com o banco; sem ele, só o `ping` funciona."""
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
            return _resultado(id_, _chamar(params.get("name"), params.get("arguments") or {}, executar))
        except KeyError:
            return _erro(id_, INVALID_PARAMS, "Ferramenta desconhecida.")
    return _erro(id_, METHOD_NOT_FOUND, "Método não suportado.")
