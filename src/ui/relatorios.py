"""Relatórios: resultado por moto, custo de manutenção, inadimplência e fluxo de
caixa — segue Relatorios.dc.html do mockup."""

from datetime import date
from html import escape

import streamlit as st

from src.domain.relatorios import agrupar_por_modelo, proporcoes
from src.domain.valores import hoje_br
from src.services import relatorios
from src.ui.componentes import (
    CORES_BORDA,
    barra_proporcional,
    cabecalho,
    chip_placa,
    proteger,
    tabela_html,
)
from src.ui.formatadores import (
    formatar_data,
    formatar_mes,
    formatar_moeda,
    formatar_placa,
)

_ABAS = ("Resultado por moto", "Custo de manutenção", "Inadimplência", "Fluxo de caixa")
_VISOES_CUSTO = [("moto", "Por moto"), ("modelo", "Por modelo")]
_VERDE, _VERMELHO, _GRAFITE = CORES_BORDA["verde"], CORES_BORDA["vermelho"], "#1E2227"
_NOTA_CRITERIOS = (
    "Cauções não compõem receita. Manutenções são contabilizadas pela entrada, "
    "documentos pela regularização. Custo/km usa as leituras disponíveis no período; "
    "sem distância registrada, fica em branco."
)


def _mono(texto, estilo=""):
    return f'<span class="mono" style="{estilo}">{texto}</span>'


def _liquido(valor):
    """Resultado em destaque: verde no positivo, vermelho no negativo."""
    cor = _VERDE if valor >= 0 else _VERMELHO
    return _mono(formatar_moeda(valor), f"font-weight:600;color:{cor};")


def _cor_barra(valor):
    return _VERDE if valor >= 0 else _VERMELHO


def _km(valor):
    return f"{int(valor):,} km".replace(",", ".")


def _periodo_texto(inicio, fim):
    if (inicio.year, inicio.month) == (fim.year, fim.month):
        return formatar_mes(inicio)
    return f"{formatar_data(inicio)} a {formatar_data(fim)}"


def _exportacao(chave, linhas):
    """Botões de exportação da aba, alinhados à direita, com os mesmos dados da tabela."""
    if not linhas:
        return
    _, csv, excel = st.columns([4, 1, 1])
    csv.download_button(
        "Exportar CSV",
        relatorios.exportar_csv(linhas),
        f"relatorio_{chave}.csv",
        "text/csv",
        key=f"exportar_csv_{chave}",
        use_container_width=True,
    )
    excel.download_button(
        "Exportar Excel",
        relatorios.exportar_excel(linhas),
        f"relatorio_{chave}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"exportar_xlsx_{chave}",
        use_container_width=True,
    )


def _pills_custo():
    atual = st.session_state.get("relatorios_custo_visao", "modelo")
    with st.container(key="relatorios_filtros"):
        colunas = st.columns([1, 1, 4])
        for coluna, (valor, rotulo) in zip(colunas, _VISOES_CUSTO):
            if coluna.button(
                rotulo,
                key=f"pill_rel_{valor}",
                type="primary" if atual == valor else "secondary",
                use_container_width=True,
            ):
                st.session_state["relatorios_custo_visao"] = valor
                st.rerun()
    return atual


# ------------------------------------------------------------------- abas --


def _aba_resultado(resultado):
    linhas = sorted(resultado, key=lambda r: (-r["resultado"], r["placa"]))
    larguras = proporcoes([r["resultado"] for r in linhas])
    tabela_html(
        ["Moto", "Receita recebida", "Manutenção", "Documentos", "Resultado", ""],
        [
            [
                chip_placa(r["placa"]),
                _mono(formatar_moeda(r["receita_recebida"])),
                _mono(formatar_moeda(r["custo_manutencao"])),
                _mono(formatar_moeda(r["custo_documentos"])),
                _liquido(r["resultado"]),
                barra_proporcional(largura, _cor_barra(r["resultado"])),
            ]
            for r, largura in zip(linhas, larguras)
        ],
        alinhar_direita={1, 2, 3, 4},
    )
    _exportacao(
        "resultado_por_moto",
        [
            {
                "Placa": formatar_placa(r["placa"]),
                "Modelo": r["modelo"],
                "Receita recebida": r["receita_recebida"],
                "Manutenção": r["custo_manutencao"],
                "Documentos": r["custo_documentos"],
                "Resultado": r["resultado"],
                "Km rodados": r["km_rodados"],
                "Custo por km": r["custo_por_km"],
            }
            for r in linhas
        ],
    )


