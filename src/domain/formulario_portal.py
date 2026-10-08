"""Leitura e validação dos formulários do Portal do Locatário (troca de óleo e troca de senha).

Funções puras: recebem o que o navegador enviou e devolvem os dados prontos para o serviço, ou levantam
`ErroDeCampos` com uma mensagem por campo. As mesmas regras valem de novo no serviço e na RPC do banco: aqui elas
só fazem o erro aparecer ao lado do campo, antes de qualquer arquivo ir para o Storage."""

from decimal import Decimal

from src.domain.acesso_locatario import validar_nova_senha
from src.domain.arquivos import TAMANHO_MAXIMO_BYTES, validar_arquivo
from src.domain.formulario_moto import ErroDeCampos, _texto
from src.domain.troca_oleo import avaliar_troca_oleo, validar_km_informado

EXTENSOES_FOTO = (".jpg", ".jpeg", ".png")
BYTES_DA_ASSINATURA = 16  # o suficiente para conferir o formato real da imagem
ROTULO_ARQUIVO = {"foto": "Foto do painel", "nota": "Foto da nota fiscal"}
_DICA_ARQUIVO = {"foto": "mostrando o hodômetro", "nota": "do óleo"}


def texto_da_troca(entrada: dict) -> dict:
    return {"km": _texto(entrada, "km")}


def _validar_arquivo(campo: str, arquivo) -> str | None:
    """Mensagem de erro do arquivo do campo, ou None se está certo. `arquivo`: (nome, tamanho, cabeçalho) ou None."""
    rotulo = ROTULO_ARQUIVO[campo]
    if arquivo is None:
        return f"{rotulo}: anexe a foto {_DICA_ARQUIVO[campo]}."
    nome, tamanho, cabecalho = arquivo
    if tamanho > TAMANHO_MAXIMO_BYTES:
        return f"{rotulo}: a imagem tem mais de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB. Tire a foto de novo com menos qualidade."
    try:
        validar_arquivo(nome, cabecalho if tamanho > 0 else b"", EXTENSOES_FOTO)
    except ValueError as erro:
        return f"{rotulo}: {str(erro).rstrip('.')}."
    return None


def ler_troca_oleo(entrada: dict, contrato: dict, arquivos: dict, valor_multa) -> int:
    """Hodômetro informado (km), depois de conferir o texto, o km mínimo e as duas fotos.

    `arquivos`: {"foto": (nome, tamanho, cabeçalho) | None, "nota": ...}. Levanta `ErroDeCampos` com todos os erros."""
    erros: dict[str, str] = {}
    km = None
    try:
        km = validar_km_informado(_texto(entrada, "km"))
        avaliar_troca_oleo(km, contrato["km_atual"], contrato.get("ultima_km"), contrato.get("intervalo_km"), Decimal(str(valor_multa)))
    except ValueError as erro:
        erros["km"] = str(erro)
    for campo in ("foto", "nota"):
        mensagem = _validar_arquivo(campo, arquivos.get(campo))
        if mensagem:
            erros[campo] = mensagem
    if erros:
        raise ErroDeCampos(erros)
    return km


def ler_nova_senha(nova: str, confirmacao: str, cpf: str) -> str:
    """Nova senha conferida (8+ caracteres, letras e números, sem o CPF). O erro vai para o campo certo."""
    try:
        return validar_nova_senha(nova, confirmacao, cpf)
    except ValueError as erro:
        campo = "confirmacao" if "conferem" in str(erro) else "nova"
        raise ErroDeCampos({campo: str(erro)}) from None
