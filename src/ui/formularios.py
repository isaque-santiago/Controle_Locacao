"""Campos e rodapé de formulário (Plano de melhorias, Etapa 5).

Cada tipo de dado tem um campo com o comportamento certo: dinheiro com prefixo `R$` e
formato brasileiro, percentual e unidades com sufixo, CPF/telefone com teclado numérico e
máscara previsível, placa em maiúsculas. A validação do navegador (`validate=`) mostra o
erro ao lado do campo, sem apagar o que foi digitado; a validação de verdade continua no
servidor (`src.domain.entradas`).

A aparência (prefixo, sufixo, linhas que empilham, rodapé) vem de classes em estilos.css,
ligadas pelas chaves de container (`moeda_*`, `sfx_*_*`, `camposlinha_*`, `rodape_*`).
"""

from collections import namedtuple
from contextlib import contextmanager
from html import escape

import streamlit as st

from src.domain.entradas import (
    REGEX_CPF,
    REGEX_MOEDA,
    REGEX_PLACA,
    REGEX_TELEFONE,
    formatar_cpf,
    formatar_telefone,
    texto_moeda,
    texto_percentual,
    texto_placa,
)
from src.ui.feedback import encerrar_operacao

# Sufixo exibido ao lado do campo: o texto vem do CSS (`sfx_<tipo>_`), pela chave do container.
SUFIXOS = ("km", "dias", "pct")

Acao = namedtuple("Acao", "confirmou cancelou")


def rotulo_obrigatorio(rotulo):
    """Marca o campo como obrigatório no rótulo (explicado por `legenda_obrigatorios`)."""
    return f"{rotulo} *"


def legenda_obrigatorios():
    st.caption("Campos marcados com * são obrigatórios.")


@contextmanager
def linha_campos(pesos, chave, **opcoes):
    """Campos lado a lado que empilham quando cada um ficaria estreito demais (menos de ~12 rem).
    Só agrupe campos curtos e relacionados (ano + vencimento, km + dias); texto longo fica em linha própria.
    Uso: `with linha_campos([1, 2], "doc_ano") as (ano, vencimento): ...`"""
    with st.container(key=f"camposlinha_{chave}"):
        yield st.columns(pesos, **opcoes)


# ------------------------------------------------------------------- campos --


def campo_moeda(rotulo, valor, chave, obrigatorio=False, ajuda=None, desabilitado=False, texto=None, ao_vivo=False):
    """Dinheiro: prefixo `R$`, valor inicial no padrão `1.234,56`. Devolve o texto digitado;
    converta com `decimal_campo(texto, rotulo)`, que levanta erro com o nome do campo.
    `texto` repõe o que o usuário já havia digitado (rascunho), sem reformatar.
    `ao_vivo=True` para campos fora de `st.form`: ali o navegador não envia um valor inválido, e o servidor
    ficaria com o valor anterior enquanto a tela mostra outro. Sem a regra do navegador o servidor recebe o
    que foi digitado e o rodapé explica o erro (`rodape_formulario(motivo=...)`)."""
    nome = rotulo_obrigatorio(rotulo) if obrigatorio else rotulo
    with st.container(key=f"moeda_{chave}"):
        return st.text_input(
            nome,
            texto_moeda(valor) if texto is None else texto,
            key=chave,
            placeholder="0,00",
            help=ajuda,
            autocomplete="off",
            disabled=desabilitado,
            validate=None if ao_vivo else (REGEX_MOEDA, f"{rotulo}: use o formato 1.234,56."),
        )


def campo_percentual(rotulo, valor, chave, ajuda=None):
    """Percentual: sufixo `%`, vírgula nos decimais (`2,50`). Devolve o texto digitado."""
    with st.container(key=f"sfx_pct_{chave}"):
        return st.text_input(
            rotulo,
            texto_percentual(valor),
            key=chave,
            placeholder="0,00",
            help=ajuda,
            autocomplete="off",
            validate=(REGEX_MOEDA, f"{rotulo}: use números com vírgula, como 2,50."),
        )


def campo_inteiro(rotulo, valor, chave, sufixo=None, minimo=0, maximo=None, ajuda=None, desabilitado=False):
    """Quantidade inteira (dias, km, anos): teclado numérico, passo 1 e, se houver, sufixo da
    unidade (`km`, `dias`). Devolve int."""
    assert sufixo in (None, *SUFIXOS), sufixo
    with st.container(key=f"sfx_{sufixo}_{chave}" if sufixo else f"inteiro_{chave}"):
        return st.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=valor,
            step=1,
            format="%d",
            key=chave,
            help=ajuda,
            disabled=desabilitado,
        )


