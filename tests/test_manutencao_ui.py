"""Tela de Manutenção: alertas, histórico, catálogo e diálogo de registro."""

from decimal import Decimal

from tests.test_telas_dados import abrir, servicos  # noqa: F401  (fixture)

ALERTAS = [
    {
        "moto_id": "m", "placa": "ABC1D23", "modelo": "CG", "km_atual": 18420,
        "item_id": "i", "item": "Pneu traseiro", "proxima_km": 19000, "proxima_data": None,
        "km_restantes": 580, "dias_restantes": None, "situacao": "proxima",
    },
    {
        "moto_id": "m", "placa": "ABC1D23", "modelo": "CG", "km_atual": 18420,
        "item_id": "i2", "item": "Filtro de ar", "proxima_km": 18000, "proxima_data": None,
        "km_restantes": -420, "dias_restantes": None, "situacao": "vencida",
    },
    {
        "moto_id": "m", "placa": "ABC1D23", "modelo": "CG", "km_atual": 18420,
        "item_id": "i3", "item": "Em dia", "proxima_km": 30000, "proxima_data": None,
        "km_restantes": 11580, "dias_restantes": None, "situacao": "em_dia",
    },
]
HISTORICO = [
    {
        "id": "h1", "moto_id": "m", "tipo": "preventiva", "status": "aberta",
        "data_entrada": "2026-09-01", "descricao": "Revisão", "oficina": "Central",
        "km": 100, "custo_total": Decimal("95.00"),
    },
    {
        "id": "h2", "moto_id": "m", "tipo": "corretiva", "status": "concluida",
        "data_entrada": "2026-08-01", "descricao": "Buzina", "oficina": None,
        "km": 90, "custo_total": Decimal("60.00"),
    },
]


def test_cabecalho_e_alertas_ordenados(servicos):
    servicos["alertas.listar_manutencao"].return_value = ALERTAS
    servicos["manutencao.listar_manutencoes"].return_value = HISTORICO
    app = abrir("6_Manutencao.py")
    assert not app.exception and not app.error
    assert [t.label for t in app.tabs] == ["Alertas", "Histórico", "Catálogo"]
    texto = " ".join(m.value for m in app.markdown)
    assert "1 vencida(s) · 1 próxima(s)" in texto
    assert texto.index("Filtro de ar") < texto.index("Pneu traseiro")
    assert "Em dia" not in texto.split("Filtro de ar")[1].split("Situação")[0]
    assert "-420 km" in texto


def test_historico_permite_concluir_so_manutencao_aberta(servicos):
    servicos["manutencao.listar_manutencoes"].return_value = HISTORICO
    app = abrir("6_Manutencao.py")
    botoes = [b.key for b in app.button if b.key and b.key.startswith("concluir_man_")]
    assert botoes == ["concluir_man_h1"]


def test_dialogo_registrar_abre_com_previa_de_custo(servicos):
    app = abrir("6_Manutencao.py")
    next(b for b in app.button if b.label == "+ Registrar manutenção").click().run()
    assert not app.exception and not app.error
    assert any(b.label == "Salvar manutenção" for b in app.button)
    texto = " ".join(m.value for m in app.markdown)
    assert "custo total" in texto
