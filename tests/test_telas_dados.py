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
            "cobrancas.calcular_encargos_cobranca": {
                "multa": Decimal(2),
                "juros": Decimal(1),
                "total": Decimal(63),
            },
            "manutencao.listar_catalogo": [ITEM],
            "manutencao.listar_manutencoes": [],
            "manutencao.listar_plano_moto": [],
            "documentos.listar_por_moto": [
                {
                    "id": "d",
                    "tipo": "ipva",
                    "vencimento": "2026-09-01",
                    "regularizado": False,
                    "moto_id": "m",
                    "ano_referencia": 2026,
                }
            ],
            "vistorias.listar_por_contrato": [
                {"id": "v", "tipo": "entrega", "km": 100, "fotos": []}
            ],
            "vistorias.comparar_entrega_devolucao": {"diferencas": None},
            "alertas.listar_manutencao": [],
            "alertas.listar_documentos": [],
            "alertas.listar_cnh": [],
            "relatorios.resultado_por_moto": {"resultado": [], "fluxo": []},
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


def test_pagamento_parcial_envia_principal_separado(servicos):
    app = abrir("5_Cobrancas.py")
    next(e for e in app.text_input if e.label == "Principal recebido (R$)").set_value(
        "30,50"
    )
    next(b for b in app.button if b.label == "Registrar pagamento").click().run()
    assert not app.error
    assert servicos["cobrancas.registrar_pagamento"].call_args.args[2:4] == (
        Decimal("30.50"),
        Decimal("3.00"),
    )
