"""Orquestra repositórios/RPCs para criação e encerramento de contratos."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.agenda_cobrancas import gerar_agenda
from src.repositories import contratos


def listar():
    return contratos.listar()


def criar_com_vistoria(dados, vistoria):
    if dados["data_fim_prevista"] < dados["data_inicio"]:
        raise ValueError("O fim do contrato deve ser igual ou posterior ao início.")
    previa_agenda(
        date.fromisoformat(dados["data_inicio"]),
        dados["periodicidade"],
        Decimal(dados["valor_periodo"]),
        date.fromisoformat(dados["data_fim_prevista"]),
    )
    return contratos.criar_com_vistoria(dados, vistoria)


def encerrar_com_vistoria(contrato_id, data, vistoria, caucao_devolvida):
    return contratos.encerrar_com_vistoria(
        contrato_id, data, vistoria, caucao_devolvida
    )


def previa_agenda(
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: date,
) -> list:
    """Prévia da agenda de cobranças exibida na tela, com a mesma lógica usada
    pela RPC ao criar o contrato de verdade."""
    return gerar_agenda(data_inicio, periodicidade, valor_periodo, data_fim_prevista)


def criar_contrato(
    moto_id: str,
    cliente_id: str,
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: Optional[date] = None,
    caucao_valor: Decimal = Decimal("0"),
    km_inicial: Optional[int] = None,
) -> dict:
    payload = {
        "moto_id": moto_id,
        "cliente_id": cliente_id,
        "data_inicio": data_inicio.isoformat(),
        "data_fim_prevista": (
            data_fim_prevista.isoformat() if data_fim_prevista else None
        ),
        "periodicidade": periodicidade,
        "valor_periodo": str(valor_periodo),
        "caucao_valor": str(caucao_valor),
        "km_inicial": km_inicial,
    }
    return contratos.criar_via_rpc(payload)


def encerrar_contrato(
    contrato_id: str, data: date, km_final: int, caucao_devolvida: bool = False
) -> dict:
    return contratos.encerrar_via_rpc(contrato_id, data, km_final, caucao_devolvida)
