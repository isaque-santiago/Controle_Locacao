"""Leitura e validação dos formulários de moto (cadastro, edição, km e regularização de documento).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

import re
from datetime import date

from src.domain.entradas import (
    REGEX_PLACA,
    decimal_campo,
    inteiro_campo,
    normalizar_placa,
)

ANO_MINIMO = 1900
ANO_MAXIMO = 2100


class ErroDeCampos(ValueError):
    """Um ou mais campos inválidos: `erros` mapeia o nome do campo à mensagem."""

    def __init__(self, erros: dict[str, str]):
        super().__init__("; ".join(erros.values()))
        self.erros = erros


def _texto(entrada: dict, campo: str) -> str:
    return str(entrada.get(campo) or "").strip()


def _opcional(entrada: dict, campo: str) -> str | None:
    return _texto(entrada, campo) or None


def _sem_milhar(texto: str) -> str:
    """'12.345' ou '12 345' -> '12345' (km e anos podem vir com ponto de milhar)."""
    return re.sub(r"[.\s]", "", texto)


def _coletar(erros: dict, campo: str, funcao, *args, **kwargs):
    try:
        return funcao(*args, **kwargs)
    except ValueError as erro:
        erros[campo] = str(erro)
        return None


def _data_iso(texto: str, rotulo: str, obrigatoria: bool) -> str | None:
    if not texto:
        if obrigatoria:
            raise ValueError(f"{rotulo}: informe uma data.")
        return None
    try:
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        raise ValueError(f"{rotulo}: use uma data válida.") from None


def ler_moto(entrada: dict, nova: bool) -> dict:
    """Dados da moto prontos para `motos.criar` / `motos.atualizar`. Na edição não há `km_atual`
    (a quilometragem muda só pelo registro de leitura)."""
    erros: dict[str, str] = {}

    placa = _texto(entrada, "placa")
    if not re.fullmatch(REGEX_PLACA, placa):
        erros["placa"] = "Placa: use ABC1234 ou ABC1D23."

    marca = _texto(entrada, "marca")
    if not marca:
        erros["marca"] = "Marca: informe a marca da moto."
    modelo = _texto(entrada, "modelo")
    if not modelo:
        erros["modelo"] = "Modelo: informe o modelo da moto."

    ano_fabricacao = _coletar(
        erros, "ano_fabricacao", inteiro_campo,
        _sem_milhar(_texto(entrada, "ano_fabricacao")), "Ano de fabricação", ANO_MINIMO, ANO_MAXIMO,
    )
    ano_modelo = _coletar(
        erros, "ano_modelo", inteiro_campo,
        _sem_milhar(_texto(entrada, "ano_modelo")), "Ano do modelo", ANO_MINIMO, ANO_MAXIMO,
    )
    km_atual = None
    if nova:
        km_atual = _coletar(
            erros, "km_atual", inteiro_campo,
            _sem_milhar(_texto(entrada, "km_atual") or "0"), "Quilometragem inicial",
        )
    aquisicao = _coletar(erros, "valor_aquisicao", decimal_campo, entrada.get("valor_aquisicao"), "Valor de aquisição")
    locacao = _coletar(erros, "valor_locacao_sugerido", decimal_campo, entrada.get("valor_locacao_sugerido"), "Locação sugerida")
    data_aquisicao = _coletar(
        erros, "data_aquisicao", _data_iso, _texto(entrada, "data_aquisicao"), "Data de aquisição", False
    )

    if erros:
        raise ErroDeCampos(erros)

    dados = {
        "placa": normalizar_placa(placa),
        "marca": marca,
        "modelo": modelo,
        "renavam": _opcional(entrada, "renavam"),
        "chassi": _opcional(entrada, "chassi"),
        "cor": _opcional(entrada, "cor"),
        "ano_fabricacao": ano_fabricacao,
        "ano_modelo": ano_modelo,
        "valor_aquisicao": str(aquisicao),
        "valor_locacao_sugerido": str(locacao),
        "data_aquisicao": data_aquisicao,
        "observacoes": _opcional(entrada, "observacoes"),
    }
    if nova:
        dados["km_atual"] = km_atual
    return dados


def ler_km(entrada: dict) -> tuple[int, bool]:
    """(nova leitura em km, confirmou lançar leitura menor que a atual)."""
    erros: dict[str, str] = {}
    km = _coletar(erros, "km", inteiro_campo, _sem_milhar(_texto(entrada, "km")), "Nova leitura")
    if erros:
        raise ErroDeCampos(erros)
    return km, bool(entrada.get("confirmar_km_menor"))


def ler_regularizacao(entrada: dict) -> date:
    """Data em que o documento foi regularizado."""
    erros: dict[str, str] = {}
    texto = _coletar(erros, "data", _data_iso, _texto(entrada, "data"), "Data de regularização", True)
    if erros:
        raise ErroDeCampos(erros)
    return date.fromisoformat(texto)
