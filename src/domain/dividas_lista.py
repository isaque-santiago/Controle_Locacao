"""Regras puras da página Dívidas: rótulos, saldo em aberto e a próxima parcela de cada dívida."""

from datetime import date
from decimal import Decimal
from typing import Optional

_ZERO = Decimal("0.00")
TIPOS_ROTULO = {
    "moto_fiado": "Moto fiado",
    "financiamento": "Financiamento",
    "fornecedor": "Fornecedor",
    "rastreador": "Rastreador",
    "emprestimo": "Empréstimo",
    "compra_parcelada": "Compra parcelada",
}
SITUACOES_PARCELA_ROTULO = {"paga": "Paga", "atrasada": "Atrasada", "a_vencer": "A vencer", "sem_data": "Sem data"}
# Tom do selo de cada situação (combina com os selos da tela).
SITUACOES_PARCELA_TOM = {"paga": "ok", "atrasada": "perigo", "a_vencer": "neutro", "sem_data": "atencao"}


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else 0))


def _data(valor) -> Optional[date]:
    if valor is None:
        return None
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def saldo_em_aberto(saldo: dict) -> Decimal:
    """Saldo que vale: o confirmado pelo responsável, senão o calculado; nunca negativo."""
    confirmado = saldo.get("saldo_confirmado")
    return max(_dinheiro(confirmado if confirmado is not None else saldo.get("saldo_calculado")), _ZERO)


def situacao_da_divida(saldo: Decimal, atrasadas: int) -> str:
    """'quitada', 'atrasada' (tem parcela vencida e não paga) ou 'em_aberto'."""
    if saldo <= 0:
        return "quitada"
    return "atrasada" if atrasadas > 0 else "em_aberto"


def linhas_da_lista(saldos: list[dict], parcelas: list[dict]) -> list[dict]:
    """Uma linha por dívida: saldo, próxima parcela em aberto e quantas estão atrasadas.

    Ordem: atrasadas primeiro, depois as em aberto (maior saldo primeiro) e as quitadas por último."""
    por_divida: dict[str, list[dict]] = {}
    for p in parcelas:
        por_divida.setdefault(p["divida_id"], []).append(p)
    ordem = {"atrasada": 0, "em_aberto": 1, "quitada": 2}
    linhas = []
    for s in saldos:
        abertas = [p for p in por_divida.get(s["divida_id"], []) if p.get("situacao") != "paga"]
        com_data = sorted((p for p in abertas if p.get("vencimento")), key=lambda p: _data(p["vencimento"]))
        proxima = com_data[0] if com_data else (abertas[0] if abertas else None)
        saldo = saldo_em_aberto(s)
        atrasadas = sum(1 for p in abertas if p.get("situacao") == "atrasada")
        linhas.append({
            "divida_id": s["divida_id"],
            "credor": s["credor"],
            "tipo": s["tipo"],
            "tipo_rotulo": TIPOS_ROTULO.get(s["tipo"], s["tipo"]),
            "moto_id": s.get("moto_id"),
            "valor_original": _dinheiro(s.get("valor_original")),
            "total_pago": _dinheiro(s.get("total_pago")),
            "saldo": saldo,
            "saldo_confirmado": s.get("saldo_confirmado") is not None,
            "proxima_vencimento": _data(proxima["vencimento"]) if proxima else None,
            "proxima_valor": _dinheiro(proxima["valor"]) if proxima else None,
            "parcelas_abertas": len(abertas),
            "parcelas_atrasadas": atrasadas,
            "situacao": situacao_da_divida(saldo, atrasadas),
        })
    linhas.sort(key=lambda l: (ordem[l["situacao"]], -l["saldo"], l["credor"]))
    return linhas


def totais(linhas: list[dict]) -> dict:
    """Cartões do topo: total em aberto, motos fiado, parcelas atrasadas e a próxima a vencer."""
    em_aberto = [l for l in linhas if l["situacao"] != "quitada"]
    proximas = sorted((l["proxima_vencimento"], l["credor"]) for l in em_aberto if l["proxima_vencimento"])
    return {
        "total_em_aberto": sum((l["saldo"] for l in em_aberto), _ZERO),
        "moto_fiado": sum((l["saldo"] for l in em_aberto if l["tipo"] == "moto_fiado"), _ZERO),
        "dividas_em_aberto": len(em_aberto),
        "parcelas_atrasadas": sum(l["parcelas_atrasadas"] for l in em_aberto),
        "proximo_vencimento": proximas[0][0] if proximas else None,
        "proximo_credor": proximas[0][1] if proximas else None,
    }


def limite_do_pagamento(pagamento: dict, parcelas: list[dict], saldo_da_divida) -> Decimal:
    """O maior valor que este pagamento pode passar a ter, sem estourar o que falta.

    Pagamento de uma parcela: valor da parcela menos o que os outros pagamentos já cobriram. Pagamento direto (sem parcela):
    saldo em aberto da dívida mais o próprio valor atual."""
    atual = _dinheiro(pagamento.get("valor"))
    vencimento_id = pagamento.get("vencimento_id")
    if vencimento_id:
        parcela = next((p for p in parcelas if p.get("vencimento_id") == vencimento_id), None)
        if parcela is not None:
            return _dinheiro(parcela["valor"]) - _dinheiro(parcela.get("valor_pago")) + atual
    return _dinheiro(saldo_da_divida) + atual