def _aba_custo(resultado):
    visao = _pills_custo()
    st.write("")
    if visao == "modelo":
        linhas = agrupar_por_modelo(resultado)
        larguras = proporcoes([g["custo_total"] for g in linhas])
        tabela_html(
            ["Modelo", "Motos", "Custo total", "Custo médio / moto", ""],
            [
                [
                    escape(g["modelo"]),
                    _mono(str(g["motos"])),
                    _mono(formatar_moeda(g["custo_total"])),
                    _mono(formatar_moeda(g["custo_medio"])),
                    barra_proporcional(largura, _GRAFITE),
                ]
                for g, largura in zip(linhas, larguras)
            ],
            alinhar_direita={1, 2, 3},
        )
        exportacao = [
            {
                "Modelo": g["modelo"],
                "Motos": g["motos"],
                "Custo total": g["custo_total"],
                "Custo médio por moto": g["custo_medio"],
            }
            for g in linhas
        ]
    else:
        linhas = sorted(resultado, key=lambda r: (-r["custo_manutencao"], r["placa"]))
        larguras = proporcoes([r["custo_manutencao"] for r in linhas])
        tabela_html(
            ["Moto", "Modelo", "Custo de manutenção", "Km rodados", "Custo / km", ""],
            [
                [
                    chip_placa(r["placa"]),
                    escape(r["modelo"]),
                    _mono(formatar_moeda(r["custo_manutencao"])),
                    _mono(_km(r["km_rodados"])) if r["km_rodados"] else "—",
                    _mono(formatar_moeda(r["custo_por_km"])) if r["custo_por_km"] is not None else "—",
                    barra_proporcional(largura, _GRAFITE),
                ]
                for r, largura in zip(linhas, larguras)
            ],
            alinhar_direita={2, 3, 4},
        )
        exportacao = [
            {
                "Placa": formatar_placa(r["placa"]),
                "Modelo": r["modelo"],
                "Custo de manutenção": r["custo_manutencao"],
                "Km rodados": r["km_rodados"],
                "Custo por km": r["custo_por_km"],
            }
            for r in linhas
        ]
    _exportacao(f"custo_manutencao_{visao}", exportacao)


def _indicador(rotulo, valor, cor=None, ultimo=False):
    borda = "" if ultimo else "border-right:1px solid var(--linha);"
    estilo_cor = f"color:{cor};" if cor else ""
    return (
        f'<div style="flex:1;padding:16px 22px;{borda}display:flex;flex-direction:column;gap:6px;">'
        f'<span class="rotulo" style="font-size:var(--fs-legenda);color:var(--texto-2);">{rotulo}</span>'
        f'<span class="mono" style="font-size:24px;font-weight:600;{estilo_cor}">{valor}</span></div>'
    )


