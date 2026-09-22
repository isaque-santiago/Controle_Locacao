"""Testes de src/domain/arquivos.py."""

import pytest

from src.domain.arquivos import TAMANHO_MAXIMO_BYTES, validar_arquivo

_PDF = b"%PDF-1.4\n..."
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
_JPEG = b"\xff\xd8\xff" + b"\x00" * 10
_PERMITIDAS = (".pdf", ".png", ".jpg", ".jpeg")


class TestValidarArquivo:
    def test_pdf_valido_passa(self):
        validar_arquivo("comprovante.pdf", _PDF, _PERMITIDAS)

    def test_png_valido_passa(self):
        validar_arquivo("foto.png", _PNG, _PERMITIDAS)

    def test_jpeg_valido_passa(self):
        validar_arquivo("foto.jpeg", _JPEG, _PERMITIDAS)

    def test_arquivo_vazio_recusado(self):
        with pytest.raises(ValueError, match="vazio"):
            validar_arquivo("comprovante.pdf", b"", _PERMITIDAS)

    def test_arquivo_maior_que_limite_recusado(self):
        conteudo = b"%PDF-" + b"\x00" * TAMANHO_MAXIMO_BYTES
        with pytest.raises(ValueError, match="MB"):
            validar_arquivo("comprovante.pdf", conteudo, _PERMITIDAS)

    def test_extensao_fora_da_lista_recusada(self):
        with pytest.raises(ValueError, match="Extensão"):
            validar_arquivo("script.exe", _PDF, _PERMITIDAS)

    def test_extensao_maiuscula_e_normalizada(self):
        validar_arquivo("COMPROVANTE.PDF", _PDF, _PERMITIDAS)

    def test_conteudo_nao_bate_com_extensao_recusado(self):
        # nome diz .pdf, mas o conteúdo é de um PNG — content_type do
        # navegador poderia mentir aqui; a assinatura binária não.
        with pytest.raises(ValueError, match="não corresponde"):
            validar_arquivo("comprovante.pdf", _PNG, _PERMITIDAS)

    def test_extensao_sem_assinatura_conhecida_nao_bloqueia(self):
        # extensão fora do mapa de assinaturas (não é o caso hoje, mas a
        # função não deve quebrar se um dia isso acontecer).
        validar_arquivo("nota.txt", b"qualquer coisa", (".txt",))
