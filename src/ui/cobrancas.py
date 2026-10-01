"""Cobranças: abas Hoje, Atrasadas, Próximos 7 dias e Pagas, com registro de
pagamento em diálogo — segue Cobrancas.dc.html do mockup."""

from datetime import date
from decimal import Decimal
from html import escape

import streamlit as st

from src.domain.painel_cobrancas import (
    ABAS,
    mensagem_cobranca,
    pertence_a_aba,
    resumo_atraso,
)
from src.domain.entradas import decimal_campo, erro_de, primeiro_erro
from src.domain.valores import hoje_br
from src.services import clientes, cobrancas, motos
from src.ui.componentes import botao_acao, cabecalho, cabecalho_pagina, chip_placa, proteger
from src.ui.formularios import campo_moeda, legenda_obrigatorios, linha_campos, rodape_formulario
from src.ui.listas import abas, aba_ativa
from src.ui.registros import campo, lista_registros, registro
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


def _texto(valor, cor="", mono=False):
    estilo = f"font-size:var(--fs-secundario);{cor}"
    return f'<span class="{"mono" if mono else ""}" style="{estilo}">{valor}</span>'


def _cartao(chave, colunas, linhas, acoes=None, subtitulo=None):
    """Lista de cobranças em cartões: a primeira coluna de `colunas` é a identidade (cliente) e as
    demais viram dados rotulados. `colunas` = [(rótulo, função(c) -> html)]; `subtitulo` é uma
    função opcional (c -> html) para uma observação sob o nome; `acoes(c, grupo)` desenha os botões."""
    (_, titulo), *dados = colunas
    with lista_registros(f"cobrancas_{chave}", acoes=2 if acoes else 0):
        for c in linhas:
            campos = [campo(rotulo, desenhar(c)) for rotulo, desenhar in dados]
            with registro(
                f"cobrancas_{chave}",
                c["id"],
                titulo(c),
                campos,
                subtitulo=subtitulo(c) if subtitulo else None,
                acoes=bool(acoes),
            ) as grupo:
                if acoes:
                    acoes(c, grupo)


