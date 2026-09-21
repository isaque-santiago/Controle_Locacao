"""Orquestra alertas, catálogo, plano por moto e registro de manutenção."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.manutencao_regras import calcular_proxima_manutencao, calcular_situacao
from src.repositories import (
    configuracoes,
    itens_manutencao,
    manutencoes,
    moto_plano_manutencao,
)


def listar_catalogo(somente_ativos: bool = False):
    return itens_manutencao.listar(somente_ativos)


def criar_item_catalogo(dados: dict) -> dict:
    if dados.get("intervalo_km") is None and dados.get("intervalo_dias") is None:
        raise ValueError("Informe intervalo_km e/ou intervalo_dias.")
    return itens_manutencao.criar(dados)


def atualizar_item_catalogo(item_id: str, dados: dict) -> dict:
    return itens_manutencao.atualizar(item_id, dados)


def listar_plano_moto(moto_id: str) -> list:
    """Plano da moto com a próxima km/data e a situação já calculadas."""
    config = configuracoes.obter()
    hoje = date.today()
    alerta_km = config["alerta_manutencao_km"]
    alerta_dias = config["alerta_manutencao_dias"]

    plano = moto_plano_manutencao.listar_por_moto(moto_id)
    resultado = []
    for linha in plano:
        item = linha["item"]
        intervalo_km = linha["intervalo_km"] or item["intervalo_km"]
        intervalo_dias = linha["intervalo_dias"] or item["intervalo_dias"]
        ultima_data = date.fromisoformat(linha["ultima_data"]) if linha["ultima_data"] else None

        proxima = calcular_proxima_manutencao(
            ultima_km=linha["ultima_km"],
            intervalo_km=intervalo_km,
            ultima_data=ultima_data,
            intervalo_dias=intervalo_dias,
        )
        # km_atual da moto vem embutido no plano só se o repositório trouxer;
        # a tela busca a moto separadamente e passa km_atual por fora quando
        # quiser a situação — aqui devolvemos os dados crus + próxima.
        resultado.append(
            {
                **linha,
                "intervalo_km_efetivo": intervalo_km,
                "intervalo_dias_efetivo": intervalo_dias,
                "proxima_km": proxima["proxima_km"],
                "proxima_data": proxima["proxima_data"],
                "_alerta_km": alerta_km,
                "_alerta_dias": alerta_dias,
                "_hoje": hoje,
            }
        )
    return resultado


def situacao_item_plano(linha_plano: dict, km_atual: int) -> str:
    """Situação (em_dia/proxima/vencida) de uma linha já processada por
    listar_plano_moto, dado o km_atual da moto."""
    return calcular_situacao(
        km_atual=km_atual,
        proxima_km=linha_plano["proxima_km"],
        hoje=linha_plano["_hoje"],
        proxima_data=linha_plano["proxima_data"],
        alerta_km=linha_plano["_alerta_km"],
        alerta_dias=linha_plano["_alerta_dias"],
    )


def aplicar_plano_padrao(moto_id: str) -> dict:
    return moto_plano_manutencao.aplicar_plano_padrao_via_rpc(moto_id)


def listar_manutencoes(moto_id: Optional[str] = None):
    return manutencoes.listar(moto_id)


def obter_manutencao(manutencao_id: str):
    return manutencoes.obter(manutencao_id)


def registrar_manutencao(
    moto_id: str,
    tipo: str,
    data_entrada: date,
    km: int,
    descricao: str,
    status: str = "concluida",
    contrato_id: Optional[str] = None,
    data_saida: Optional[date] = None,
    oficina: Optional[str] = None,
    custo_mao_obra: Decimal = Decimal("0"),
    cobrar_do_cliente: bool = False,
    observacoes: Optional[str] = None,
    itens: Optional[list] = None,
) -> dict:
    """Registra manutenção (preventiva/corretiva) com seus itens, via RPC
    (grava manutencao + itens + zera contador do plano + histórico de km +
    ajusta status da moto, tudo numa transação)."""
    if tipo not in ("preventiva", "corretiva"):
        raise ValueError("tipo deve ser 'preventiva' ou 'corretiva'.")

    payload = {
        "moto_id": moto_id,
        "contrato_id": contrato_id,
        "tipo": tipo,
        "status": status,
        "data_entrada": data_entrada.isoformat(),
        "data_saida": data_saida.isoformat() if data_saida else None,
        "km": km,
        "oficina": oficina,
        "descricao": descricao,
        "custo_mao_obra": str(custo_mao_obra),
        "cobrar_do_cliente": cobrar_do_cliente,
        "observacoes": observacoes,
        "itens": [
            {
                "item_id": item.get("item_id"),
                "descricao": item["descricao"],
                "quantidade": str(item.get("quantidade", 1)),
                "valor_unitario": str(item.get("valor_unitario", 0)),
            }
            for item in (itens or [])
        ],
    }
    return manutencoes.registrar_via_rpc(payload)
