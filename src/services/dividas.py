"""Compra a prazo como dívida (ex.: Celta, entrada de R$ 5.000 + 9 parcelas de R$ 1.000)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain import dividas_lista
from src.domain.valores import hoje_br
from src.domain.dividas import calendario_parcelas, saldo_compra, validar_compra_parcelada
from src.repositories import contas, dividas, motos


def criar_compra_parcelada(
    credor: str,
    valor_total: Decimal,
    numero_parcelas: int,
    valor_parcela: Decimal,
    primeira_parcela: date,
    valor_entrada: Decimal = Decimal("0"),
    data_entrada: Optional[date] = None,
    parcelas_pagas: int = 0,
    conta_id: Optional[str] = None,
    fornecedor_id: Optional[str] = None,
    moto_id: Optional[str] = None,
    descricao: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Cria a dívida com a entrada e o calendário de parcelas. As `parcelas_pagas` primeiras entram como pagas
    (data = vencimento, marcada como estimada). A conferência dos números é a mesma da RPC."""
    credor = (credor or "").strip()
    if not credor:
        raise ValueError("Informe o credor da compra parcelada.")
    validar_compra_parcelada(valor_total, valor_entrada, numero_parcelas, valor_parcela, parcelas_pagas)
    payload = {
        "credor": credor,
        "valor_total": str(valor_total),
        "valor_entrada": str(valor_entrada),
        "numero_parcelas": numero_parcelas,
        "valor_parcela": str(valor_parcela),
        "primeira_parcela": primeira_parcela.isoformat(),
        "parcelas_pagas": parcelas_pagas,
        "data_entrada": data_entrada.isoformat() if data_entrada else None,
        "conta_id": conta_id,
        "fornecedor_id": fornecedor_id,
        "moto_id": moto_id,
        "descricao": (descricao or "").strip() or None,
        "observacoes": (observacoes or "").strip() or None,
    }
    return dividas.criar_compra_parcelada(payload)


def previa_calendario(primeira_parcela: date, numero_parcelas: int, valor_parcela: Decimal) -> list:
    """Prévia das parcelas (número, vencimento, valor), igual à que a RPC grava."""
    return [
        {"numero": i + 1, "vencimento": vencimento, "valor": valor_parcela}
        for i, vencimento in enumerate(calendario_parcelas(primeira_parcela, numero_parcelas))
    ]


def previa_saldo(
    valor_total: Decimal, valor_entrada: Decimal, valor_parcela: Decimal, parcelas_pagas: int
) -> Decimal:
    return saldo_compra(valor_total, valor_entrada, valor_parcela, parcelas_pagas)


