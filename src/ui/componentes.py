"""Componentes compartilhados e erros sem expor dados pessoais."""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from html import escape
from math import ceil
import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_placa, mascarar_cpf

# Tokens de cor do mockup navegável (Arquivos/Design_UI.md, seção 1) — a cor de
# status é a única que "grita"; estados neutros/operacionais (alugada, aberta)
# não recebem tinta, só o selo (bolinha) — conforme Motos.dc.html e Cobrancas.dc.html.
_SITUACOES = {
    "vencido": "vermelho",
    "vencida": "vermelho",
    "atrasada": "vermelho",
    "atrasado": "vermelho",
    "bloqueado": "vermelho",
    "proxima": "amarelo",
    "a_vencer": "amarelo",
    "manutencao": "amarelo",
    "em_dia": "verde",
    "ok": "verde",
    "disponivel": "verde",
    "paga": "verde",
    "ativo_cliente": "verde",
    "inativa": "cinza",
    "inativo": "cinza",
    "cancelada": "cinza",
    "cancelado": "cinza",
    "encerrado": "cinza",
}
# Cor do selo/borda (dot, círculo tracejado, segmento de barra): tom puro do token.
CORES_BORDA = {
    "vermelho": "#D64545",
    "amarelo": "#F2B705",
    "verde": "#2F9E6E",
    "cinza": "#9AA0A6",
}
# Cor do texto: igual à borda, exceto o amarelo — usa o tom escuro do mockup
# (#8a6600) para manter contraste legível sobre fundo claro.
CORES_TEXTO = {**CORES_BORDA, "amarelo": "#8a6600"}
CORES_STATUS_BORDA = {chave: CORES_BORDA[cor] for chave, cor in _SITUACOES.items()}
CORES_STATUS_TEXTO = {chave: CORES_TEXTO[cor] for chave, cor in _SITUACOES.items()}


@contextmanager
def proteger():
    try:
        yield
    except ValueError as erro:
        st.error(str(erro))
    except APIError as erro:
        mensagens = {
            "23505": "Este registro já existe. Atualize a lista antes de tentar novamente.",
            "23514": "Confira datas, valores e situação do cadastro.",
            "23503": "Há registros vinculados ou uma referência deixou de existir. Atualize a página.",
            "42501": "Sua sessão não tem permissão para esta operação. Entre novamente.",
            "PGRST202": "Aplique as migrations mais recentes no banco. Consulte o guia de instalação.",
        }
        st.error(
            mensagens.get(
                erro.code,
                "Não foi possível concluir a operação. Confira os dados e atualize a página.",
            )
        )
    except Exception:
        st.error(
            "Não foi possível acessar o serviço. Verifique a conexão e a configuração do Supabase e tente novamente."
        )


def cartao_kpi(titulo, valor):
    st.metric(titulo, valor)


def tabela(linhas, chave="tabela", colunas=None):
    if not linhas:
        st.info("Nenhum registro encontrado.")
        return
    pagina = 1
    paginas = ceil(len(linhas) / 25)
    if paginas > 1:
        if st.session_state.get(chave + "_pagina", 1) > paginas:
            st.session_state[chave + "_pagina"] = paginas
        pagina = st.number_input(
            "Página", min_value=1, max_value=paginas, value=1, key=chave + "_pagina"
        )
    st.caption(f"{len(linhas)} registro(s) • página {pagina} de {paginas}")
    registros = []
    for linha in linhas[(pagina - 1) * 25 : pagina * 25]:
        registro = {}
        for nome, valor in linha.items():
            if (
                nome.startswith("_")
                or nome == "id"
                or nome.endswith("_id")
                or (colunas and nome not in colunas)
                or isinstance(valor, (dict, list))
            ):
                continue
            if nome == "cpf":
                valor = mascarar_cpf(valor or "")
            elif nome == "placa":
                valor = formatar_placa(valor) if valor else valor
            elif nome in {"situacao", "status"} and valor:
                valor = f"● {str(valor).replace('_', ' ')}"
            elif isinstance(valor, Decimal) or nome in {
                "valor",
                "saldo",
                "valor_pago",
                "valor_periodo",
                "custo_total",
                "custo_pecas",
                "custo_mao_obra",
                "receita_recebida",
                "custo_manutencao",
                "custo_documentos",
                "resultado",
                "custo_por_km",
                "valor_aquisicao",
                "valor_locacao_sugerido",
                "caucao_valor",
                "multa_juros",
            }:
                valor = formatar_moeda(valor) if valor is not None else "—"
            elif (
                isinstance(valor, date)
                or nome.startswith("data_")
                or nome in {"vencimento", "cnh_validade", "ultima_data", "proxima_data"}
            ):
                valor = formatar_data(valor)
            registro[nome.replace("_", " ").capitalize()] = valor
        registros.append(registro)
    quadro = pd.DataFrame(registros)

    def estilo_linha(linha):
        cor = None
        for coluna in ("Situacao", "Status"):
            if coluna in linha:
                cor = CORES_STATUS_TEXTO.get(
                    str(linha[coluna]).lstrip("● ").replace(" ", "_")
                )
        return [f"color: {cor}; font-weight: 600" if cor else "" for _ in linha]

    estilizado = quadro.style.apply(estilo_linha, axis=1)
    if "Placa" in quadro.columns:
        estilizado = estilizado.set_properties(
            subset=["Placa"],
            **{
                "background-color": "#1E2227",
                "color": "#FAFAF9",
                "font-family": "'IBM Plex Mono', monospace",
                "font-weight": "600",
                "letter-spacing": "0.03em",
            },
        )
    st.dataframe(estilizado, hide_index=True, use_container_width=True)


