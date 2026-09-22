from decimal import Decimal
from unittest.mock import patch

from src.ui import clientes
from src.ui.componentes import selo_situacao


def test_dados_cadastrados_sao_escapados_no_html_da_ficha():
    cliente = {
        "cpf": "52998224725",
        "cnh_numero": None,
        "cnh_categoria": None,
        "cnh_validade": None,
        "telefone": None,
        "email": "pessoa@example.com",
        "endereco": '<script>alert("x")</script>',
    }
    with patch.object(clientes.st, "markdown") as markdown:
        clientes._card_dados_pessoais(cliente)

    html = markdown.call_args.args[0]
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "<b>Ativo</b>" not in selo_situacao("<b>Ativo</b>", "ativo")


def test_multa_dos_pagamentos_permanece_decimal_ate_a_formatacao():
    parcela = {
        "id": "c1",
        "tipo": "locacao",
        "vencimento": "2026-09-01",
        "valor": "100.00",
        "situacao": "paga",
    }
    historicos = {
        "c1": [
            {
                "data_pagamento": "2026-09-01",
                "forma": "pix",
                "multa_juros": "0.10",
            },
            {
                "data_pagamento": "2026-09-02",
                "forma": "pix",
                "multa_juros": "0.20",
            },
        ]
    }
    valores_formatados = []

    def formatar(valor):
        valores_formatados.append(valor)
        return str(valor)

    with (
        patch.object(clientes, "formatar_moeda", side_effect=formatar),
        patch.object(clientes, "tabela_html"),
    ):
        clientes._aba_pagamentos([parcela], historicos)

    assert Decimal("0.30") in valores_formatados
