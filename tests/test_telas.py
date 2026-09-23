"""Smoke tests das páginas e login, usando serviços isolados do banco real."""

from pathlib import Path
from time import time
from unittest.mock import patch
from contextlib import ExitStack

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "arquivo",
    ["app.py"] + [str(p.relative_to(RAIZ)) for p in (RAIZ / "pages").glob("*.py")],
)
def test_pagina_sem_login_nao_acessa_dados(arquivo):
    app = AppTest.from_file(str(RAIZ / arquivo), default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == "Entrar"
    assert any(entrada.label == "E-mail" for entrada in app.text_input)
    assert any(entrada.label == "Senha" for entrada in app.text_input)
    assert any(botao.label == "Entrar no painel" for botao in app.button)


def test_login_exige_email_e_senha():
    app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=20).run()
    next(botao for botao in app.button if botao.label == "Entrar no painel").click().run()
    assert [erro.value for erro in app.error] == ["Informe o e-mail e a senha."]


def test_tema_escuro_injeta_sobrescritas_de_contraste():
    from src.ui import tema

    with (
        patch.object(tema.st, "session_state", {"modo_escuro": True}),
        patch.object(tema.st, "markdown") as markdown,
    ):
        tema.aplicar()

    assert markdown.call_count == 2
    assert "background:#15181C" in markdown.call_args.args[0]


@pytest.mark.parametrize(
    "arquivo",
    ["app.py"] + [str(p.relative_to(RAIZ)) for p in (RAIZ / "pages").glob("*.py")],
)
def test_paginas_vazias_autenticadas(arquivo):
    with ExitStack() as pilha:
        for modulo, nomes in {
            "motos": ["listar"],
            "clientes": ["listar"],
            "contratos": ["listar"],
            "cobrancas": ["listar", "gerar_cobrancas_pendentes", "configuracao_encargos"],
            "manutencao": ["listar_catalogo", "listar_manutencoes"],
            "vistorias": ["listar"],
            "documentos": ["listar_todos"],
            "alertas": ["listar_manutencao", "listar_documentos", "listar_cnh"],
        }.items():
            for nome in nomes:
                pilha.enter_context(
                    patch(f"src.services.{modulo}.{nome}", return_value=[])
                )
        pilha.enter_context(
            patch(
                "src.services.relatorios.resultado_por_moto",
                return_value={"resultado": [], "fluxo": []},
            )
        )
        pilha.enter_context(
            patch(
                "src.services.relatorios.inadimplencia",
                return_value={
                    "linhas": [],
                    "total_atraso": 0,
                    "clientes": 0,
                    "percentual_carteira": None,
                },
            )
        )
        pilha.enter_context(
            patch(
                "src.services.configuracoes.obter",
                return_value={
                    "multa_atraso_percentual": 2,
                    "juros_mensal_percentual": 1,
                    "carencia_dias": 0,
                    "alerta_manutencao_km": 300,
                    "alerta_manutencao_dias": 15,
                    "alerta_documento_dias": 30,
                    "alerta_cnh_dias": 30,
                },
            )
        )
        app = AppTest.from_file(str(RAIZ / arquivo), default_timeout=20)
        app.session_state["usuario"] = {"id": "teste", "email": "teste@example.com"}
        app.session_state["ultima_atividade"] = time()
        app.run()
        assert not app.exception
        assert not app.error, [e.value for e in app.error]