def painel_selos(itens):
    """Selos circulares tracejados (adesivo de vistoria) para alertas — como em
    Main.dc.html: círculo de 40px, borda tracejada no tom puro, número no tom
    escuro (amarelo) ou puro (vermelho) para manter contraste.

    itens: lista de (rótulo, quantidade, situação), situação em CORES_STATUS_BORDA.
    """
    if not itens:
        return
    blocos = "".join(
        f"""
        <div style="display:flex;align-items:center;gap:.6rem;min-width:11rem;">
          <div style="width:40px;height:40px;flex-shrink:0;border-radius:50%;
                      border:2px dashed {CORES_STATUS_BORDA.get(situacao, '#9AA0A6')};
                      display:flex;align-items:center;justify-content:center;
                      font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:15px;
                      color:{CORES_STATUS_TEXTO.get(situacao, '#585F66')};">
            {quantidade}
          </div>
          <span style="font-size:.8rem;color:#585F66;">{rotulo}</span>
        </div>
        """
        for rotulo, quantidade, situacao in itens
    )
    st.markdown(
        f'<div style="display:flex;gap:1.25rem;flex-wrap:wrap;margin:.75rem 0 1.25rem;">{blocos}</div>',
        unsafe_allow_html=True,
    )


# Cores da barra de ocupação da frota — como em Main.dc.html: alugada é
# grafite-900 (estado dominante, não é um alerta), as demais seguem o token
# de situação de fato (verde/amarelo/cinza).
CORES_OCUPACAO = {
    "alugada": "#1E2227",
    "disponivel": "#2F9E6E",
    "manutencao": "#F2B705",
    "inativa": "#9AA0A6",
}


def barra_ocupacao(segmentos):
    """Barra segmentada (medidor de combustível) em vez de gráfico de biblioteca.

    segmentos: lista de (rótulo, quantidade, status), status em CORES_OCUPACAO.
    """
    partes = [(r, q, CORES_OCUPACAO.get(s, "#9AA0A6")) for r, q, s in segmentos if q]
    if not partes:
        st.caption("Sem motos cadastradas para exibir ocupação.")
        return
    barra = "".join(
        f'<div style="flex:{q};background:{cor};"></div>' for _, q, cor in partes
    )
    legenda = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4rem;margin-right:1.2rem;'
        f'font-size:.8rem;color:#585F66;"><span style="width:8px;height:8px;border-radius:2px;'
        f'background:{cor};display:inline-block;"></span>{rotulo} ({q})</span>'
        for rotulo, q, cor in partes
    )
    st.markdown(
        f"""
        <div style="display:flex;height:8px;border-radius:2px;overflow:hidden;margin:.6rem 0 .5rem;">{barra}</div>
        <div style="margin-bottom:.75rem;">{legenda}</div>
        """,
        unsafe_allow_html=True,
    )


def chip_placa(placa, tamanho="normal"):
    """Chip mono de placa (fundo grafite-900), como nas tabelas do mockup."""
    fonte = "18px" if tamanho == "grande" else "12px"
    padding = "8px 14px" if tamanho == "grande" else "3px 8px"
    return (
        f'<span class="mono" style="background:#1E2227;color:#FAFAF9;padding:{padding};'
        f'border-radius:{"5px" if tamanho == "grande" else "4px"};font-weight:600;'
        f'font-size:{fonte};letter-spacing:0.05em;">{escape(formatar_placa(placa))}</span>'
    )


def barra_proporcional(percentual, cor="#2F9E6E"):
    """Barra de 100px (6px de altura) para tabelas de Relatórios, em vez de gráfico
    de biblioteca. `percentual` de 0 a 100."""
    largura = max(0, min(100, int(percentual)))
    return (
        '<div style="height:6px;width:100px;border-radius:2px;overflow:hidden;'
        'background:rgba(30,34,39,0.12);">'
        f'<div style="height:100%;width:{largura}%;background:{cor};"></div></div>'
    )


def selo_situacao(texto, situacao):
    """Bolinha de 6-8px colorida + texto — o selo de status padrão das tabelas."""
    borda = CORES_STATUS_BORDA.get(situacao)
    cor_texto = CORES_STATUS_TEXTO.get(situacao)
    pontinho = borda or "#1E2227"
    estilo_cor = f"color:{cor_texto};" if cor_texto else ""
    return (
        f'<div style="display:flex;align-items:center;gap:6px;{estilo_cor}">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{pontinho};'
        f'display:inline-block;flex-shrink:0;"></span>{escape(str(texto))}</div>'
    )


