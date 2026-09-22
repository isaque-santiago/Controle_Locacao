"""Componentes compartilhados e erros sem expor dados pessoais."""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from math import ceil
import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from src.ui.formatadores import formatar_data, formatar_moeda, formatar_placa, mascarar_cpf

# Tokens de cor de Arquivos/Design_UI.md — a cor de status é a única que "grita".
CORES_STATUS = {
    "vencido": "#D64545",
    "vencida": "#D64545",
    "atrasada": "#D64545",
    "atrasado": "#D64545",
    "bloqueado": "#D64545",
    "proxima": "#F2B705",
    "a_vencer": "#F2B705",
    "manutencao": "#F2B705",
    "em_dia": "#2F9E6E",
    "ok": "#2F9E6E",
    "ativo": "#2F9E6E",
    "disponivel": "#2F9E6E",
    "paga": "#2F9E6E",
    "aberta": "#585F66",
    "aberto": "#585F66",
    "alugada": "#585F66",
    "inativa": "#9AA0A6",
    "inativo": "#9AA0A6",
    "cancelada": "#9AA0A6",
    "cancelado": "#9AA0A6",
    "encerrado": "#9AA0A6",
}


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
                cor = CORES_STATUS.get(
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
    """Selos circulares tracejados (adesivo de vistoria) para alertas.

    itens: lista de (rótulo, quantidade, situação), situação em CORES_STATUS.
    """
    if not itens:
        return
    blocos = "".join(
        f"""
        <div style="display:flex;flex-direction:column;align-items:center;gap:.45rem;min-width:5.5rem;">
          <div style="width:3.4rem;height:3.4rem;border-radius:50%;border:2px dashed {CORES_STATUS.get(situacao, '#9AA0A6')};
                      display:flex;align-items:center;justify-content:center;
                      font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:1.2rem;
                      color:{CORES_STATUS.get(situacao, '#9AA0A6')};">
            {quantidade}
          </div>
          <span style="font-size:.78rem;color:#585F66;text-align:center;">{rotulo}</span>
        </div>
        """
        for rotulo, quantidade, situacao in itens
    )
    st.markdown(
        f'<div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin:.75rem 0 1.25rem;">{blocos}</div>',
        unsafe_allow_html=True,
    )


def barra_ocupacao(segmentos):
    """Barra segmentada (medidor de combustível) em vez de gráfico de biblioteca.

    segmentos: lista de (rótulo, quantidade, situação), situação em CORES_STATUS.
    """
    partes = [(r, q, CORES_STATUS.get(s, "#9AA0A6")) for r, q, s in segmentos if q]
    if not partes:
        st.caption("Sem motos cadastradas para exibir ocupação.")
        return
    barra = "".join(
        f'<div style="flex:{q};background:{cor};"></div>' for _, q, cor in partes
    )
    legenda = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.4rem;margin-right:1.2rem;'
        f'font-size:.8rem;color:#585F66;"><span style="width:8px;height:8px;border-radius:50%;'
        f'background:{cor};display:inline-block;"></span>{rotulo} ({q})</span>'
        for rotulo, q, cor in partes
    )
    st.markdown(
        f"""
        <div style="display:flex;height:.65rem;border-radius:4px;overflow:hidden;background:#EEF0F0;margin:.6rem 0 .5rem;">{barra}</div>
        <div style="margin-bottom:.75rem;">{legenda}</div>
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


def cabecalho(titulo):
    from src.auth import require_login
    from src.ui.tema import aplicar

    aplicar()
    require_login()
    st.title(titulo)
    if mensagem := st.session_state.pop("mensagem_sucesso", None):
        st.success(mensagem)
