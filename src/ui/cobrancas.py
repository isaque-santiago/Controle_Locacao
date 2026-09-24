"""Cobranças: abas Hoje, Atrasadas, Próximos 7 dias e Pagas, com registro de
pagamento em diálogo — segue Cobrancas.dc.html do mockup."""

from datetime import date

import streamlit as st

from src.domain.painel_cobrancas import (
    ABAS,
    mensagem_cobranca,
    pertence_a_aba,
    resumo_atraso,
)
from src.domain.valores import decimal_br, hoje_br
from src.services import clientes, cobrancas, motos
from src.ui.componentes import cabecalho, chip_placa, proteger
from src.ui.formatadores import formatar_data, formatar_moeda

_FORMAS = ["pix", "dinheiro", "cartao", "transferencia", "outro"]
_FORMAS_ROTULO = {
    "pix": "Pix",
    "dinheiro": "Dinheiro",
    "cartao": "Cartão",
    "transferencia": "Transferência",
    "outro": "Outro",
}
_LIMITE_PAGAS = 30
_VAZIO = {
    "Hoje": "Nenhuma cobrança vence hoje.",
    "Atrasadas": "Nenhuma cobrança em atraso.",
    "Próximos 7 dias": "Nenhuma cobrança vence nos próximos 7 dias.",
    "Pagas": "Nenhuma cobrança paga.",
}


def _salvo(mensagem="Pagamento registrado."):
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


def _texto(valor, cor="", direita=False, mono=False):
    estilo = f"font-size:var(--fs-secundario);{cor}"
    if direita:
        estilo += "text-align:right;display:block;"
    return f'<span class="{"mono" if mono else ""}" style="{estilo}">{valor}</span>'


def _cartao(chave, colunas, linhas, acoes=None):
    """Tabela em cartão: `colunas` = [(rótulo, peso, função(c) -> html)]; `acoes`
    desenha os botões da última coluna."""
    pesos = [peso for _, peso, _ in colunas] + ([1.0] if acoes else [])
    with st.container(key=f"cobrancas_card_{chave}"):
        cab = st.columns(pesos, vertical_alignment="center")
        for coluna, (rotulo, _, _) in zip(cab, colunas):
            coluna.markdown(_texto(rotulo, "color:var(--texto-2);"), unsafe_allow_html=True)
        for c in linhas:
            linha = st.columns(pesos, vertical_alignment="center")
            for coluna, (_, _, desenhar) in zip(linha, colunas):
                coluna.markdown(desenhar(c), unsafe_allow_html=True)
            if acoes:
                with linha[-1]:
                    acoes(c)


def _acoes_abertas(chave):
    def desenhar(c):
        col_msg, col_pagar = st.columns(2)
        with col_msg.popover(
            ":material/chat:",
            help="Copiar mensagem de cobrança",
            use_container_width=True,
        ):
            st.code(
                mensagem_cobranca(
                    c["cliente"],
                    c["placa"],
                    formatar_data(c["vencimento"]),
                    formatar_moeda(c["saldo"]),
                    c["encargos"]["dias_atraso"],
                ),
                language=None,
                wrap_lines=True,
            )
        if col_pagar.button(
            ":material/check:",
            key=f"pagar_{chave}_{c['id']}",
            help="Registrar pagamento",
            use_container_width=True,
        ):
            _dialog_pagamento(c)

    return desenhar