def tabela_html(cabecalhos, linhas, alinhar_direita=None):
    """Tabela somente leitura, hairline entre linhas, sem zebra — para abas sem
    ação por linha (Plano de manutenção, Histórico, Contratos...). Cada célula
    de `linhas` já vem pronta como HTML (use selo_situacao/chip_placa/mono)."""
    alinhar_direita = alinhar_direita or set()
    ultimo = len(cabecalhos) - 1

    def celula(i, conteudo, tag, borda):
        padding = "20px" if i in (0, ultimo) else "12px"
        alinhamento = "text-align:right;" if i in alinhar_direita else ""
        return (
            f'<{tag} style="padding:12px {padding};{borda}{alinhamento}'
            f'{"font-weight:500;color:#585F66;" if tag == "th" else ""}">{conteudo}</{tag}>'
        )

    ths = "".join(
        celula(i, c, "th", "border-bottom:1px solid rgba(30,34,39,0.12);")
        for i, c in enumerate(cabecalhos)
    )
    if not linhas:
        corpo = (
            f'<tr><td colspan="{len(cabecalhos)}" style="padding:16px 20px;'
            f'color:#585F66;font-size:13px;">Nenhum registro encontrado.</td></tr>'
        )
    else:
        corpo = ""
        for indice, linha in enumerate(linhas):
            borda = (
                "border-bottom:1px solid rgba(30,34,39,0.12);"
                if indice < len(linhas) - 1
                else ""
            )
            corpo += "<tr>" + "".join(
                celula(i, valor, "td", borda) for i, valor in enumerate(linha)
            ) + "</tr>"
    st.markdown(
        f"""
        <div class="tabela-leitura" style="background:#FAFAF9;border:1px solid rgba(30,34,39,0.12);border-radius:2px;overflow:auto;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr>{ths}</tr></thead>
            <tbody>{corpo}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def indicador_etapas(atual, rotulos):
    """Assistente (wizard): círculos numerados conectados por linha — só usado em Novo contrato."""
    itens = ""
    for i, rotulo in enumerate(rotulos, start=1):
        concluido = i <= atual
        cor_fundo = "#1E2227" if concluido else "transparent"
        cor_borda = "#1E2227" if concluido else "#9AA0A6"
        cor_texto = "#FAFAF9" if concluido else "#9AA0A6"
        if i > 1:
            cor_linha = "#1E2227" if i <= atual else "#9AA0A6"
            itens += f'<div style="flex:1;height:2px;background:{cor_linha};margin-top:1.05rem;"></div>'
        itens += f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:.4rem;">
          <div style="width:2.1rem;height:2.1rem;border-radius:50%;background:{cor_fundo};
                      border:2px solid {cor_borda};display:flex;align-items:center;justify-content:center;
                      color:{cor_texto};font-family:'IBM Plex Mono',monospace;font-weight:600;">{i}</div>
          <span style="font-size:.72rem;color:#585F66;white-space:nowrap;">{rotulo}</span>
        </div>
        """
    st.markdown(
        f'<div style="display:flex;align-items:flex-start;margin:1rem 0 1.5rem;">{itens}</div>',
        unsafe_allow_html=True,
    )


def selecionar(titulo, linhas, rotulo, chave):
    if not linhas:
        st.info(f"Nenhum registro disponível para {titulo.lower()}.")
        return None
    mapa = {r["id"]: r for r in linhas}
    escolhido = st.selectbox(
        titulo,
        list(mapa),
        format_func=lambda identificador: rotulo(mapa[identificador]),
        key=chave,
    )
    return mapa[escolhido]


def abrir_ficha_contrato(contrato_id):
    """Abre a página de contratos com a ficha indicada já selecionada."""
    st.session_state["contratos_visao"] = "ficha"
    st.session_state["contratos_id_selecionado"] = contrato_id
    st.switch_page("pages/4_Contratos.py")


def abrir_ficha_cliente(cliente_id):
    """Abre a página de clientes com a ficha indicada já selecionada."""
    st.session_state["clientes_visao"] = "ficha"
    st.session_state["clientes_id_selecionado"] = cliente_id
    st.switch_page("pages/3_Clientes.py")


def campo_data(titulo, valor=None, **kwargs):
    return st.date_input(
        titulo,
        value=date.fromisoformat(valor[:10]) if valor else None,
        format="DD/MM/YYYY",
        **kwargs,
    )


def sucesso():
    st.session_state["mensagem_sucesso"] = "Alterações salvas."
    st.rerun()


def cabecalho(titulo, exibir_titulo=True):
    from src.auth import require_login
    from src.ui.tema import aplicar

    aplicar()
    require_login()
    if exibir_titulo:
        st.title(titulo)
    if mensagem := st.session_state.pop("mensagem_sucesso", None):
        st.success(mensagem)
