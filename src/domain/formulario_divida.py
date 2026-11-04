"""Leitura e validação dos formulários de Dívidas (pagamento de parcela e, depois, compra parcelada).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

from datetime import date
from decimal import Decimal

from src.domain.dividas import calendario_parcelas, saldo_compra
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto
from src.domain.mensagens import moeda

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


def ler_pagamento_parcela(entrada: dict, saldo, contas_validas: set[str]) -> dict:
    """Pagamento pronto para `dividas.pagar_parcela`. O valor vai de 0,01 ao saldo da parcela (menos que o saldo
    deixa o resto em aberto); a conta é opcional, mas tem que ser uma das contas ativas."""
    erros: dict[str, str] = {}
    saldo = Decimal(str(saldo))
    data = _coletar(erros, "data", _data_iso, _texto(entrada, "data"), "Data do pagamento", True)
    valor = _coletar(erros, "valor", decimal_campo, entrada.get("valor"), "Valor pago", positivo=True)
    if valor is not None and valor > saldo:
        erros["valor"] = f"Valor pago: não pode ser maior que o saldo da parcela ({moeda(saldo)})."
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
