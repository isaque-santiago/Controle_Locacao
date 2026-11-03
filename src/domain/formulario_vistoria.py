"""Leitura e validação do registro de vistoria (página Vistorias) e das fotos enviadas.

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo."""

from datetime import date

from src.domain.arquivos import TAMANHO_MAXIMO_BYTES, validar_arquivo
from src.domain.formulario_contrato import _juntar, ler_vistoria, texto_da_vistoria, vistoria_inicial
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto
from src.domain.vistorias import NIVEIS_COMBUSTIVEL

LIMITE_FOTOS = 10  # por envio
EXTENSOES_FOTO = (".jpg", ".jpeg", ".png")
TIPOS_CONTEUDO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
BYTES_DA_ASSINATURA = 16  # o suficiente para conferir o formato real do arquivo


def registro_inicial(hoje: date, km_atual: int, faltantes: list[str]) -> dict:
    """Texto inicial do formulário: o primeiro tipo que falta, hoje, km da moto e combustível cheio."""
    return {
        **vistoria_inicial(km_atual),
        "tipo": faltantes[0] if faltantes else "",
        "data": hoje.isoformat(),
        "nivel_combustivel": NIVEIS_COMBUSTIVEL[-1],
    }


def texto_do_registro(entrada: dict) -> dict:
    return {**texto_da_vistoria(entrada), "tipo": _texto(entrada, "tipo"), "data": _texto(entrada, "data")}


def ler_registro(entrada: dict, hoje: date, inicio_contrato, km_minimo: int, faltantes: list[str]) -> dict:
    """Registro pronto para o serviço: tipo, dia e vistoria. A data não pode ser futura nem anterior ao
    início do contrato; o km não pode ser menor que a leitura atual da moto."""
    erros: dict[str, str] = {}
    inicio = date.fromisoformat(str(inicio_contrato)[:10])
    tipo = _texto(entrada, "tipo")
    if tipo not in faltantes:
        erros["tipo"] = "Tipo: escolha um tipo de vistoria ainda não registrado neste contrato."
    texto_dia = _coletar(erros, "data", _data_iso, _texto(entrada, "data"), "Data", True)
    dia = date.fromisoformat(texto_dia) if texto_dia else None
    if dia and dia > hoje:
        erros["data"] = "Data: a vistoria não pode ser registrada com data futura."
    elif dia and dia < inicio:
        erros["data"] = f"Data: a vistoria não pode anteceder o início do contrato ({inicio.strftime('%d/%m/%Y')})."
    vistoria = _juntar(erros, ler_vistoria, entrada, km_minimo)
    if erros:
        raise ErroDeCampos(erros)
    return {"tipo": tipo, "dia": dia, "vistoria": {**vistoria, "avarias": vistoria["avarias"] or None}}


def validar_fotos(fotos: list[tuple[str, int, bytes]]) -> None:
    """`fotos`: (nome, tamanho em bytes, primeiros bytes). Confere quantidade, tamanho, extensão e formato real
    antes de gravar a vistoria, para o erro aparecer no campo e nada ficar pela metade."""
    if len(fotos) > LIMITE_FOTOS:
        raise ErroDeCampos({"fotos": f"Fotos: envie até {LIMITE_FOTOS} fotos por vez."})
    for nome, tamanho, cabecalho in fotos:
        if tamanho > TAMANHO_MAXIMO_BYTES:
            raise ErroDeCampos({"fotos": f"Fotos: {nome} tem mais de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB."})
        try:
            validar_arquivo(nome, cabecalho if tamanho > 0 else b"", EXTENSOES_FOTO)
        except ValueError as erro:
            raise ErroDeCampos({"fotos": f"Fotos: {nome}: {erro}"}) from None
