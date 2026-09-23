"""Regras da tela Configurações: validação e exemplo de encargos."""

from decimal import Decimal

import pytest

from src.domain.configuracoes import exemplo_encargos, validar_configuracao

ENTRADA = {
    "multa_atraso_percentual": "2,00",
    "juros_mensal_percentual": "1,5",
    "carencia_dias": 0,
    "alerta_manutencao_km": 300,
    "alerta_manutencao_dias": 15,
    "alerta_documento_dias": 30,
    "alerta_cnh_dias": 30,
}


def test_validar_converte_percentuais_e_inteiros():
    dados = validar_configuracao(ENTRADA)
    assert dados["multa_atraso_percentual"] == "2.00"
    assert dados["juros_mensal_percentual"] == "1.50"
    assert dados["alerta_manutencao_km"] == 300


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("multa_atraso_percentual", "abc"),
        ("multa_atraso_percentual", "-1"),
        ("multa_atraso_percentual", "101"),
        ("juros_mensal_percentual", "1,234"),
        ("carencia_dias", "-3"),
        ("carencia_dias", "2,5"),
        ("alerta_cnh_dias", ""),
        ("alerta_manutencao_km", "999999999"),
    ],
)
def test_validar_rejeita_valores_invalidos(campo, valor):
    with pytest.raises(ValueError):
        validar_configuracao({**ENTRADA, campo: valor})


def test_exemplo_encargos_igual_ao_mockup():
    exemplo = exemplo_encargos(Decimal("2.00"), Decimal("1.00"), 0)
    assert exemplo["multa"] == Decimal("10.00")
    assert exemplo["juros"] == Decimal("0.83")
    assert exemplo["total"] == Decimal("510.83")


def test_exemplo_encargos_respeita_carencia():
    exemplo = exemplo_encargos(Decimal("2.00"), Decimal("1.00"), 5)
    assert exemplo["multa"] == Decimal("0.00")
    assert exemplo["total"] == Decimal("500.00")


DO_BANCO = {**ENTRADA, "multa_atraso_percentual": 2, "juros_mensal_percentual": Decimal("1.50")}


def _abrir_pagina():
    from pathlib import Path
    from time import time

    from streamlit.testing.v1 import AppTest

    raiz = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(raiz / "pages" / "10_Configuracoes.py"), default_timeout=20)
    app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
    app.session_state["ultima_atividade"] = time()
    return app.run()


def test_tela_salva_valores_digitados():
    from unittest.mock import patch

    with (
        patch("src.services.configuracoes.obter", return_value=DO_BANCO),
        patch("src.services.configuracoes.atualizar") as atualizar,
    ):
        app = _abrir_pagina()
        assert not app.exception
        assert app.text_input[0].value == "2,00"
        app.text_input[0].set_value("3,5")
        app.button[0].click().run()
    assert atualizar.call_args.args[0]["multa_atraso_percentual"] == "3,5"


def test_tela_mostra_erro_de_validacao_sem_salvar():
    from unittest.mock import patch

    with (
        patch("src.services.configuracoes.obter", return_value=DO_BANCO),
        patch("src.repositories.configuracoes.atualizar") as gravar,
    ):
        app = _abrir_pagina()
        app.text_input[2].set_value("-3")
        app.button[0].click().run()
    assert not gravar.called
    assert "Carência" in app.error[0].value