def _aba_inadimplencia(dados):
    st.caption("Posição atual de cobranças em atraso, independente do período selecionado.")
    percentual = dados["percentual_carteira"]
    st.markdown(
        '<div style="display:flex;background:var(--superficie);border:1px solid var(--linha);'
        'border-radius:var(--raio-sm);margin-bottom:20px;">'
        + _indicador("total em atraso", formatar_moeda(dados["total_atraso"]), _VERMELHO if dados["total_atraso"] else None)
        + _indicador(
            "% da carteira do mês",
            f"{percentual}%".replace(".", ",") if percentual is not None else "—",
        )
        + _indicador("clientes atrasados", str(dados["clientes"]), ultimo=True)
        + "</div>",
        unsafe_allow_html=True,
    )
    linhas = dados["linhas"]
    tabela_html(
        ["Cliente", "Moto", "Vencimento", "Dias em atraso", "Valor + encargos"],
        [
            [
                escape(l["cliente"]),
                chip_placa(l["placa"]) if l["placa"] else "—",
                _mono(formatar_data(l["vencimento"])),
                f'<span style="color:{_VERMELHO};">{l["dias_atraso"]} dia(s)</span>',
                _mono(formatar_moeda(l["total_com_encargos"])),
            ]
            for l in linhas
        ],
        alinhar_direita={4},
    )
    _exportacao(
        "inadimplencia",
        [
            {
                "Cliente": l["cliente"],
                "Placa": formatar_placa(l["placa"]) if l["placa"] else "",
                "Vencimento": formatar_data(l["vencimento"]),
                "Dias em atraso": l["dias_atraso"],
                "Saldo": l["saldo"],
                "Valor com encargos": l["total_com_encargos"],
            }
            for l in linhas
        ],
    )


def _aba_fluxo(fluxo, hoje):
    larguras = proporcoes([m["resultado"] for m in fluxo])
    mes_atual = hoje.isoformat()[:7]
    tabela_html(
        ["Mês", "Recebido", "Manutenção", "Documentos", "Líquido", ""],
        [
            [
                escape(formatar_mes(m["mes"]))
                + (
                    ' <span style="color:var(--texto-3);font-weight:400;">(parcial)</span>'
                    if m["mes"] == mes_atual
                    else ""
                ),
                _mono(formatar_moeda(m["receita_recebida"])),
                _mono(formatar_moeda(m["custo_manutencao"])),
                _mono(formatar_moeda(m["custo_documentos"])),
                _liquido(m["resultado"]),
                barra_proporcional(largura, _cor_barra(m["resultado"])),
            ]
            for m, largura in zip(fluxo, larguras)
        ],
        alinhar_direita={1, 2, 3, 4},
    )
    _exportacao(
        "fluxo_de_caixa",
        [
            {
                "Mês": formatar_mes(m["mes"]),
                "Recebido": m["receita_recebida"],
                "Manutenção": m["custo_manutencao"],
                "Documentos": m["custo_documentos"],
                "Líquido": m["resultado"],
            }
            for m in fluxo
        ],
    )


# ----------------------------------------------------------------- página --


def _periodo():
    hoje = hoje_br()
    col_de, col_ate, _ = st.columns([1.2, 1.2, 4], vertical_alignment="bottom")
    inicio = col_de.date_input("De", hoje.replace(day=1), format="DD/MM/YYYY", key="relatorios_de")
    fim = col_ate.date_input("Até", hoje, format="DD/MM/YYYY", key="relatorios_ate")
    return hoje, inicio, fim


def exibir():
    cabecalho("Relatórios", exibir_titulo=False)
    with proteger():
        hoje = hoje_br()
        inicio = st.session_state.get("relatorios_de", hoje.replace(day=1))
        fim = st.session_state.get("relatorios_ate", hoje)
        subtitulo = _periodo_texto(inicio, fim) if isinstance(inicio, date) and isinstance(fim, date) else ""
        st.markdown(
            f"""
            <h1 class="rotulo pagina-titulo">Relatórios</h1>
            <div style="color:var(--texto-2);font-size:var(--fs-secundario);margin-top:2px;">{escape(subtitulo)}</div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        hoje, inicio, fim = _periodo()
        dados = relatorios.resultado_por_moto(inicio, fim)

        guias = st.tabs(list(_ABAS))
        with guias[0]:
            _aba_resultado(dados["resultado"])
        with guias[1]:
            _aba_custo(dados["resultado"])
        with guias[2]:
            _aba_inadimplencia(relatorios.inadimplencia(hoje))
        with guias[3]:
            _aba_fluxo(dados["fluxo"], hoje)
        st.caption(_NOTA_CRITERIOS)
