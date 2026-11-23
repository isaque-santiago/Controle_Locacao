"""Orquestra cadastro de motos e atualização de quilometragem."""

from postgrest.exceptions import APIError

from datetime import date

from src.domain import arquivamento
from src.domain.arquivamento import Pendencias
from src.domain.validadores import validar_placa
from src.repositories import cobrancas, contratos, historico_km, manutencoes, motos

_CODIGO_VIOLACAO_UNICIDADE = "23505"


def _normalizar_placa(placa: str) -> str:
    return (placa or "").strip().upper().replace("-", "")


def listar():
    return motos.listar()


def obter(moto_id: str):
    return motos.obter(moto_id)


def criar(dados: dict) -> dict:
    """Valida e normaliza a placa antes de cadastrar a moto."""
    dados = dict(dados)
    if not dados.get("marca", "").strip() or not dados.get("modelo", "").strip():
        raise ValueError("Informe marca e modelo.")
    if not validar_placa(dados.get("placa", "")):
        raise ValueError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
    dados["placa"] = _normalizar_placa(dados["placa"])

    try:
        return motos.criar(dados)
    except APIError as erro:
        if erro.code == _CODIGO_VIOLACAO_UNICIDADE:
            raise ValueError(
                f"Já existe um veículo cadastrado com a placa {dados['placa']}."
            ) from erro
        raise


def atualizar(moto_id: str, dados: dict) -> dict:
    dados = dict(dados)
    if "km_atual" in dados:
        raise ValueError("Use o registro de quilometragem para alterar o km.")
    if "placa" in dados:
        if not validar_placa(dados["placa"]):
            raise ValueError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
        dados["placa"] = _normalizar_placa(dados["placa"])

    try:
        return motos.atualizar(moto_id, dados)
    except APIError as erro:
        if erro.code == _CODIGO_VIOLACAO_UNICIDADE:
            raise ValueError(
                f"Já existe um veículo cadastrado com a placa {dados['placa']}."
            ) from erro
        raise


def atualizar_km(
    moto_id: str,
    km: int,
    origem: str = "manual",
    confirmar_km_menor: bool = False,
    chave_operacao: str | None = None,
) -> dict:
    """Registra novo km no histórico. O trigger do banco só sobe motos.km_atual;
    km menor que o atual exige confirmação explícita (serve para lançar dado antigo)."""
    moto = motos.obter(moto_id)
    if moto is None:
        raise ValueError("Veículo não encontrado.")

    if km < moto["km_atual"] and not confirmar_km_menor:
        raise ValueError(
            f"O km informado ({km}) é menor que o km atual do veículo ({moto['km_atual']}). "
            "Confirme se deseja registrar mesmo assim."
        )

    return historico_km.criar({"moto_id": moto_id, "km": km, "origem": origem}, chave_operacao)


def historico(moto_id):
    return historico_km.listar_por_moto(moto_id)


def pendencias_para_arquivar(moto_id: str) -> Pendencias:
    """O que impede arquivar o veículo (contrato ativo, manutenção aberta, cobrança em aberto)."""
    return arquivamento.pendencias_da_moto(
        moto_id, contratos.listar(), contratos.listar_vinculos(), manutencoes.listar(moto_id), cobrancas.listar()
    )


def arquivar(moto_id: str, motivo: str, vendida_em: date | None = None) -> dict:
    """Arquiva o veículo (ex.: vendido) se não houver pendências. O banco confere de novo na RPC."""
    moto = motos.obter(moto_id)
    if moto is None:
        raise ValueError("Veículo não encontrado.")
    if arquivamento.esta_arquivado(moto):
        raise ValueError("Este veículo já está arquivado.")
    if moto["status"] not in ("disponivel", "inativa"):
        raise ValueError("Só é possível arquivar veículos disponíveis ou inativos; este veículo está em uso.")
    pendencias = pendencias_para_arquivar(moto_id)
    if not pendencias.pode_arquivar:
        raise ValueError(arquivamento.texto_recusa(pendencias, "o veículo"))
    motivo = arquivamento.motivo_valido(motivo)
    return motos.arquivar_via_rpc(moto_id, motivo, vendida_em.isoformat() if motivo == "vendida" and vendida_em else None)


def desarquivar(moto_id: str) -> dict:
    return motos.desarquivar_via_rpc(moto_id)
