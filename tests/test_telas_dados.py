"""Exercita renderização e gravação de formulários com dados representativos."""

from contextlib import ExitStack
from time import time
from unittest.mock import patch
from pathlib import Path
from decimal import Decimal
import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
MOTO = {
    "id": "m",
    "placa": "ABC1D23",
    "marca": "Honda",
    "modelo": "CG",
    "km_atual": 100,
    "status": "disponivel",
}
CLIENTE = {"id": "cl", "nome": "Pessoa teste", "cpf": "52998224725", "status": "ativo"}
CONTRATO = {
    "id": "ct",
    "moto_id": "m",
    "cliente_id": "cl",
    "data_inicio": "2026-09-01",
    "data_fim_prevista": "2026-10-01",
    "data_encerramento": None,
    "status": "ativo",
    "km_inicial": 100,
    "km_final": None,
    "periodicidade": "mensal",
    "valor_periodo": Decimal("100"),
    "caucao_valor": Decimal("0"),
    "caucao_devolvida": False,
}
COBRANCA = {
    "id": "c",
    "contrato_id": "ct",
    "moto_id": "m",
    "cliente_id": "cl",
    "tipo": "locacao",
    "vencimento": "2026-09-01",
    "valor": 100,
    "saldo": 60,
    "valor_pago": 40,
    "situacao": "atrasada",
}
DOCUMENTO = {
    "id": "d",
    "tipo": "ipva",
    "vencimento": "2026-09-01",
    "regularizado": False,
    "moto_id": "m",
    "ano_referencia": 2026,
    "valor": Decimal("380.00"),
    "descricao": None,
    "arquivo_path": None,
}
ITEM = {
    "id": "i",
    "nome": "Óleo",
    "ativo": True,
    "intervalo_km": 1000,
    "intervalo_dias": 90,
}


@pytest.fixture
def servicos():
    with ExitStack() as pilha:
        retornos = {
            "motos.listar": [MOTO],
            "motos.historico": [],
            "clientes.listar": [CLIENTE],
            "contratos.listar": [CONTRATO],
            "cobrancas.listar": [COBRANCA],
            "cobrancas.listar_por_contrato": [COBRANCA],
            "cobrancas.historico_pagamentos": [],
            "cobrancas.historicos_pagamentos": {},
            "cobrancas.configuracao_encargos": {},
            "cobrancas.calcular_encargos_cobranca": {
                "dias_atraso": 22,
                "multa": Decimal(2),
                "juros": Decimal(1),
                "total": Decimal(63),
            },
            "manutencao.listar_catalogo": [ITEM],
            "manutencao.listar_manutencoes": [],
            "manutencao.listar_plano_moto": [],
            "documentos.listar_todos": [DOCUMENTO],
            "documentos.listar_por_moto": [DOCUMENTO],
            "vistorias.listar_por_contrato": [
                {"id": "v", "tipo": "entrega", "km": 100, "fotos": [], "data": "2026-09-01T10:00:00+00:00", "nivel_combustivel": "cheio", "checklist": {}}
            ],
            "vistorias.listar": [
                {"id": "v", "contrato_id": "ct", "tipo": "entrega", "km": 100, "fotos": [], "data": "2026-09-01T10:00:00+00:00", "nivel_combustivel": "cheio", "checklist": {}}
            ],
            "vistorias.comparar_entrega_devolucao": {
                "entrega": None,
                "devolucao": None,
                "diferencas": None,
            },
            "alertas.listar_manutencao": [],
            "alertas.listar_documentos": [],
            "alertas.listar_cnh": [],
            "relatorios.resultado_por_moto": {"resultado": [], "fluxo": []},
            "relatorios.inadimplencia": {
                "linhas": [],
                "total_atraso": Decimal(0),
                "clientes": 0,
                "percentual_carteira": None,
            },
            "motos.criar": MOTO,
            "clientes.criar": CLIENTE,
            "cobrancas.registrar_pagamento": {},
            "configuracoes.obter": {
                "multa_atraso_percentual": 2,
                "juros_mensal_percentual": 1,
                "carencia_dias": 0,
                "alerta_manutencao_km": 300,
                "alerta_manutencao_dias": 15,
                "alerta_documento_dias": 30,
                "alerta_cnh_dias": 30,
            },
        }
        mocks = {
            nome: pilha.enter_context(
                patch("src.services." + nome, return_value=retorno)
            )
            for nome, retorno in retornos.items()
        }
        yield mocks


def abrir(nome):
    app = AppTest.from_file(str(RAIZ / "pages" / nome), default_timeout=20)
    app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
    app.session_state["ultima_atividade"] = time()
    return app.run()


