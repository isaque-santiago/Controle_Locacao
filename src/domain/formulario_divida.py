"""Leitura e validação dos formulários de Dívidas (pagamento de parcela e, depois, compra parcelada).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

from datetime import date
from decimal import Decimal

from src.domain.entradas import decimal_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto
from src.domain.mensagens import moeda


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