@st.dialog("Registrar pagamento")
def _dialog_pagamento(c):
    st.markdown(
        f'{chip_placa(c["placa"])} <span style="margin-left:8px;">{c["cliente"]}</span>'
        f'<div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:4px;">'
        f'{c["tipo"].capitalize()} · vencimento {formatar_data(c["vencimento"])}</div>',
        unsafe_allow_html=True,
    )
    data = st.date_input(
        "Data do pagamento", hoje_br(), format="DD/MM/YYYY", key=f"pg_data_{c['id']}"
    )
    enc = cobrancas.calcular_encargos_cobranca(
        c, data, cobrancas.configuracao_encargos()
    )
    linha = "display:flex;justify-content:space-between;"
    st.markdown(
        f"""
        <div style="background:var(--fundo);border-radius:var(--raio-sm);padding:12px 14px;font-size:var(--fs-secundario);">
          <div style="{linha}"><span>Valor original (saldo)</span><span class="mono">{formatar_moeda(c["saldo"])}</span></div>
          <div style="{linha}"><span>Multa</span><span class="mono">{formatar_moeda(enc["multa"])}</span></div>
          <div style="{linha}"><span>Juros ({enc["dias_atraso"]} dia(s) de atraso)</span><span class="mono">{formatar_moeda(enc["juros"])}</span></div>
          <div style="{linha}font-weight:600;border-top:1px solid var(--linha);margin-top:6px;padding-top:6px;"><span>Total</span><span class="mono">{formatar_moeda(enc["total"])}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sufixo = f"{c['id']}_{data.isoformat()}"
    col_p, col_e = st.columns(2)
    principal = col_p.text_input(
        "Principal recebido (R$)", str(c["saldo"]), key=f"pg_principal_{sufixo}"
    )
    extras = col_e.text_input(
        "Multa e juros recebidos (R$)",
        str(enc["multa"] + enc["juros"]),
        key=f"pg_extras_{sufixo}",
    )
    st.caption("Principal menor que o saldo deixa a cobrança em aberto com o restante.")
    forma = st.radio(
        "Forma de pagamento",
        _FORMAS,
        format_func=_FORMAS_ROTULO.get,
        horizontal=True,
        key=f"pg_forma_{c['id']}",
    )
    observacoes = st.text_area("Observações", key=f"pg_obs_{c['id']}")
    if st.button("Confirmar pagamento", type="primary", use_container_width=True):
        try:
            cobrancas.registrar_pagamento(
                c["id"],
                data,
                decimal_br(principal, positivo=True),
                decimal_br(extras),
                forma,
                observacoes or None,
            )
        except ValueError as erro:
            st.error(str(erro))
        else:
            _salvo()


def _colunas_base():
    return [
        ("Cliente", 1.6, lambda c: _texto(c["cliente"] or "—")),
        ("Moto", 1.1, lambda c: chip_placa(c["placa"]) if c["placa"] else "—"),
        ("Vencimento", 1.1, lambda c: _texto(formatar_data(c["vencimento"]), mono=True)),
    ]


def _moeda(campo):
    return lambda c: _texto(formatar_moeda(c[campo]), direita=True, mono=True)


def _aba_pagas(linhas):
    historicos = cobrancas.historicos_pagamentos([c["id"] for c in linhas])
    for c in linhas:
        pagamentos = historicos.get(c["id"], [])
        c["pago_em"] = pagamentos[-1]["data_pagamento"] if pagamentos else None
        c["forma"] = pagamentos[-1]["forma"] if pagamentos else None
    linhas.sort(key=lambda c: c["pago_em"] or "", reverse=True)
    _cartao(
        "pagas",
        _colunas_base()
        + [
            ("Pago em", 1.1, lambda c: _texto(formatar_data(c["pago_em"]) if c["pago_em"] else "—", mono=True)),
            ("Forma", 1.1, lambda c: _texto(_FORMAS_ROTULO.get(c["forma"], "—"), "color:var(--texto-2);")),
            ("Valor", 1.1, _moeda("valor")),
        ],
        linhas[:_LIMITE_PAGAS],
    )
    if len(linhas) > _LIMITE_PAGAS:
        st.caption(f"Mostrando as {_LIMITE_PAGAS} mais recentes de {len(linhas)}.")


def _aba_atrasadas(linhas):
    dias = lambda c: _texto(f'{c["encargos"]["dias_atraso"]} dia(s)', "color:var(--perigo-texto);")
    encargos = lambda c: _texto(
        formatar_moeda(c["encargos"]["multa"] + c["encargos"]["juros"]),
        direita=True,
        mono=True,
    )
    total = lambda c: _texto(formatar_moeda(c["encargos"]["total"]), direita=True, mono=True)
    _cartao(
        "atrasadas",
        _colunas_base()
        + [
            ("Atraso", 0.9, dias),
            ("Original", 1.1, _moeda("saldo")),
            ("Encargos", 1.1, encargos),
            ("Total", 1.1, total),
        ],
        linhas,
        _acoes_abertas("atrasadas"),
    )


def _aba_hoje(linhas):
    _cartao(
        "hoje",
        _colunas_base() + [("Valor", 1.1, _moeda("saldo"))],
        linhas,
        _acoes_abertas("hoje"),
    )


def _aba_proximos(linhas):
    primeira = lambda c: (
        _texto("1ª parcela", "color:var(--texto-2);") if c.get("numero") == 1 else ""
    )
    _cartao(
        "proximos",
        _colunas_base() + [("Valor", 1.1, _moeda("saldo")), ("", 1.1, primeira)],
        linhas,
    )


_DESENHO_ABA = {
    "Hoje": _aba_hoje,
    "Atrasadas": _aba_atrasadas,
    "Próximos 7 dias": _aba_proximos,
    "Pagas": _aba_pagas,
}


def exibir():
    cabecalho("Cobranças", exibir_titulo=False)
    with proteger():
        hoje = hoje_br()
        placas = {m["id"]: m["placa"] for m in motos.listar()}
        nomes = {cl["id"]: cl["nome"] for cl in clientes.listar()}
        config = cobrancas.configuracao_encargos()
        linhas = []
        for c in cobrancas.listar():
            linha = {
                **c,
                "placa": placas.get(c["moto_id"]),
                "cliente": nomes.get(c["cliente_id"]),
            }
            if c["situacao"] in ("aberta", "atrasada"):
                linha["encargos"] = cobrancas.calcular_encargos_cobranca(c, hoje, config)
            linhas.append(linha)

        total_atraso, qtd_clientes = resumo_atraso(linhas)
        subtitulo = (
            f"{formatar_moeda(total_atraso)} em atraso · {qtd_clientes} cliente(s)"
            if qtd_clientes
            else "Nenhuma cobrança em atraso"
        )
        st.markdown(
            f"""
            <h1 class="rotulo pagina-titulo">Cobranças</h1>
            <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{subtitulo}</div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        por_aba = {
            aba: [
                c
                for c in linhas
                if pertence_a_aba(
                    c["situacao"], date.fromisoformat(c["vencimento"]), aba, hoje
                )
            ]
            for aba in ABAS
        }
        rapida = st.session_state.pop("cobranca_rapida", None)
        alvo = next(
            (c for aba in ("Hoje", "Atrasadas") for c in por_aba[aba] if c["id"] == rapida),
            None,
        )
        if alvo:
            _dialog_pagamento(alvo)

        guias = st.tabs([f"{aba} · {len(por_aba[aba])}" for aba in ABAS])
        for aba, guia in zip(ABAS, guias):
            with guia:
                if por_aba[aba]:
                    _DESENHO_ABA[aba](por_aba[aba])
                else:
                    st.markdown(
                        f'<div style="color:var(--texto-2);font-size:var(--fs-secundario);padding:8px 0;">{_VAZIO[aba]}</div>',
                        unsafe_allow_html=True,
                    )
