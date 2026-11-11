"""Documentos (dono): conferir o comprovante que o locatário enviou pelo portal: aceitar (regulariza) ou recusar com motivo."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.domain.valores import hoje_br
from tests.web.conftest import csrf_da_sessao, entrar

E1 = "00000000-0000-0000-0000-0000000000e1"  # IPVA vencido, sem envio aguardando
E2 = "00000000-0000-0000-0000-0000000000e2"  # seguro a vencer, COM envio aguardando
E4 = "00000000-0000-0000-0000-0000000000e4"  # regularizado
ENVIO = "00000000-0000-0000-0000-0000000000b1"


@pytest.fixture
def acoes(monkeypatch):
    from src.web import acoes_documentos

    s = SimpleNamespace(aceites=[], recusas=[], falhar=None, sugestao=None)

    def aceitar(envio_id, data):
        if s.falhar:
            raise s.falhar
        s.aceites.append((envio_id, data))
        return {"documento": {"id": E2}, "sugestao_proximo": s.sugestao}

    def recusar(envio_id, motivo):
        if s.falhar:
            raise s.falhar
        s.recusas.append((envio_id, motivo))

    monkeypatch.setattr(acoes_documentos, "documentos", SimpleNamespace(aceitar_comprovante=aceitar, recusar_comprovante=recusar))
    return s


def test_lista_destaca_o_documento_com_comprovante_a_conferir(cliente, base_documentos):
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert "1 comprovante(s) a conferir" in html and "Comprovante a conferir" in html
    assert f'href="/documentos/{E2}/comprovante-enviado"' in html and "Conferir comprovante" in html
    assert f'href="/documentos/{E1}/comprovante-enviado"' not in html  # só quem tem envio aguardando


def test_lista_sem_envios_nao_muda(cliente, base_documentos):
    base_documentos.envios.clear()
    entrar(cliente)
    html = cliente.get("/documentos").text
    assert "Comprovante a conferir" not in html and "comprovante(s) a conferir" not in html


def test_falha_ao_ler_os_envios_nao_derruba_a_lista(cliente, base_documentos, monkeypatch):
    from src.web import dados_documentos

    def quebra():
        raise RuntimeError("tabela inexistente")

    monkeypatch.setattr(dados_documentos.documentos, "comprovantes_aguardando", quebra)
    entrar(cliente)
    resposta = cliente.get("/documentos")
    assert resposta.status_code == 200 and "Documentos" in resposta.text and "Comprovante a conferir" not in resposta.text


def test_pagina_de_conferencia_mostra_quem_enviou_e_as_duas_acoes(cliente, base_documentos, acoes):
    entrar(cliente)
    html = cliente.get(f"/documentos/{E2}/comprovante-enviado").text
    assert "Conferir comprovante" in html and "Maria Souza" in html and "10/11/2026 12:30" in html
    assert "Paguei &lt;b&gt;hoje&lt;/b&gt;" in html and "<b>hoje</b>" not in html  # a observação do locatário é escapada
    assert f'href="/documentos/{E2}/comprovante-enviado/arquivo"' in html
    assert f'action="/documentos/{E2}/comprovante-enviado/aceitar"' in html and f'action="/documentos/{E2}/comprovante-enviado/recusar"' in html
    assert f'value="{hoje_br().isoformat()}"' in html and "Cadastrar em seguida o documento de 2027" in html


def test_documento_sem_envio_aguardando_explica(cliente, base_documentos, acoes):
    entrar(cliente)
    html = cliente.get(f"/documentos/{E1}/comprovante-enviado").text
    assert "Nenhum comprovante aguardando conferência" in html and "comprovante-enviado/aceitar" not in html


def test_abre_o_arquivo_por_url_assinada_sem_cache(cliente, base_documentos):
    entrar(cliente)
    r = cliente.get(f"/documentos/{E2}/comprovante-enviado/arquivo")
    assert r.status_code == 303 and r.headers["location"] == base_documentos.url_assinada + "portal/c1/arq.pdf?token=x"
    assert r.headers["Cache-Control"] == "no-store"
    assert cliente.get(f"/documentos/{E1}/comprovante-enviado/arquivo").status_code == 404
    assert cliente.get("/documentos/nao-e-uuid/comprovante-enviado/arquivo").status_code == 404


def test_aceitar_regulariza_e_volta_para_a_lista(cliente, base_documentos, acoes):
    entrar(cliente)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"csrf_token": csrf_da_sessao(cliente), "data": hoje_br().isoformat()})
    assert r.status_code == 303 and r.headers["location"] == "/documentos"
    assert acoes.aceites == [(ENVIO, hoje_br())]
    assert "marcado como regularizado" in cliente.get("/documentos").text


def test_aceitar_pedindo_o_proximo_leva_ao_cadastro_do_ano_seguinte(cliente, base_documentos, acoes):
    acoes.sugestao = {"tipo": "seguro", "ano_referencia": 2027, "vencimento": None, "regularizado": False}
    entrar(cliente)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar",
                     data={"csrf_token": csrf_da_sessao(cliente), "data": hoje_br().isoformat(), "criar_proximo": "on"})
    assert r.status_code == 303 and r.headers["location"].startswith("/documentos/novo?") and "tipo=seguro" in r.headers["location"] and "ano=2027" in r.headers["location"]


def test_aceitar_com_data_futura_ou_vazia_mostra_o_erro_e_nao_grava(cliente, base_documentos, acoes):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    futura = (hoje_br() + timedelta(days=1)).isoformat()
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"csrf_token": token, "data": futura})
    assert r.status_code == 422 and "não pode ser uma data futura" in r.text and f'value="{futura}"' in r.text
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"csrf_token": token, "data": ""})
    assert r.status_code == 422 and "informe uma data" in r.text and acoes.aceites == []


def test_aceitar_sem_envio_aguardando_ou_ja_conferido_avisa(cliente, base_documentos, acoes):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    r = cliente.post(f"/documentos/{E1}/comprovante-enviado/aceitar", data={"csrf_token": token, "data": hoje_br().isoformat()})
    assert r.status_code == 422 and "Não há comprovante aguardando conferência" in r.text
    acoes.falhar = ValueError("Este comprovante já foi conferido.")
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"csrf_token": token, "data": hoje_br().isoformat()})
    assert r.status_code == 422 and "já foi conferido" in r.text and acoes.aceites == []


def test_recusar_grava_o_motivo_e_volta_para_a_lista(cliente, base_documentos, acoes):
    entrar(cliente)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/recusar", data={"csrf_token": csrf_da_sessao(cliente), "motivo": "  Foto cortada  "})
    assert r.status_code == 303 and r.headers["location"] == "/documentos" and acoes.recusas == [(ENVIO, "Foto cortada")]
    assert "recusado" in cliente.get("/documentos").text


def test_recusar_sem_motivo_mostra_o_erro_no_campo(cliente, base_documentos, acoes):
    entrar(cliente)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/recusar", data={"csrf_token": csrf_da_sessao(cliente), "motivo": "ab"})
    assert r.status_code == 422 and "Motivo: explique o que está errado" in r.text and acoes.recusas == []


def test_recusar_o_que_ja_foi_conferido_avisa(cliente, base_documentos, acoes):
    acoes.falhar = ValueError("Este comprovante já foi conferido. Atualize a página.")
    entrar(cliente)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/recusar", data={"csrf_token": csrf_da_sessao(cliente), "motivo": "Foto cortada"})
    assert r.status_code == 422 and "já foi conferido" in r.text


def test_historico_mostra_envios_anteriores_com_motivo(cliente, base_documentos, acoes):
    base_documentos.historico[E2] = [
        {"id": "x2", "documento_id": E2, "status": "enviado", "enviado_em": "2026-11-10T15:30:00+00:00", "motivo_recusa": None, "clientes": {"nome": "Maria Souza"}},
        {"id": "x1", "documento_id": E2, "status": "recusado", "enviado_em": "2026-11-08T10:00:00+00:00", "motivo_recusa": "Foto cortada", "clientes": {"nome": "Maria Souza"}},
    ]
    entrar(cliente)
    html = cliente.get(f"/documentos/{E2}/comprovante-enviado").text
    assert "Histórico de comprovantes deste documento" in html and "Foto cortada" in html and "Recusado" in html and "Aguardando conferência" in html


def test_so_o_dono_com_csrf(cliente, base_documentos, acoes):
    assert cliente.get(f"/documentos/{E2}/comprovante-enviado").status_code in (302, 303)
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    assert cliente.get(f"/documentos/{E2}/comprovante-enviado", follow_redirects=False).status_code in (302, 303, 403)
    r = cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"csrf_token": "x", "data": hoje_br().isoformat()})
    assert r.status_code in (302, 303, 400, 403) and acoes.aceites == []
    cliente.cookies.clear()
    entrar(cliente)
    assert cliente.post(f"/documentos/{E2}/comprovante-enviado/aceitar", data={"data": hoje_br().isoformat()}).status_code in (400, 403)
    assert cliente.post(f"/documentos/{E2}/comprovante-enviado/recusar", data={"motivo": "Foto cortada"}).status_code in (400, 403)
    assert acoes.aceites == [] and acoes.recusas == []
