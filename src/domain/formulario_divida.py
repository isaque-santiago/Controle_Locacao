"""Leitura e validação dos formulários de Dívidas (pagamento de parcela e, depois, compra parcelada).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

from datetime import date
from decimal import Decimal

from src.domain.dividas import calendario_parcelas, saldo_compra
from src.domain.dividas_lista import TIPOS_ROTULO
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto
from src.domain.mensagens import moeda

# Tipos que se cadastram à mão aqui; a compra parcelada tem formulário próprio (calendário e entrada).
TIPOS_NOVA = ("moto_fiado", "financiamento", "fornecedor", "rastreador", "emprestimo")
CAMPOS_DIVIDA = (
    "tipo", "credor", "valor_original", "numero_parcelas", "valor_parcela", "dia_vencimento", "saldo_confirmado",
    "moto_id", "descricao", "observacoes",
)
MAX_PARCELAS = 120
MAX_CREDOR = 120
CAMPOS_COMPRA = (
    "credor", "valor_entrada", "numero_parcelas", "valor_parcela", "primeira_parcela", "parcelas_pagas",
    "data_entrada", "conta_id", "moto_id", "descricao", "observacoes",
)


def pagamento_parcela_inicial(data: date, saldo) -> dict:
    """Texto inicial dos campos: hoje, o saldo da parcela e nenhuma conta."""
    return {"data": data.isoformat(), "valor": texto_moeda(saldo), "conta_id": "", "observacoes": ""}


def texto_do_pagamento_parcela(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in ("data", "valor", "conta_id", "observacoes")}


def ler_pagamento_parcela(entrada: dict, saldo, contas_validas: set[str], alvo: str = "da parcela") -> dict:
    """Pagamento pronto para `dividas.pagar_parcela` (ou `pagar_divida`, com `alvo="da dívida"`). O valor vai de 0,01 ao
    saldo (menos que o saldo deixa o resto em aberto); a conta é opcional, mas tem que ser uma das contas ativas."""
    erros: dict[str, str] = {}
    saldo = Decimal(str(saldo))
    data = _coletar(erros, "data", _data_iso, _texto(entrada, "data"), "Data do pagamento", True)
    valor = _coletar(erros, "valor", decimal_campo, entrada.get("valor"), "Valor pago", positivo=True)
    if valor is not None and valor > saldo:
        erros["valor"] = f"Valor pago: não pode ser maior que o saldo {alvo} ({moeda(saldo)})."
    conta_id = _texto(entrada, "conta_id")
    if conta_id and conta_id not in contas_validas:
        erros["conta_id"] = "Conta: escolha uma das opções."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "data": date.fromisoformat(data),
        "valor": valor,
        "conta_id": conta_id or None,
        "observacoes": _texto(entrada, "observacoes") or None,
        "quitada": valor >= saldo,
    }


def compra_inicial(hoje: date) -> dict:
    """Texto inicial dos campos de uma compra parcelada nova."""
    return {
        "credor": "", "valor_entrada": "0,00", "numero_parcelas": "", "valor_parcela": "", "primeira_parcela": hoje.isoformat(),
        "parcelas_pagas": "0", "data_entrada": "", "conta_id": "", "moto_id": "", "descricao": "", "observacoes": "",
    }


def texto_da_compra(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in CAMPOS_COMPRA}


def ler_compra_parcelada(entrada: dict, contas_validas: set[str], motos_validas: set[str]) -> dict:
    """Compra a prazo pronta para `dividas.criar_compra_parcelada`.

    O total não é digitado: é a entrada mais as parcelas (entrada + n x parcela), a mesma conta que a RPC confere."""
    erros: dict[str, str] = {}
    credor = _texto(entrada, "credor")
    if not credor:
        erros["credor"] = "Credor: informe a quem se deve."
    elif len(credor) > MAX_CREDOR:
        erros["credor"] = f"Credor: use no máximo {MAX_CREDOR} caracteres."
    entrada_valor = _coletar(erros, "valor_entrada", decimal_campo, entrada.get("valor_entrada") or "0", "Entrada")
    n = _coletar(erros, "numero_parcelas", inteiro_campo, _texto(entrada, "numero_parcelas"), "Número de parcelas", 1, MAX_PARCELAS)
    parcela = _coletar(erros, "valor_parcela", decimal_campo, entrada.get("valor_parcela"), "Valor da parcela", positivo=True)
    primeira = _coletar(erros, "primeira_parcela", _data_iso, _texto(entrada, "primeira_parcela"), "Primeira parcela", True)
    pagas = _coletar(erros, "parcelas_pagas", inteiro_campo, _texto(entrada, "parcelas_pagas") or "0", "Parcelas já pagas", 0)
    if n is not None and pagas is not None and pagas > n:
        erros["parcelas_pagas"] = f"Parcelas já pagas: no máximo {n}, o número de parcelas."
    data_entrada = _coletar(erros, "data_entrada", _data_iso, _texto(entrada, "data_entrada"), "Data da entrada", False)
    conta_id = _texto(entrada, "conta_id")
    if conta_id and conta_id not in contas_validas:
        erros["conta_id"] = "Conta: escolha uma das opções."
    moto_id = _texto(entrada, "moto_id")
    if moto_id and moto_id not in motos_validas:
        erros["moto_id"] = "Moto: escolha uma das opções."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "credor": credor,
        "valor_total": entrada_valor + n * parcela,
        "valor_entrada": entrada_valor,
        "numero_parcelas": n,
        "valor_parcela": parcela,
        "primeira_parcela": date.fromisoformat(primeira),
        "parcelas_pagas": pagas,
        "data_entrada": date.fromisoformat(data_entrada) if data_entrada else None,
        "conta_id": conta_id or None,
        "moto_id": moto_id or None,
        "descricao": _texto(entrada, "descricao") or None,
        "observacoes": _texto(entrada, "observacoes") or None,
    }


def previa_da_compra(dados: dict) -> dict:
    """O que a compra vai gerar: total, saldo depois da entrada e das parcelas já pagas, e o calendário."""
    vencimentos = calendario_parcelas(dados["primeira_parcela"], dados["numero_parcelas"])
    return {
        "valor_total": dados["valor_total"],
        "saldo": saldo_compra(dados["valor_total"], dados["valor_entrada"], dados["valor_parcela"], dados["parcelas_pagas"]),
        "parcelas": [
            {"numero": i, "vencimento": v, "valor": dados["valor_parcela"], "paga": i <= dados["parcelas_pagas"]}
            for i, v in enumerate(vencimentos, start=1)
        ],
    }


def tipos_para_selecao() -> list[tuple[str, str]]:
    return [(t, TIPOS_ROTULO[t]) for t in TIPOS_NOVA]


def divida_inicial() -> dict:
    return {"tipo": TIPOS_NOVA[0], "credor": "", "valor_original": "", "numero_parcelas": "", "valor_parcela": "",
            "dia_vencimento": "", "saldo_confirmado": "", "moto_id": "", "descricao": "", "observacoes": ""}


def texto_da_divida(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in CAMPOS_DIVIDA}


def ler_divida(entrada: dict, motos_validas: set[str]) -> dict:
    """Dívida pronta para `dividas.criar_divida`. Parcelas e valor da parcela vêm juntos ou nenhum dos dois; o saldo confirmado
    (opcional) é o que o responsável informou como o que falta pagar; o valor original pode ser 0,00 quando só se sabe o saldo."""
    erros: dict[str, str] = {}
    tipo = _texto(entrada, "tipo")
    if tipo not in TIPOS_NOVA:
        erros["tipo"] = "Tipo: escolha uma das opções."
    credor = _texto(entrada, "credor")
    if not credor:
        erros["credor"] = "Credor: informe a quem se deve."
    elif len(credor) > MAX_CREDOR:
        erros["credor"] = f"Credor: use no máximo {MAX_CREDOR} caracteres."
    original = _coletar(erros, "valor_original", decimal_campo, entrada.get("valor_original") or "0", "Valor original")
    texto_n, texto_parcela = _texto(entrada, "numero_parcelas"), _texto(entrada, "valor_parcela")
    n = parcela = None
    if texto_n or texto_parcela:
        n = _coletar(erros, "numero_parcelas", inteiro_campo, texto_n, "Número de parcelas", 1, MAX_PARCELAS)
        parcela = _coletar(erros, "valor_parcela", decimal_campo, texto_parcela, "Valor da parcela", positivo=True)
    dia = None
    if _texto(entrada, "dia_vencimento"):
        dia = _coletar(erros, "dia_vencimento", inteiro_campo, _texto(entrada, "dia_vencimento"), "Dia do vencimento", 1, 31)
    confirmado = None
    if _texto(entrada, "saldo_confirmado"):
        confirmado = _coletar(erros, "saldo_confirmado", decimal_campo, entrada.get("saldo_confirmado"), "Saldo confirmado")
    moto_id = _texto(entrada, "moto_id")
    if moto_id and moto_id not in motos_validas:
        erros["moto_id"] = "Moto: escolha uma das opções."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "tipo": tipo,
        "credor": credor,
        "valor_original": original,
        "numero_parcelas": n,
        "valor_parcela": parcela,
        "dia_vencimento": dia,
        "saldo_confirmado": confirmado,
        "moto_id": moto_id or None,
        "descricao": _texto(entrada, "descricao") or None,
        "observacoes": _texto(entrada, "observacoes") or None,
    }


# ---------------------------------------------------------------- editar e confirmar saldo --

# Na compra parcelada, valor original = entrada + n x parcela é uma regra do banco: só os dados de identificação mudam.
CAMPOS_EDICAO_COMPRA = ("credor", "moto_id", "descricao", "observacoes")
CAMPOS_EDICAO = (
    "tipo", "credor", "valor_original", "numero_parcelas", "valor_parcela", "dia_vencimento", "moto_id", "descricao", "observacoes",
)


def campos_editaveis(tipo: str) -> tuple[str, ...]:
    return CAMPOS_EDICAO_COMPRA if tipo == "compra_parcelada" else CAMPOS_EDICAO


def edicao_inicial(divida: dict) -> dict:
    """Texto inicial dos campos da edição, com o que a dívida tem hoje."""
    def numero(campo):
        return "" if divida.get(campo) is None else str(divida[campo])

    def dinheiro(campo):
        return "" if divida.get(campo) is None else texto_moeda(divida[campo])

    return {
        "tipo": divida.get("tipo") or "", "credor": divida.get("credor") or "", "valor_original": dinheiro("valor_original"),
        "numero_parcelas": numero("numero_parcelas"), "valor_parcela": dinheiro("valor_parcela"),
        "dia_vencimento": numero("dia_vencimento"), "moto_id": divida.get("moto_id") or "",
        "descricao": divida.get("descricao") or "", "observacoes": divida.get("observacoes") or "",
    }


def texto_da_edicao(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in CAMPOS_EDICAO}


def ler_edicao_divida(entrada: dict, tipo: str, motos_validas: set[str]) -> dict:
    """Colunas da dívida a gravar. As mesmas regras do cadastro; na compra parcelada só credor, moto, descrição e observações
    mudam (o total e as parcelas estão amarrados ao calendário já gerado). Nos outros tipos o tipo também pode mudar, entre os
    cinco de `TIPOS_NOVA`; uma dívida nunca vira (nem deixa de ser) compra parcelada, porque essa tem calendário e regra de total."""
    erros: dict[str, str] = {}
    credor = _texto(entrada, "credor")
    if not credor:
        erros["credor"] = "Credor: informe a quem se deve."
    elif len(credor) > MAX_CREDOR:
        erros["credor"] = f"Credor: use no máximo {MAX_CREDOR} caracteres."
    moto_id = _texto(entrada, "moto_id")
    if moto_id and moto_id not in motos_validas:
        erros["moto_id"] = "Moto: escolha uma das opções."
    dados = {"credor": credor, "moto_id": moto_id or None, "descricao": _texto(entrada, "descricao") or None,
             "observacoes": _texto(entrada, "observacoes") or None}
    if tipo != "compra_parcelada":
        tipo_novo = _texto(entrada, "tipo") or tipo
        if tipo_novo not in TIPOS_NOVA:
            erros["tipo"] = "Tipo: escolha uma das opções."
        dados["tipo"] = tipo_novo
        original = _coletar(erros, "valor_original", decimal_campo, entrada.get("valor_original") or "0", "Valor original")
        texto_n, texto_parcela = _texto(entrada, "numero_parcelas"), _texto(entrada, "valor_parcela")
        n = parcela = None
        if texto_n or texto_parcela:
            n = _coletar(erros, "numero_parcelas", inteiro_campo, texto_n, "Número de parcelas", 1, MAX_PARCELAS)
            parcela = _coletar(erros, "valor_parcela", decimal_campo, texto_parcela, "Valor da parcela", positivo=True)
        dia = None
        if _texto(entrada, "dia_vencimento"):
            dia = _coletar(erros, "dia_vencimento", inteiro_campo, _texto(entrada, "dia_vencimento"), "Dia do vencimento", 1, 31)
        dados.update(valor_original=original, numero_parcelas=n, valor_parcela=parcela, dia_vencimento=dia)
    if erros:
        raise ErroDeCampos(erros)
    return dados


def saldo_inicial(divida: dict, saldo_atual, hoje: date) -> dict:
    """Campos da confirmação de saldo: o confirmado de hoje (ou, sem ele, o saldo que o sistema calcula) e a data de hoje."""
    confirmado = divida.get("saldo_confirmado")
    return {"saldo": texto_moeda(confirmado if confirmado is not None else saldo_atual), "data": hoje.isoformat()}


def texto_do_saldo(entrada: dict) -> dict:
    return {"saldo": _texto(entrada, "saldo"), "data": _texto(entrada, "data")}


def ler_saldo_confirmado(entrada: dict, hoje: date) -> dict:
    """`acao=limpar` tira a confirmação (volta a valer o saldo calculado). Senão confirma: saldo de 0,00 para cima e data até hoje."""
    if _texto(entrada, "acao") == "limpar":
        return {"saldo_confirmado": None, "confirmado_em": None}
    erros: dict[str, str] = {}
    saldo = _coletar(erros, "saldo", decimal_campo, entrada.get("saldo"), "Saldo confirmado")
    data = _coletar(erros, "data", _data_iso, _texto(entrada, "data"), "Data da confirmação", True)
    if data is not None and date.fromisoformat(data) > hoje:
        erros["data"] = "Data da confirmação: não pode ser no futuro."
    if erros:
        raise ErroDeCampos(erros)
    return {"saldo_confirmado": saldo, "confirmado_em": date.fromisoformat(data)}
