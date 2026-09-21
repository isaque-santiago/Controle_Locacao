"""Orquestra cadastro de motos e atualização de quilometragem."""

from postgrest.exceptions import APIError

from src.domain.validadores import validar_placa
from src.repositories import historico_km, motos

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
                f"Já existe uma moto cadastrada com a placa {dados['placa']}."
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
                f"Já existe uma moto cadastrada com a placa {dados['placa']}."
            ) from erro
        raise


def atualizar_km(
    moto_id: str, km: int, origem: str = "manual", confirmar_km_menor: bool = False
) -> dict:
    """Registra novo km no histórico. O trigger do banco só sobe motos.km_atual;
    km menor que o atual exige confirmação explícita (serve para lançar dado antigo)."""
    moto = motos.obter(moto_id)
    if moto is None:
        raise ValueError("Moto não encontrada.")

    if km < moto["km_atual"] and not confirmar_km_menor:
        raise ValueError(
            f"O km informado ({km}) é menor que o km atual da moto ({moto['km_atual']}). "
            "Confirme se deseja registrar mesmo assim."
        )

    return historico_km.criar({"moto_id": moto_id, "km": km, "origem": origem})


def historico(moto_id):
    return historico_km.listar_por_moto(moto_id)
