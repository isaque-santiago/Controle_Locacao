"""Remove dados pessoais das fotos antes de guardá-las (localização e identificação do aparelho).

Fotos de câmera trazem nos metadados EXIF a posição por GPS, a marca e o modelo do aparelho, números de série e até uma
miniatura. Só ficam a data da foto e a orientação (para a imagem aparecer de pé). A limpeza não recodifica a imagem: os
dados dos pixels seguem iguais, byte a byte; só os metadados são reescritos ou descartados.

JPEG: o bloco EXIF é refeito só com a lista de permitidos; XMP, IPTC, comentários e blocos de fabricante (APP2 a APP15, salvo
perfil de cor ICC e Adobe) são descartados. PNG: saem os blocos de
texto e de EXIF. PDF e outros tipos passam sem alteração.
"""

import io
import struct
from pathlib import PurePath

from PIL import Image

_ORIENTACAO = 0x0112
_DATA_HORA = 0x0132
_IFD_EXIF = 0x8769
_PERMITIDOS_IFD0 = (_ORIENTACAO, _DATA_HORA)
# Data/hora original, digitalizada e os fusos (OffsetTime*) das duas datas.
_PERMITIDOS_EXIF = (0x9003, 0x9004, 0x9010, 0x9011, 0x9012)

_PREFIXO_EXIF = b"Exif\x00\x00"
_PREFIXO_XMP = b"http://ns.adobe.com/xap/"
_PREFIXO_ICC = b"ICC_PROFILE\x00"  # perfil de cor: sem ele as cores mudam
_PREFIXO_ADOBE = b"Adobe"  # APP14: diz como decodificar as cores (CMYK/YCCK)
_BLOCOS_PNG_REMOVIDOS = (b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME")


class ImagemInvalida(ValueError):
    """O arquivo não pôde ser lido como a imagem que diz ser (não é guardado, para não vazar metadados)."""


def _exif_limpo(carga: bytes) -> bytes | None:
    """Novo bloco EXIF só com orientação e datas, ou None quando não sobra nada."""
    try:
        original = Image.Exif()
        original.load(carga)
        novo = Image.Exif()
        for tag in _PERMITIDOS_IFD0:
            if tag in original:
                novo[tag] = original[tag]
        origem_exif = original.get_ifd(_IFD_EXIF)
        destino_exif = {tag: origem_exif[tag] for tag in _PERMITIDOS_EXIF if tag in origem_exif}
        if destino_exif:
            novo.get_ifd(_IFD_EXIF).update(destino_exif)
        dados = novo.tobytes()
    except Exception as erro:
        raise ImagemInvalida("Não foi possível ler os metadados da foto.") from erro
    return dados if len(dados) > len(_PREFIXO_EXIF) + 8 else None


def _limpar_jpeg(conteudo: bytes) -> bytes:
    if conteudo[:2] != b"\xff\xd8":
        raise ImagemInvalida("Arquivo JPEG inválido.")
    saida = bytearray(b"\xff\xd8")
    pos = 2
    tamanho = len(conteudo)
    while pos < tamanho:
        if conteudo[pos] != 0xFF:
            raise ImagemInvalida("Arquivo JPEG inválido.")
        while pos < tamanho and conteudo[pos] == 0xFF:  # bytes de preenchimento antes do marcador
            pos += 1
        if pos >= tamanho:
            break
        marcador = conteudo[pos]
        pos += 1
        if marcador == 0xDA or marcador == 0xD9:  # início dos dados da imagem (SOS) ou fim: o resto é cópia fiel
            saida += bytes([0xFF, marcador]) + conteudo[pos:]
            return bytes(saida)
        if marcador == 0x01 or 0xD0 <= marcador <= 0xD8:  # marcadores sem tamanho
            saida += bytes([0xFF, marcador])
            continue
        if pos + 2 > tamanho:
            raise ImagemInvalida("Arquivo JPEG truncado.")
        comprimento = struct.unpack(">H", conteudo[pos : pos + 2])[0]
        fim = pos + comprimento
        if comprimento < 2 or fim > tamanho:
            raise ImagemInvalida("Arquivo JPEG truncado.")
        carga = conteudo[pos + 2 : fim]
        pos = fim
        if marcador == 0xE1 and carga.startswith(_PREFIXO_EXIF):
            novo = _exif_limpo(carga)
            if novo is not None:
                saida += b"\xff\xe1" + struct.pack(">H", len(novo) + 2) + novo
            continue
        if marcador == 0xE1 and carga.startswith(_PREFIXO_XMP):
            continue
        if marcador in (0xED, 0xFE):  # APP13 (IPTC/Photoshop) e comentários
            continue
        # Blocos de fabricante (APP2 a APP15 que não são perfil de cor nem Adobe) carregam marca e modelo (ex.: XIAOMI_CUSTOMIZE).
        if 0xE2 <= marcador <= 0xEF and not carga.startswith((_PREFIXO_ICC, _PREFIXO_ADOBE)):
            continue
        saida += bytes([0xFF, marcador]) + struct.pack(">H", comprimento) + carga
    raise ImagemInvalida("Arquivo JPEG sem dados de imagem.")


def _limpar_png(conteudo: bytes) -> bytes:
    assinatura = b"\x89PNG\r\n\x1a\n"
    if not conteudo.startswith(assinatura):
        raise ImagemInvalida("Arquivo PNG inválido.")
    saida = bytearray(assinatura)
    pos = len(assinatura)
    while pos < len(conteudo):
        if pos + 8 > len(conteudo):
            raise ImagemInvalida("Arquivo PNG truncado.")
        comprimento = struct.unpack(">I", conteudo[pos : pos + 4])[0]
        tipo = conteudo[pos + 4 : pos + 8]
        fim = pos + 12 + comprimento
        if fim > len(conteudo):
            raise ImagemInvalida("Arquivo PNG truncado.")
        if tipo not in _BLOCOS_PNG_REMOVIDOS:
            saida += conteudo[pos:fim]
        pos = fim
    return bytes(saida)


def remover_dados_pessoais(nome_arquivo: str, conteudo: bytes) -> bytes:
    """Devolve o arquivo sem GPS nem dados do aparelho (JPEG e PNG); outros tipos voltam como vieram."""
    extensao = PurePath(nome_arquivo).suffix.lower()
    if extensao in (".jpg", ".jpeg"):
        return _limpar_jpeg(conteudo)
    if extensao == ".png":
        return _limpar_png(conteudo)
    return conteudo


def metadados_restantes(conteudo: bytes) -> dict:
    """Etiquetas EXIF que sobraram (para testes e conferência): {nome do IFD: {tag: valor}}."""
    exif = Image.open(io.BytesIO(conteudo)).getexif()
    restante = {"principal": dict(exif)}
    restante["exif"] = dict(exif.get_ifd(_IFD_EXIF))
    restante["gps"] = dict(exif.get_ifd(0x8825))
    return restante
