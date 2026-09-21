"""Componentes compartilhados e erros sem expor dados pessoais."""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from math import ceil
import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from src.ui.formatadores import formatar_data, formatar_moeda, mascarar_cpf


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

    def cor(linha):
        cores = {
            "vencido": "#7f1d1d",
            "vencida": "#7f1d1d",
            "atrasada": "#7f1d1d",
            "proxima": "#713f12",
            "a_vencer": "#713f12",
            "em_dia": "#14532d",
            "ok": "#14532d",
            "inativa": "#374151",
        }
        fundo = cores.get(linha.get("Situacao", linha.get("Status", "")))
        return [
            f"background-color: {fundo}; color: white" if fundo else "" for _ in linha
        ]

    st.dataframe(
        quadro.style.apply(cor, axis=1), hide_index=True, use_container_width=True
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
