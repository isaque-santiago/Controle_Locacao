"""Orquestra repositórios/RPCs para criação e encerramento de contratos."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.agenda_cobrancas import gerar_agenda
from src.domain.contrato_motos import normalizar_motos_vinculadas
from src.domain.vistorias_por_moto import exigir_todas_as_motos, validar_vistorias_vinculadas
from src.repositories import contratos, motos as repo_motos


def listar():
    return contratos.listar()


def _km_atual_por_moto() -> dict:
    return {m["id"]: m["km_atual"] for m in repo_motos.listar()}


def criar_com_vistoria(dados, vistoria, vistorias_vinculadas=None, exigir_todas=False):
    """Cria o contrato com a vistoria de entrega. `data_fim_prevista` ausente ou nula é contrato
    por prazo indeterminado (a regra da operação). `vistorias_vinculadas` traz a vistoria de entrega de cada moto
    vinculada; com `exigir_todas` (regra da tela) todas as vinculadas precisam ter a sua."""
    fim = dados.get("data_fim_prevista") or None
    if fim is not None and fim < dados["data_inicio"]:
        raise ValueError("O fim do contrato deve ser igual ou posterior ao início.")
    if dados.get("motos_vinculadas"):
        dados = {**dados, "motos_vinculadas": normalizar_motos_vinculadas(dados["moto_id"], dados["motos_vinculadas"])}
    previa_agenda(
        date.fromisoformat(dados["data_inicio"]),
        dados["periodicidade"],
        Decimal(dados["valor_periodo"]),
        date.fromisoformat(fim) if fim else None,
        numero_parcelas=dados.get("numero_parcelas"),
        parcelas_pagas_inicial=dados.get("parcelas_pagas_inicial") or 0,
        primeira_cobranca=date.fromisoformat(dados["primeira_cobranca"]) if dados.get("primeira_cobranca") else None,
    )
    dados = {**dados, "data_fim_prevista": fim}
    if exigir_todas:
        exigir_todas_as_motos(dados["moto_id"], dados.get("motos_vinculadas"), vistorias_vinculadas)
    if vistorias_vinculadas:
        validadas = validar_vistorias_vinculadas(
            dados["moto_id"], dados.get("motos_vinculadas"), vistorias_vinculadas, _km_atual_por_moto()
        )
        return contratos.criar_com_vistoria(dados, vistoria, validadas)
    return contratos.criar_com_vistoria(dados, vistoria)


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
    vistorias_vinculadas=None,
    exigir_todas=False,
):
    """Encerra o contrato com a vistoria de devolução. Os danos são descontados da caução
    (e o excedente é cobrado do cliente): a RPC calcula a devolução (`domain/caucao.py`).
    `vistorias_vinculadas` traz a devolução de cada moto vinculada (com `exigir_todas`, todas precisam ter a sua)."""
    descricao = _validar_danos(valor_danos, descricao_danos)
    if exigir_todas or vistorias_vinculadas:
        motos_do_contrato = contratos.listar_motos_do_contrato(contrato_id)
        principal = next((m["moto_id"] for m in motos_do_contrato if m["principal"]), None)
        vinculadas = [m["moto_id"] for m in motos_do_contrato if not m["principal"]]
        if principal is None:
            raise ValueError("Contrato não encontrado.")
        if exigir_todas:
            exigir_todas_as_motos(principal, vinculadas, vistorias_vinculadas)
        if vistorias_vinculadas:
            validadas = validar_vistorias_vinculadas(principal, vinculadas, vistorias_vinculadas, _km_atual_por_moto())
            return contratos.encerrar_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao, validadas)
    return contratos.encerrar_com_vistoria(contrato_id, data, vistoria, valor_danos, descricao)


def previa_agenda(
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: Optional[date] = None,
    *,
    numero_parcelas: Optional[int] = None,
    parcelas_pagas_inicial: int = 0,
    primeira_cobranca: Optional[date] = None,
) -> list:
    """Prévia da agenda de cobranças exibida na tela, com a mesma lógica usada
    pela RPC ao criar o contrato de verdade. Sem data final (prazo indeterminado),
    mostra só a janela inicial; as seguintes são geradas enquanto o contrato estiver ativo.
    Na promessa de compra, `numero_parcelas` limita a agenda e as pagas/âncora vêm do contrato em andamento."""
    return gerar_agenda(
        data_inicio, periodicidade, valor_periodo, data_fim_prevista,
        numero_parcelas=numero_parcelas, parcelas_pagas_inicial=parcelas_pagas_inicial, primeira_cobranca=primeira_cobranca,
    )


def criar_contrato(
    moto_id: str,
    cliente_id: str,
    data_inicio: date,
    periodicidade: str,
    valor_periodo: Decimal,
    data_fim_prevista: Optional[date] = None,
    caucao_valor: Decimal = Decimal("0"),
    km_inicial: Optional[int] = None,
    motos_vinculadas: Optional[list] = None,
) -> dict:
    """Cria o contrato. `motos_vinculadas` são as motos além da principal (contrato com mais de uma moto:
    a parcela e a receita ficam na moto principal)."""
    vinculadas = normalizar_motos_vinculadas(moto_id, motos_vinculadas)
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
    if vinculadas:
        payload["motos_vinculadas"] = vinculadas
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


def listar_vinculos() -> list:
    """Motos vinculadas de todos os contratos (linhas de `contrato_motos`), para resolver o locatário de cada moto."""
    return contratos.listar_vinculos()


def contar_vinculadas() -> dict:
    """{contrato_id: nº de motos vinculadas} de todos os contratos, para a lista."""
    return contratos.contar_vinculadas()


def motos_do_contrato(contrato_id: str) -> list:
    """Motos do contrato, a principal primeiro (`principal` = True)."""
    return contratos.listar_motos_do_contrato(contrato_id)
