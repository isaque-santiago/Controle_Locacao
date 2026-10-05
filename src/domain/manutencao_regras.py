"""Próxima manutenção e situação do alerta (em_dia, proxima, vencida).

Mesma lógica usada pela view vw_alertas_manutencao no banco: replicada aqui
para poder ser testada isoladamente e usada em prévias na tela, antes de
gravar qualquer coisa.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from src.domain.entradas import decimal_campo


def _vale(texto, esperado) -> bool:
    """Campo vazio ou que equivale ao valor de uma linha ainda não preenchida (`1` ou `0,00`)."""
    bruto = str(texto if texto is not None else "").strip()
    if not bruto:
        return True
    try:
        return decimal_campo(bruto, "Campo") == esperado
    except ValueError:
        return False


def preparar_itens_adicionais(linhas: list[dict]) -> list[dict]:
    """Valida as linhas livres adicionadas na lista de peças e serviços. Cada erro cita a linha
    pelo nome da peça ou serviço."""
    itens = []
    for linha in linhas:
        descricao = str(linha.get("descricao") or "").strip()
        quantidade = linha.get("quantidade")
        valor_unitario = linha.get("valor_unitario")
        if not descricao and _vale(quantidade, Decimal("1")) and _vale(valor_unitario, Decimal("0")):
            continue
        if not descricao:
            raise ValueError("Informe a descrição de cada peça ou serviço adicional.")
        itens.append(
            {
                "descricao": descricao,
                "quantidade": decimal_campo(str(quantidade or "1"), f"Quantidade de {descricao}", positivo=True),
                "valor_unitario": decimal_campo(str(valor_unitario or "0"), f"Valor unitário de {descricao}"),
            }
        )
    return itens


def calcular_proxima_manutencao(
    ultima_km: Optional[int],
    intervalo_km: Optional[int],
    ultima_data: Optional[date],
    intervalo_dias: Optional[int],
) -> dict:
    """Próxima km e próxima data de um item do plano (podem coexistir; o que
    vencer primeiro decide a situação em calcular_situacao)."""
    proxima_km = None
    if intervalo_km is not None:
        proxima_km = (ultima_km or 0) + intervalo_km

    proxima_data = None
    if intervalo_dias is not None and ultima_data is not None:
        proxima_data = ultima_data + timedelta(days=intervalo_dias)

    return {"proxima_km": proxima_km, "proxima_data": proxima_data}


def calcular_situacao(
    km_atual: int,
    proxima_km: Optional[int],
    hoje: date,
    proxima_data: Optional[date],
    alerta_km: int,
    alerta_dias: int,
) -> str:
    """Situação do alerta: 'vencida' (passou), 'proxima' (dentro do limite
    de alerta) ou 'em_dia'."""
    vencida = (proxima_km is not None and km_atual >= proxima_km) or (
        proxima_data is not None and hoje >= proxima_data
    )
    if vencida:
        return "vencida"

    proxima = (proxima_km is not None and proxima_km - km_atual <= alerta_km) or (
        proxima_data is not None and (proxima_data - hoje).days <= alerta_dias
    )
    if proxima:
        return "proxima"

    return "em_dia"