def _acoes_abertas(chave):
    def desenhar(c, grupo):
        with grupo.popover(
            "Mensagem",
            icon=":material/content_copy:",
            help=f"Copiar a mensagem de cobrança de {c['cliente']}",
            type="tertiary",
            key=f"mensagem_{chave}_{c['id']}",
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
        if botao_acao(
            grupo,
            "pagar",
            f"pagar_{chave}_{c['id']}",
            ajuda=f"Registrar o pagamento de {c['cliente']}",
        ):
            _dialog_pagamento(c)

    return desenhar


@st.dialog("Registrar pagamento")
def _dialog_pagamento(c):
    st.markdown(
        f'{chip_placa(c["placa"])} <span style="margin-left:8px;">{escape(c["cliente"] or "")}</span>'
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
    def linha(rotulo, valor, total=False):
        classe = "resumo-linhas__linha resumo-linhas__linha--total" if total else "resumo-linhas__linha"
        return f'<div class="{classe}"><span>{rotulo}</span><span class="mono">{valor}</span></div>'

    st.markdown(
        '<div class="resumo-linhas">'
        + linha("Valor original (saldo)", formatar_moeda(c["saldo"]))
        + linha("Multa", formatar_moeda(enc["multa"]))
        + linha(f'Juros ({enc["dias_atraso"]} dia(s) de atraso)', formatar_moeda(enc["juros"]))
        + linha("Total", formatar_moeda(enc["total"]), total=True)
        + "</div>",
        unsafe_allow_html=True,
    )
    sufixo = f"{c['id']}_{data.isoformat()}"
    with linha_campos([1, 1], "pg_valores") as (col_principal, col_extras):
        with col_principal:
            principal = campo_moeda(
                "Principal recebido", c["saldo"], f"pg_principal_{sufixo}", obrigatorio=True, ao_vivo=True
            )
        with col_extras:
            extras = campo_moeda(
                "Multa e juros recebidos", enc["multa"] + enc["juros"], f"pg_extras_{sufixo}", ao_vivo=True
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
    legenda_obrigatorios()

    saldo = Decimal(str(c["saldo"]))
    erro = primeiro_erro(
        erro_de(decimal_campo, principal, "Principal recebido", positivo=True),
        erro_de(decimal_campo, extras, "Multa e juros recebidos"),
    )
    if not erro and decimal_campo(principal, "Principal recebido") > saldo:
        erro = f"Principal recebido: não pode ser maior que o saldo da cobrança ({formatar_moeda(saldo)})."
    acao = rodape_formulario("Confirmar pagamento", "pagamento", desabilitado=bool(erro), motivo=erro)
    if acao.cancelou:
        st.rerun()
    if acao.confirmou:
        with proteger():
            cobrancas.registrar_pagamento(
                c["id"],
                data,
                decimal_campo(principal, "Principal recebido", positivo=True),
                decimal_campo(extras, "Multa e juros recebidos"),
                forma,
                observacoes or None,
            )
            _salvo()


def _colunas_base():
    return [
        ("Cliente", lambda c: escape(c["cliente"] or "—")),
        ("Moto", lambda c: chip_placa(c["placa"]) if c["placa"] else "—"),
        ("Vencimento", lambda c: _texto(formatar_data(c["vencimento"]), mono=True)),
    ]


def _moeda(campo):
    return lambda c: _texto(formatar_moeda(c[campo]), mono=True)


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
            ("Pago em", lambda c: _texto(formatar_data(c["pago_em"]) if c["pago_em"] else "—", mono=True)),
            ("Forma", lambda c: _texto(_FORMAS_ROTULO.get(c["forma"], "—"), "color:var(--texto-2);")),
            ("Valor", _moeda("valor")),
        ],
        linhas[:_LIMITE_PAGAS],
    )
    if len(linhas) > _LIMITE_PAGAS:
        st.caption(f"Mostrando as {_LIMITE_PAGAS} mais recentes de {len(linhas)}.")


def _aba_atrasadas(linhas):
    dias = lambda c: _texto(f'{c["encargos"]["dias_atraso"]} dia(s)', "color:var(--perigo-texto);")
    encargos = lambda c: _texto(
        formatar_moeda(c["encargos"]["multa"] + c["encargos"]["juros"]),
        mono=True,
    )
    total = lambda c: _texto(formatar_moeda(c["encargos"]["total"]), mono=True)
    _cartao(
        "atrasadas",
        _colunas_base()
        + [
            ("Atraso", dias),
            ("Original", _moeda("saldo")),
            ("Encargos", encargos),
            ("Total", total),
        ],
        linhas,
        _acoes_abertas("atrasadas"),
    )


def _aba_hoje(linhas):
    _cartao(
        "hoje",
        _colunas_base() + [("Valor", _moeda("saldo"))],
        linhas,
        _acoes_abertas("hoje"),
    )


def _aba_proximos(linhas):
    primeira = lambda c: (
        _texto("1ª parcela", "color:var(--texto-2);") if c.get("numero") == 1 else ""
    )
    _cartao(
        "proximos",
        _colunas_base() + [("Valor", _moeda("saldo"))],
        linhas,
        subtitulo=primeira,
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
        cabecalho_pagina("Cobranças", sub=subtitulo)

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

        guias = abas("cobrancas_abas", [f"{aba} · {len(por_aba[aba])}" for aba in ABAS])
        for aba, guia in zip(ABAS, guias):
            with guia:
                if not aba_ativa(guia):
                    continue
                if por_aba[aba]:
                    _DESENHO_ABA[aba](por_aba[aba])
                else:
                    st.markdown(
                        f'<div style="color:var(--texto-2);font-size:var(--fs-secundario);padding:8px 0;">{_VAZIO[aba]}</div>',
                        unsafe_allow_html=True,
                    )