@pytest.mark.parametrize(
    "nome",
    [
        "2_Motos.py",
        "3_Clientes.py",
        "4_Contratos.py",
        "5_Cobrancas.py",
        "6_Manutencao.py",
        "7_Documentos.py",
        "8_Vistorias.py",
        "9_Relatorios.py",
    ],
)
def test_paginas_com_dados(servicos, nome):
    app = abrir(nome)
    assert not app.exception
    assert not app.error, [e.value for e in app.error]


def test_dialog_nova_moto_abre_com_campos_do_formulario(servicos):
    app = abrir("2_Motos.py")
    next(b for b in app.button if b.label == "+ Nova moto").click().run()
    assert not app.error
    rotulos = {entrada.label for entrada in app.text_input}
    assert {"Placa", "Marca", "Modelo", "Valor de aquisição (R$)"} <= rotulos
    assert any(b.label == "Salvar moto" for b in app.button)


def _abrir_dialogo_pagamento():
    def roteiro():
        from src.ui.cobrancas import _dialog_pagamento

        _dialog_pagamento(
            {
                "id": "c",
                "tipo": "locacao",
                "vencimento": "2026-09-01",
                "saldo": 60,
                "placa": "ABC1D23",
                "cliente": "Pessoa teste",
            }
        )

    return AppTest.from_function(roteiro, default_timeout=20).run()


def test_pagamento_parcial_envia_principal_separado(servicos):
    app = _abrir_dialogo_pagamento()
    next(e for e in app.text_input if e.label == "Principal recebido (R$)").set_value(
        "30,50"
    )
    next(b for b in app.button if b.label == "Confirmar pagamento").click().run()
    assert not app.error
    assert servicos["cobrancas.registrar_pagamento"].call_args.args[2:4] == (
        Decimal("30.50"),
        Decimal("3.00"),
    )


def test_cobranca_rapida_do_dashboard_abre_o_dialogo_de_pagamento(servicos):
    app = AppTest.from_file(str(RAIZ / "pages" / "5_Cobrancas.py"), default_timeout=20)
    app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
    app.session_state["ultima_atividade"] = time()
    app.session_state["cobranca_rapida"] = "c"
    app.run()
    assert not app.exception
    assert any(e.label == "Principal recebido (R$)" for e in app.text_input)


def test_contrato_indicado_por_outra_ficha_fica_selecionado(servicos):
    app = AppTest.from_file(str(RAIZ / "pages" / "4_Contratos.py"), default_timeout=20)
    app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
    app.session_state["ultima_atividade"] = time()
    app.session_state["contratos_visao"] = "ficha"
    app.session_state["contratos_id_selecionado"] = "ct"
    app.run()

    assert [t.label for t in app.tabs] == ["Cobranças", "Vistorias", "Manutenções"]
    assert not app.error


def test_relatorios_renderiza_abas_com_dados_e_alterna_custo(servicos):
    servicos["relatorios.resultado_por_moto"].return_value = {
        "resultado": [
            {
                "moto_id": "m",
                "placa": "ABC1D23",
                "modelo": "CG",
                "receita_recebida": Decimal("1000.00"),
                "custo_manutencao": Decimal("100.00"),
                "custo_documentos": Decimal("50.00"),
                "km_rodados": 500,
                "custo_por_km": Decimal("0.20"),
                "resultado": Decimal("850.00"),
            }
        ],
        "fluxo": [
            {
                "mes": "2026-09",
                "receita_recebida": Decimal("1000.00"),
                "custo_manutencao": Decimal("100.00"),
                "custo_documentos": Decimal("50.00"),
                "resultado": Decimal("850.00"),
            }
        ],
    }
    servicos["relatorios.inadimplencia"].return_value = {
        "linhas": [
            {
                "cliente": "Pessoa teste",
                "placa": "ABC1D23",
                "vencimento": "2026-09-01",
                "dias_atraso": 22,
                "saldo": Decimal("60.00"),
                "total_com_encargos": Decimal("63.00"),
            }
        ],
        "total_atraso": Decimal("60.00"),
        "clientes": 1,
        "percentual_carteira": Decimal("6.0"),
    }
    app = abrir("9_Relatorios.py")
    assert not app.exception and not app.error
    html = " ".join(m.value for m in app.markdown)
    assert "R$ 850,00" in html and "Setembro de 2026" in html
    assert "R$ 63,00" in html and "6,0%" in html
    next(b for b in app.button if b.label == "Por moto").click().run()
    assert not app.exception and not app.error
    assert "R$ 0,20" in " ".join(m.value for m in app.markdown)