def pagar_parcela(
    vencimento_id: str,
    data: date,
    valor: Optional[Decimal] = None,
    conta_id: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Paga uma parcela (padrão: o saldo todo). Pagamento parcial é aceito; a parcela só fica 'paga'
    quando a soma cobre o valor."""
    if valor is not None and valor <= 0:
        raise ValueError("O valor do pagamento deve ser positivo.")
    return dividas.pagar_parcela(vencimento_id, data, valor, conta_id, (observacoes or "").strip() or None)


def parcelas_da_divida(divida_id: str) -> list:
    return dividas.listar_parcelas(divida_id)


def resumo() -> dict:
    """Linhas da página Dívidas (uma por dívida, com saldo e próxima parcela) e os totais do topo."""
    linhas = dividas_lista.linhas_da_lista(dividas.listar_saldos(), dividas.listar_todas_parcelas())
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    for linha in linhas:
        linha["placa"] = placas.get(linha["moto_id"])
    return {"linhas": linhas, "totais": dividas_lista.totais(linhas)}


def ficha(divida_id: str) -> Optional[dict]:
    """Dívida com saldo, parcelas e pagamentos, ou None se não existir."""
    divida = dividas.obter(divida_id)
    if divida is None:
        return None
    saldo = next((s for s in dividas.listar_saldos() if s["divida_id"] == divida_id), None)
    parcelas = dividas.listar_parcelas(divida_id)
    moto = motos.obter(divida["moto_id"]) if divida.get("moto_id") else None
    numeros = {p["vencimento_id"]: p["numero"] for p in parcelas}
    pagamentos = [
        {**p, "parcela_numero": numeros.get(p.get("vencimento_id"))} for p in dividas.listar_pagamentos(divida_id)
    ]
    return {
        "divida": divida,
        "tipo_rotulo": dividas_lista.TIPOS_ROTULO.get(divida["tipo"], divida["tipo"]),
        "saldo": dividas_lista.saldo_em_aberto(saldo or {"saldo_calculado": divida["valor_original"]}),
        "total_pago": Decimal(str((saldo or {}).get("total_pago") or 0)),
        "saldo_confirmado": (saldo or {}).get("saldo_confirmado"),
        "diferenca": (saldo or {}).get("diferenca"),
        "parcelas": parcelas,
        "pagamentos": pagamentos,
        "moto": moto,
    }


def parcela(vencimento_id: str) -> Optional[dict]:
    return dividas.obter_parcela(vencimento_id)


def contas_ativas() -> list:
    return contas.listar_ativas()


def motos_para_selecao() -> list:
    """Motos que podem ser ligadas a uma dívida (id, placa e modelo), por placa."""
    return sorted(({"id": m["id"], "placa": m["placa"], "modelo": m.get("modelo") or ""} for m in motos.listar()),
                  key=lambda m: m["placa"])


def criar_divida(
    tipo: str,
    credor: str,
    valor_original: Decimal,
    numero_parcelas: Optional[int] = None,
    valor_parcela: Optional[Decimal] = None,
    dia_vencimento: Optional[int] = None,
    saldo_confirmado: Optional[Decimal] = None,
    moto_id: Optional[str] = None,
    descricao: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Cadastra uma dívida que não é compra parcelada (moto fiado, financiamento, fornecedor, rastreador, empréstimo).

    Com saldo confirmado, `confirmado_em` fica em hoje. A compra parcelada tem RPC própria (calendário e entrada)."""
    if tipo == "compra_parcelada":
        raise ValueError("Compra parcelada se cadastra pelo formulário próprio.")
    credor = (credor or "").strip()
    if not credor:
        raise ValueError("Informe o credor da dívida.")
    if valor_original < 0 or (saldo_confirmado is not None and saldo_confirmado < 0):
        raise ValueError("Os valores da dívida não podem ser negativos.")
    if (numero_parcelas is None) != (valor_parcela is None):
        raise ValueError("Informe o número de parcelas e o valor da parcela, ou nenhum dos dois.")
    dados = {
        "tipo": tipo,
        "credor": credor,
        "valor_original": str(valor_original),
        "numero_parcelas": numero_parcelas,
        "valor_parcela": None if valor_parcela is None else str(valor_parcela),
        "dia_vencimento": dia_vencimento,
        "saldo_confirmado": None if saldo_confirmado is None else str(saldo_confirmado),
        "confirmado_em": hoje_br().isoformat() if saldo_confirmado is not None else None,
        "moto_id": moto_id,
        "descricao": (descricao or "").strip() or None,
        "observacoes": (observacoes or "").strip() or None,
    }
    return dividas.criar_divida(dados)


def pagar_divida(
    divida_id: str,
    data: date,
    valor: Decimal,
    conta_id: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Registra um pagamento direto da dívida (sem parcela), para dívidas que não têm calendário, como moto fiado."""
    if valor <= 0:
        raise ValueError("O valor do pagamento deve ser positivo.")
    return dividas.registrar_pagamento({
        "divida_id": divida_id,
        "data": data.isoformat(),
        "valor": str(valor),
        "conta_id": conta_id,
        "observacoes": (observacoes or "").strip() or None,
    })


def atualizar_divida(divida_id: str, dados: dict) -> dict:
    """Grava a edição de uma dívida. Valores em dinheiro vão como texto; credor vazio e valores negativos são recusados.
    `dados` tem só as colunas a mudar (na compra parcelada, só credor, moto, descrição e observações)."""
    if "credor" in dados:
        dados = {**dados, "credor": (dados["credor"] or "").strip()}
        if not dados["credor"]:
            raise ValueError("Informe o credor da dívida.")
    for campo in ("valor_original", "valor_parcela"):
        if dados.get(campo) is not None:
            if Decimal(str(dados[campo])) < 0:
                raise ValueError("Os valores da dívida não podem ser negativos.")
            dados = {**dados, campo: str(dados[campo])}
    if ("numero_parcelas" in dados or "valor_parcela" in dados) and (
        (dados.get("numero_parcelas") is None) != (dados.get("valor_parcela") is None)
    ):
        raise ValueError("Informe o número de parcelas e o valor da parcela, ou nenhum dos dois.")
    return dividas.atualizar_divida(divida_id, dados)


def confirmar_saldo(divida_id: str, saldo: Optional[Decimal], data: Optional[date]) -> dict:
    """Confirma o saldo da dívida (o que falta pagar, informado pelo responsável) ou, com `saldo=None`, tira a confirmação."""
    if saldo is None:
        return dividas.atualizar_divida(divida_id, {"saldo_confirmado": None, "confirmado_em": None})
    if saldo < 0:
        raise ValueError("O saldo confirmado não pode ser negativo.")
    if data is None:
        raise ValueError("Informe a data da confirmação.")
    return dividas.atualizar_divida(divida_id, {"saldo_confirmado": str(saldo), "confirmado_em": data.isoformat()})


def apagar_divida(divida_id: str) -> None:
    """Apaga a dívida com as parcelas e os pagamentos. Irreversível: a tela pede confirmação antes."""
    dividas.apagar_divida(divida_id)


def pagamento(pagamento_id: str) -> Optional[dict]:
    return dividas.obter_pagamento(pagamento_id)


def atualizar_parcela(vencimento_id: str, vencimento: Optional[date], valor: Optional[Decimal] = None) -> dict:
    """Muda o vencimento (vazio = sem data) e, se a parcela ainda não tem pagamento, o valor."""
    atual = dividas.obter_parcela(vencimento_id)
    if atual is None:
        raise ValueError("Parcela não encontrada.")
    dados: dict = {"vencimento": vencimento.isoformat() if vencimento else None}
    if valor is not None:
        if valor <= 0:
            raise ValueError("O valor da parcela deve ser positivo.")
        if Decimal(str(atual.get("valor_pago") or 0)) > 0:
            raise ValueError("Esta parcela já tem pagamento: o valor não pode mudar. Corrija o pagamento.")
        dados["valor"] = str(valor)
    return dividas.atualizar_parcela(vencimento_id, dados)


def atualizar_pagamento(
    pagamento_id: str,
    data: date,
    valor: Decimal,
    conta_id: Optional[str] = None,
    observacoes: Optional[str] = None,
    data_estimada: bool = False,
) -> dict:
    """Corrige data, valor, conta, observações e se a data é aproximada. O limite do valor é conferido na tela (regra pura)
    e, no banco, pelo gatilho da parcela."""
    if valor <= 0:
        raise ValueError("O valor do pagamento deve ser positivo.")
    return dividas.atualizar_pagamento(pagamento_id, {
        "data": data.isoformat(),
        "valor": str(valor),
        "conta_id": conta_id,
        "observacoes": (observacoes or "").strip() or None,
        "data_estimada": bool(data_estimada),
    })