def campo_cpf(rotulo, valor, chave, obrigatorio=False):
    """CPF: teclado numérico, máscara `000.000.000-00` e erro ao lado do campo. O servidor
    valida os dígitos verificadores e guarda só os números."""
    nome = rotulo_obrigatorio(rotulo) if obrigatorio else rotulo
    return st.text_input(
        nome,
        formatar_cpf(valor),
        key=chave,
        type="phone",
        icon="",
        placeholder="000.000.000-00",
        max_chars=14,
        autocomplete="off",
        validate=(REGEX_CPF, "CPF: informe os 11 números, por exemplo 529.982.247-25."),
    )


def campo_telefone(rotulo, valor, chave, ajuda=None):
    """Telefone com DDD: teclado numérico e máscara `(11) 91234-5678`."""
    return st.text_input(
        rotulo,
        formatar_telefone(valor),
        key=chave,
        type="phone",
        icon="",
        placeholder="(11) 91234-5678",
        max_chars=15,
        help=ajuda,
        autocomplete="tel",
        validate=(REGEX_TELEFONE, f"{rotulo}: informe DDD e número, por exemplo (11) 91234-5678."),
    )


def campo_email(rotulo, valor, chave):
    """E-mail: teclado de e-mail no celular e erro ao lado do campo. Opcional (vazio passa)."""
    return st.text_input(
        rotulo,
        valor or "",
        key=chave,
        type="email",
        placeholder="nome@exemplo.com",
        autocomplete="email",
        validate=(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", f"{rotulo}: use o formato nome@exemplo.com."),
    )


def campo_placa(rotulo, valor, chave, obrigatorio=False):
    """Placa antiga ou Mercosul, exibida como `ABC-1D23`; o serviço guarda `ABC1D23`."""
    nome = rotulo_obrigatorio(rotulo) if obrigatorio else rotulo
    return st.text_input(
        nome,
        texto_placa(valor),
        key=chave,
        placeholder="ABC-1D23",
        max_chars=8,
        autocomplete="off",
        validate=(REGEX_PLACA, "Placa: use ABC1234 ou ABC1D23."),
    )


# ------------------------------------------------------------------- rodapé --


def rodape_formulario(
    confirmar,
    chave,
    formulario=False,
    desabilitado=False,
    motivo=None,
    perigo=False,
    cancelar="Cancelar",
    icone=None,
):
    """Rodapé de formulário: `Cancelar` e a ação principal, com a principal por último na ordem de
    leitura. Em tela estreita as duas empilham em largura total (consulta ao próprio rodapé, não à
    janela, então vale também dentro de diálogos).

    - `formulario=True`: botões de envio de um `st.form`; senão, `st.button`.
    - `desabilitado` + `motivo`: a confirmação fica indisponível e o motivo aparece escrito acima
      dos botões (nunca só em dica). Dentro de `st.form` os valores só chegam ao enviar, então ali
      o motivo vem da validação do envio, não daqui.
    - `perigo=True`: ação destrutiva (borda e texto de perigo).
    - `cancelar=None` omite o botão de cancelar.
    - Ao confirmar, o botão vira `Salvando…` e não aceita outro clique (script em `feedback.py`); ao cancelar,
      a chave de operação de mesmo nome (`feedback.chave_operacao(chave, ...)`) é descartada.
    Devolve `Acao(confirmou, cancelou)`; quem chama decide o que limpar e se reexecuta."""
    botao = st.form_submit_button if formulario else st.button
    with st.container(key=f"rodape_{chave}"):
        if desabilitado and motivo:
            st.markdown(
                f'<div class="rodape-form__motivo" role="status">{escape(motivo)}</div>',
                unsafe_allow_html=True,
            )
        cancelou = bool(cancelar) and botao(cancelar, key=f"{chave}_cancelar", icon=None)
        confirmou = botao(
            confirmar,
            key=f"perigo_{chave}_confirmar" if perigo else f"{chave}_salvar",
            type="primary",
            icon=icone,
            disabled=desabilitado,
        )
    if cancelou:
        encerrar_operacao(chave)
    return Acao(confirmou, cancelou)
