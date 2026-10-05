"""Orquestra repositórios/RPCs para criação e encerramento de contratos."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.agenda_cobrancas import gerar_agenda
from src.repositories import contratos


def listar():
    return contratos.listar()


def criar_com_vistoria(dados, vistoria):
    """Cria o contrato com a vistoria de entrega. `data_fim_prevista` ausente ou nula é contrato
    por prazo indeterminado (a regra da operação)."""
    fim = dados.get("data_fim_prevista") or None
    if fim is not None and fim < dados["data_inicio"]:
        raise ValueError("O fim do contrato deve ser igual ou posterior ao início.")
    previa_agenda(
        date.fromisoformat(dados["data_inicio"]),
        dados["periodicidade"],
        Decimal(dados["valor_periodo"]),
        date.fromisoformat(fim) if fim else None,
    )
    return contratos.criar_com_vistoria({**dados, "data_fim_prevista": fim}, vistoria)


def _validar_danos(valor_danos: Decimal, descricao_danos: Optional[str]) -> Optional[str]:
    if valor_danos < 0:
        raise ValueError("O valor dos danos não pode ser negativo.")
    descricao = (descricao_danos or "").strip() or None
    if valor_danos > 0 and descricao is None:
        raise ValueError("Descreva os danos que serão descontados da caução.")
    return descricao


def encerrar_com_vistoria(
    contrato_id,
    data,
    vistoria,
    valor_danos: Decimal = Decimal("0"),
    descricao_danos: Optional[str] = None,
):
    """Encerra o contrato com a vistoria de devolução. Os danos são descontados da caução
    (e o excedente é cobrado do cliente): a RPC calcula a devolução (`domain/caucao.py`)."""
    descricao = _validar_danos(valor_danos, descricao_danos)
    return contratos.encerrar_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao)


def previa_agenda(
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: Optional[date] = None,
) -> list:
    """Prévia da agenda de cobranças exibida na tela, com a mesma lógica usada
    pela RPC ao criar o contrato de verdade. Sem data final (prazo indeterminado),
    mostra só a janela inicial; as seguintes são geradas enquanto o contrato estiver ativo."""
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
    contrato_id: str,
    data: date,
    km_final: int,
    valor_danos: Decimal = Decimal("0"),
    descricao_danos: Optional[str] = None,
) -> dict:
    descricao = _validar_danos(valor_danos, descricao_danos)
    return contratos.encerrar_via_rpc(contrato_id, data, km_final, valor_danos, descricao)
