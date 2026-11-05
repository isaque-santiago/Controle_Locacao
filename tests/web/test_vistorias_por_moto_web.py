"""Vistoria por moto em contrato com várias motos: lista, comparação, pendentes e registro (entrega retroativa)."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.domain.valores import hoje_br
from src.domain.vistorias import CHECKLIST_PADRAO
from tests.web.conftest import CONTRATO_VISTORIAS, csrf_da_sessao, entrar

HX = {"HX-Request": "true"}
VINCULADA = "00000000-0000-0000-0000-0000000000b9"
VALOR = f"{CONTRATO_VISTORIAS}:{VINCULADA}"


@pytest.fixture
def com_vinculada(base_vistorias):
    """O contrato com vistorias ganha a moto vinculada m9 (QRS4T21), ainda sem vistoria."""
    base_vistorias.vinculos.append({"contrato_id": CONTRATO_VISTORIAS, "moto_id": VINCULADA})
    return base_vistorias


def _entrega_da_vinculada(base):
    registro = {"id": "00000000-0000-0000-0000-0000000000f9", "moto_id": VINCULADA, "contrato_id": CONTRATO_VISTORIAS,
                "tipo": "entrega", "data": "2026-08-01", "km": 5000, "nivel_combustivel": "cheio", "avarias": None,
                "checklist": {"farol_dianteiro": "ok"}, "fotos": []}
    base.registradas.append(registro)
    return registro


@pytest.fixture
def servico_vist(monkeypatch):
    from src.web import acoes_vistorias

    registros = []

    def registrar(contrato_id, moto_id, tipo, **dados):
        registros.append((contrato_id, moto_id, tipo, dados))
        return {"vistoria_id": "nova-1"}

    monkeypatch.setattr(acoes_vistorias, "vistorias", SimpleNamespace(
        registrar_vistoria=registrar, anexar_foto=lambda *a, **k: None))
    return registros


# ---------------------------------------------------------------- lista --

def test_lista_mostra_a_placa_da_moto_da_propria_vistoria(cliente, com_vinculada):
    _entrega_da_vinculada(com_vinculada)
    entrar(cliente)
    html = cliente.get("/vistorias").text
    assert "QRS-4T21" in html and "BRA-2E19" in html
    assert "QRS-4T21" in cliente.get("/vistorias?q=qrs").text and "BRA-2E19" not in cliente.get("/vistorias?q=qrs").text


# ----------------------------------------------------------- comparação --

def test_comparacao_mostra_um_grupo_por_moto_vinculada(cliente, com_vinculada):
    _entrega_da_vinculada(com_vinculada)
    entrar(cliente)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO_VISTORIAS}").text
    assert "moto principal" in html and "moto vinculada" in html and "QRS-4T21" in html
    assert html.count("vist-cartao") >= 3  # entrega e devolução da principal + a entrega da vinculada


def test_comparacao_oferece_registrar_a_devolucao_da_vinculada(cliente, com_vinculada):
    _entrega_da_vinculada(com_vinculada)
    entrar(cliente)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO_VISTORIAS}").text
    assert f"/vistorias/registrar?contrato={VALOR}" in html


def test_comparacao_de_contrato_de_uma_moto_nao_muda(cliente, base_vistorias):
    entrar(cliente)
    html = cliente.get(f"/vistorias/contrato/{CONTRATO_VISTORIAS}").text
    assert "moto principal" not in html and "moto vinculada" not in html


# ------------------------------------------------------------- pendentes --

def test_escolher_lista_a_moto_vinculada_sem_vistoria(cliente, com_vinculada):
    entrar(cliente)
    html = cliente.get("/vistorias/registrar", headers=HX).text
    assert f'value="{VALOR}"' in html and "QRS-4T21" in html and "vinculada" in html


def test_escolher_nao_lista_moto_vinculada_com_as_duas_vistorias(cliente, com_vinculada):
    base = com_vinculada
    entrega = _entrega_da_vinculada(base)
    base.registradas.append({**entrega, "id": "00000000-0000-0000-0000-0000000000fa", "tipo": "devolucao"})
    entrar(cliente)
    assert f'value="{VALOR}"' not in cliente.get("/vistorias/registrar", headers=HX).text


def test_entrega_da_principal_nao_vale_pela_vinculada(cliente, com_vinculada):
    """O contrato tem as duas vistorias da principal, mas a vinculada ainda não: continua pendente."""
    entrar(cliente)
    html = cliente.get("/vistorias/registrar", headers=HX).text
    assert f'value="{CONTRATO_VISTORIAS}"' not in html and f'value="{VALOR}"' in html


# -------------------------------------------------------------- registro --

def test_formulario_da_vinculada_traz_o_tipo_que_falta_e_o_km_dela(cliente, com_vinculada):
    entrar(cliente)
    html = cliente.get(f"/vistorias/registrar?contrato={VALOR}", headers=HX).text
    assert f'name="contrato" value="{VALOR}"' in html and "moto vinculada" in html
    assert "QRS-4T21" in html and 'value="5000"' in html and '<option value="entrega"' in html


def test_moto_fora_do_contrato_da_404(cliente, com_vinculada):
    entrar(cliente)
    assert cliente.get(f"/vistorias/registrar?contrato={CONTRATO_VISTORIAS}:m1x").status_code == 404
    outro = "00000000-0000-0000-0000-0000000000aa"
    assert cliente.get(f"/vistorias/registrar?contrato={CONTRATO_VISTORIAS}:{outro}").status_code == 404


def test_registra_a_entrega_retroativa_da_vinculada(cliente, com_vinculada, servico_vist):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    dados = {"csrf_token": token, "contrato": VALOR, "tipo": "entrega", "data": (hoje_br() - timedelta(days=1)).isoformat(),
             "km": "5050", "nivel_combustivel": "1/2", "avarias": "", "adicionais": "",
             **{"item_" + i: "ok" for i in CHECKLIST_PADRAO}}
    resposta = cliente.post("/vistorias/registrar", data=dados, headers=HX)
    assert resposta.status_code == 200
    ((contrato_id, moto_id, tipo, extra),) = servico_vist
    assert (contrato_id, moto_id, tipo) == (CONTRATO_VISTORIAS, VINCULADA, "entrega") and extra["km"] == 5050
    assert resposta.headers["HX-Redirect"] == f"/vistorias/contrato/{CONTRATO_VISTORIAS}"


def test_km_menor_que_o_atual_da_vinculada_e_recusado(cliente, com_vinculada, servico_vist):
    entrar(cliente)
    token = csrf_da_sessao(cliente)
    dados = {"csrf_token": token, "contrato": VALOR, "tipo": "entrega", "data": hoje_br().isoformat(),
             "km": "10", "nivel_combustivel": "1/2", "avarias": "", "adicionais": "",
             **{"item_" + i: "ok" for i in CHECKLIST_PADRAO}}
    resposta = cliente.post("/vistorias/registrar", data=dados, headers=HX)
    assert servico_vist == [] and resposta.status_code == 422
