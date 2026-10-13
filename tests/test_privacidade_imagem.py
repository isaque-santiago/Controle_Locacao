"""Fotos guardadas sem GPS nem dados do aparelho, mantendo data e orientação (Fase 4, parte E)."""

import io
import struct

import pytest
from PIL import Image

from src.domain.privacidade_imagem import ImagemInvalida, metadados_restantes, remover_dados_pessoais


def _jpeg_com_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Xiaomi"  # fabricante
    exif[0x0110] = "23013PC75G"  # modelo
    exif[0x0131] = "MIUI Camera"  # programa
    exif[0x0112] = 6  # orientação
    exif[0x0132] = "2026:10:13 09:30:00"
    exif.get_ifd(0x8769).update({0x9003: "2026:10:13 09:30:00", 0xA431: "SERIAL123", 0xA434: "Lente do aparelho"})
    exif.get_ifd(0x8825).update({1: "S", 2: (23.0, 33.0, 12.0), 3: "W", 4: (46.0, 38.0, 1.0)})
    imagem = Image.effect_noise((64, 48), 80).convert("RGB")
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", exif=exif.tobytes(), quality=90)
    return saida.getvalue()


def test_a_foto_de_teste_realmente_traz_gps_e_aparelho():
    meta = metadados_restantes(_jpeg_com_exif())
    assert meta["gps"] and meta["principal"][0x010F] == "Xiaomi" and meta["exif"][0xA431] == "SERIAL123"


def test_jpeg_perde_gps_e_aparelho_mas_mantem_data_e_orientacao():
    limpo = remover_dados_pessoais("foto.jpg", _jpeg_com_exif())
    meta = metadados_restantes(limpo)
    assert meta["gps"] == {}
    for tag in (0x010F, 0x0110, 0x0131):
        assert tag not in meta["principal"]
    assert 0xA431 not in meta["exif"] and 0xA434 not in meta["exif"]
    assert meta["principal"][0x0112] == 6
    assert meta["principal"][0x0132] == "2026:10:13 09:30:00"
    assert meta["exif"][0x9003] == "2026:10:13 09:30:00"


def test_jpeg_nao_e_recodificado_os_pixels_ficam_iguais():
    original = _jpeg_com_exif()
    limpo = remover_dados_pessoais("FOTO.JPEG", original)
    assert list(Image.open(io.BytesIO(limpo)).getdata()) == list(Image.open(io.BytesIO(original)).getdata())
    # tudo a partir do início dos dados da imagem (SOS) é cópia fiel
    assert limpo[limpo.index(b"\xff\xda") :] == original[original.index(b"\xff\xda") :]


def test_jpeg_sem_exif_passa_igual():
    simples = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(simples, "JPEG")
    assert remover_dados_pessoais("a.jpg", simples.getvalue()) == simples.getvalue()


def test_jpeg_perde_xmp_e_comentarios():
    original = _jpeg_com_exif()
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>gps</x:xmpmeta>"
    comentario = b"tirada em casa"
    inserido = (
        original[:2]
        + b"\xff\xe1" + struct.pack(">H", len(xmp) + 2) + xmp
        + b"\xff\xfe" + struct.pack(">H", len(comentario) + 2) + comentario
        + original[2:]
    )
    limpo = remover_dados_pessoais("a.jpg", inserido)
    assert b"xmpmeta" not in limpo and b"tirada em casa" not in limpo


def test_png_perde_blocos_de_texto_e_exif():
    exif = Image.Exif()
    exif[0x010F] = "Xiaomi"
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Comentario", "localização secreta")
    saida = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(saida, "PNG", exif=exif.tobytes(), pnginfo=info)
    original = saida.getvalue()
    assert b"secreta" in original
    limpo = remover_dados_pessoais("a.png", original)
    assert b"secreta" not in limpo and b"eXIf" not in limpo and b"Xiaomi" not in limpo
    assert list(Image.open(io.BytesIO(limpo)).getdata()) == list(Image.open(io.BytesIO(original)).getdata())


def test_pdf_passa_sem_alteracao():
    assert remover_dados_pessoais("c.pdf", b"%PDF-1.4 conteudo") == b"%PDF-1.4 conteudo"


@pytest.mark.parametrize("nome,conteudo", [("a.jpg", b"\xff\xd8\xff\xe1\x00"), ("a.jpg", b"nao e jpeg"), ("a.png", b"\x89PNG\r\n\x1a\n\x00\x00")])
def test_arquivo_corrompido_e_recusado_em_vez_de_guardado_com_metadados(nome, conteudo):
    with pytest.raises(ImagemInvalida):
        remover_dados_pessoais(nome, conteudo)


def test_servicos_guardam_a_foto_ja_limpa(monkeypatch):
    from unittest.mock import patch

    from src.services import documentos, vistorias

    original = _jpeg_com_exif()
    with patch("src.services.vistorias.vistoria_fotos") as fotos:
        fotos.upload_foto.return_value = "v/1.jpg"
        vistorias.anexar_foto("vist1", "a.jpg", original, "image/jpeg")
    enviado = fotos.upload_foto.call_args.args[2]
    assert enviado != original and metadados_restantes(enviado)["gps"] == {}

    with patch("src.services.documentos.documentos_moto") as docs:
        docs.upload_comprovante.return_value = "d/1.jpg"
        documentos.anexar_comprovante("doc1", "moto1", "c.jpg", original, "image/jpeg")
    enviado = docs.upload_comprovante.call_args.args[3]
    assert enviado != original and metadados_restantes(enviado)["gps"] == {}
