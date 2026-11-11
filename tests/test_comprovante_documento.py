"""Testes de src/domain/comprovante_documento.py: envio do locatário, recusa e aceite do dono, rótulos e alerta."""

from datetime import date

import pytest

from src.domain.comprovante_documento import (
    STATUS_ROTULO, STATUS_TOM, alertas_de_comprovantes, ler_aceite, ler_envio, ler_recusa, nome_do_documento, pode_enviar,
)
from src.domain.formulario_moto import ErroDeCampos

PDF = ("comprovante.pdf", 2048, b"%PDF-1.7 corpo")
JPG = ("foto.JPG", 4096, b"\xff\xd8\xff\xe0\x00\x10JFIF")


def test_nome_do_documento():
    assert nome_do_documento("ipva", None, 2026) == "IPVA 2026"
    assert nome_do_documento("seguro") == "Seguro"
    assert nome_do_documento("outro", "Taxa do rastreador", 2026) == "Taxa do rastreador"
    assert nome_do_documento("outro", None, None) == "Outro"
    assert nome_do_documento("desconhecido") == "desconhecido"


def test_pode_enviar_so_sem_envio_aguardando():
    assert pode_enviar({}) and pode_enviar({"envio_status": None})
    assert pode_enviar({"envio_status": "recusado"}) and pode_enviar({"envio_status": "aceito"})
    assert not pode_enviar({"envio_status": "enviado"})


@pytest.mark.parametrize("arquivo", [PDF, JPG])
def test_envio_valido_devolve_a_observacao_aparada(arquivo):
    assert ler_envio({"observacao": "  Paguei hoje  "}, arquivo) == "Paguei hoje"
    assert ler_envio({}, arquivo) is None


def test_envio_sem_arquivo():
    with pytest.raises(ErroDeCampos) as erro:
        ler_envio({}, None)
    assert erro.value.erros == {"comprovante": "Comprovante: anexe a foto ou o PDF do comprovante."}


@pytest.mark.parametrize("arquivo, trecho", [
    (("c.exe", 100, b"MZ.."), "Extensão não permitida"),
    (("c.pdf", 100, b"nao e pdf"), "não corresponde à extensão"),
    (("c.pdf", 0, b""), "Arquivo vazio"),
    (("c.pdf", 11 * 1024 * 1024, b"%PDF-"), "mais de 10 MB"),
])
def test_envio_com_arquivo_ruim(arquivo, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        ler_envio({}, arquivo)
    assert erro.value.erros["comprovante"].startswith("Comprovante: ") and trecho in erro.value.erros["comprovante"]


def test_observacao_longa_e_arquivo_ruim_aparecem_juntos():
    with pytest.raises(ErroDeCampos) as erro:
        ler_envio({"observacao": "x" * 201}, ("c.exe", 1, b"MZ"))
    assert set(erro.value.erros) == {"comprovante", "observacao"}
    assert "200" in erro.value.erros["observacao"]
    assert ler_envio({"observacao": "x" * 200}, PDF) == "x" * 200


def test_recusa_exige_motivo_de_3_a_200_letras():
    assert ler_recusa({"motivo": "  Foto cortada  "}) == "Foto cortada"
    for ruim in ("", "ab", "x" * 201):
        with pytest.raises(ErroDeCampos) as erro:
            ler_recusa({"motivo": ruim})
        assert erro.value.erros["motivo"].startswith("Motivo:")


HOJE = date(2026, 11, 12)


def test_aceite_com_data_de_hoje_ou_passada():
    assert ler_aceite({"data": "2026-11-12"}, HOJE) == {"data": HOJE, "criar_proximo": False}
    assert ler_aceite({"data": "2026-11-01", "criar_proximo": "on"}, HOJE) == {"data": date(2026, 11, 1), "criar_proximo": True}


@pytest.mark.parametrize("data, trecho", [("", "informe uma data"), ("2026-11-13", "futura"), ("12/11/2026", "")])
def test_aceite_com_data_invalida(data, trecho):
    with pytest.raises(ErroDeCampos) as erro:
        ler_aceite({"data": data}, HOJE)
    assert "data" in erro.value.erros and trecho in erro.value.erros["data"]


def test_rotulos_e_tons_cobrem_todas_as_situacoes():
    assert set(STATUS_ROTULO) == set(STATUS_TOM) == {"enviado", "aceito", "recusado"}


def test_alerta_do_dashboard():
    assert alertas_de_comprovantes([]) == []
    um = alertas_de_comprovantes([{"cliente": "Maria", "documento": "IPVA 2026 · ABC-1D23"}])[0]
    assert (um.quantidade, um.titulo, um.tom, um.area) == (1, "Comprovante a conferir", "atencao", "documentos")
    assert um.descricao == "Maria · IPVA 2026 · ABC-1D23"
    varios = alertas_de_comprovantes([{"cliente": "Maria", "documento": "IPVA"}, {"cliente": "João", "documento": "Seguro"}])[0]
    assert varios.quantidade == 2 and varios.descricao == "Maria · IPVA e mais 1"
