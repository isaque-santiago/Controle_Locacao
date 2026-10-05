"""Feedback de operações: confirmação, erro, estado ocupado e nova tentativa (Etapa 7 do plano de UI/UX).

- **Sucesso**: `concluir(aviso)` guarda a mensagem (`src.domain.mensagens`) e reexecuta a página; a
  mensagem aparece depois do `st.rerun()` (`exibir_pendentes`, chamado por `cabecalho`), como toast
  para confirmações simples ou alerta persistente quando há o que fazer em seguida.
- **Falha**: `exibir_falha` mostra o texto de `src.domain.erros.classificar_erro` com aparência e ação
  próprias: validação (corrigir), sessão expirada (entrar de novo), sem permissão, indisponibilidade
  (tentar novamente).
- **Envio**: o estado `Salvando…` e o bloqueio do segundo clique vêm de um pequeno script no navegador
  (`SCRIPT_OCUPADO`, injetado por `tema.aplicar`), que age no instante do clique, sem esperar a ida e volta ao servidor.
  A proteção de verdade é a chave de operação (`chave_operacao`): o banco recusa a segunda gravação.
"""

from itertools import count

import streamlit as st
from streamlit.errors import StreamlitAPIException

from src.domain import erros, operacoes
from src.domain.mensagens import ALERTA

_PENDENTES = "feedback_pendentes"
_PREFIXO_OPERACAO = "operacao_"
_contador_botoes = count(1)

_ICONE_SUCESSO = ":material/check_circle:"
_ICONE_ATENCAO = ":material/warning:"

def _md(texto):
    """Toasts e alertas do Streamlit são Markdown: dois `R$` no mesmo texto viram uma fórmula e o cifrão some."""
    return str(texto).replace("$", r"\$")


# ------------------------------------------------------------------ sucesso --


def avisar(aviso):
    """Guarda o aviso para a próxima execução da página (não reexecuta)."""
    st.session_state.setdefault(_PENDENTES, []).append((aviso.texto, aviso.tom, aviso.atencao))


def concluir(aviso, operacao=None):
    """Confirma uma operação: guarda o aviso, encerra a chave de operação (`operacao` é o nome usado em
    `chave_operacao`) e reexecuta a página, que exibe a mensagem."""
    avisar(aviso)
    if operacao:
        encerrar_operacao(operacao)
    st.rerun()


def exibir_pendentes():
    """Mostra e descarta os avisos guardados. Toast: some sozinho, para confirmações simples.
    Alerta: fica visível até a próxima ação da pessoa, para o que pede atenção ou um próximo passo."""
    pendentes = st.session_state.pop(_PENDENTES, [])
    alertas = [item for item in pendentes if item[1] == ALERTA]
    for texto, tom, _ in pendentes:
        if tom != ALERTA:
            st.toast(_md(texto), icon=_ICONE_SUCESSO, duration="long")
    if alertas:
        with st.container(key="feedback_alertas"):
            for texto, _, atencao in alertas:
                if atencao:
                    st.warning(_md(texto), icon=_ICONE_ATENCAO)
                else:
                    st.success(_md(texto), icon=_ICONE_SUCESSO)


# ------------------------------------------------------- chave de operação --


def chave_operacao(nome, conteudo):
    """Chave (uuid) do envio em andamento. Repetir o mesmo conteúdo reaproveita a chave, e o banco devolve o
    registro já gravado; conteúdo diferente é outra operação e ganha chave nova. `nome` é o mesmo da chave
    do rodapé do formulário (`rodape_formulario(..., chave=nome)`), que descarta a chave ao cancelar."""
    estado = st.session_state.get(_PREFIXO_OPERACAO + nome)
    par = operacoes.chave_para(estado, conteudo)
    st.session_state[_PREFIXO_OPERACAO + nome] = par
    return par[1]


def encerrar_operacao(nome):
    st.session_state.pop(_PREFIXO_OPERACAO + nome, None)


# -------------------------------------------------------------------- falha --


def _sair():
    from src.auth import logout

    logout()


def _botao_se_possivel(rotulo, on_click=None):
    """Botão de ação da falha. Dentro de `st.form` o Streamlit não aceita `st.button`: ali o texto da
    mensagem já diz o que fazer, então a falta do botão não esconde nada."""
    try:
        st.button(rotulo, key=f"feedback_acao_{next(_contador_botoes)}", on_click=on_click)
    except StreamlitAPIException:
        return False
    return True


def exibir_falha(falha, nova_tentativa=False):
    """Mostra uma falha classificada (`classificar_erro`), cada categoria com o seu ícone e a sua ação:

    - validação: corrigir o que foi preenchido (nada a repetir);
    - sessão expirada: `Entrar novamente`;
    - sem permissão: informa, sem repetir;
    - indisponibilidade: `Tentar novamente` (`nova_tentativa=True`, consultas) ou, em formulários, a
      orientação de enviar de novo, já que o que foi digitado continua nos campos."""
    categoria = falha.categoria
    mensagem = _md(falha.mensagem)
    if categoria == erros.VALIDACAO:
        st.error(mensagem, icon=":material/edit_note:")
    elif categoria == erros.SESSAO_EXPIRADA:
        st.warning(mensagem, icon=":material/lock_clock:")
        if not _botao_se_possivel("Entrar novamente", on_click=_sair):
            st.caption("Recarregue a página para entrar novamente.")
    elif categoria == erros.SEM_PERMISSAO:
        st.error(mensagem, icon=":material/lock:")
    elif categoria in (erros.INDISPONIVEL, erros.DESCONHECIDO) and falha.recuperavel:
        if nova_tentativa:
            st.error(mensagem, icon=":material/cloud_off:")
            _botao_se_possivel("Tentar novamente")
        else:
            st.error(
                f"{mensagem} O que você digitou continua no formulário; envie de novo.",
                icon=":material/cloud_off:",
            )
    else:
        st.error(mensagem, icon=":material/error:")


# --------------------------------------------------------- estado ocupado --

# Botões de confirmação dos rodapés (`rodape_*`) e os de chave `ocupa_*` viram `Salvando…` (a cor, o rótulo
# e o bloqueio vêm de estilos.css, pelo atributo `data-ocupado`). O estado termina quando a execução do
# script acaba (sucesso, erro ou fechamento do diálogo) ou, se o clique nem chegou a iniciar uma execução
# (campo inválido no navegador), depois de 1,5 s.
SCRIPT_OCUPADO = """
(function () {
  if (window.__locacaoOcupado) return;
  window.__locacaoOcupado = true;
  var ALVOS = '[class*="st-key-rodape_"] button[data-testid^="stBaseButton-primary"], [class*="st-key-ocupa_"] button';
  var espera = null;
  function executando() {
    var app = document.querySelector('[data-testid="stApp"]');
    return !!app && app.getAttribute('data-test-script-state') === 'running';
  }
  function liberar() {
    clearTimeout(espera);
    document.querySelectorAll('button[data-ocupado]').forEach(function (b) {
      b.removeAttribute('data-ocupado');
      b.removeAttribute('aria-busy');
    });
  }
  document.addEventListener('click', function (evento) {
    var botao = evento.target.closest && evento.target.closest('button');
    if (!botao || !botao.matches(ALVOS)) return;
    if (botao.hasAttribute('data-ocupado')) {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      return;
    }
    botao.setAttribute('data-ocupado', '');
    botao.setAttribute('aria-busy', 'true');
    clearTimeout(espera);
    espera = setTimeout(function () { if (!executando()) liberar(); }, 1500);
  }, true);
  new MutationObserver(function () {
    if (!executando()) liberar();
  }).observe(document.body, { attributes: true, subtree: true, attributeFilter: ['data-test-script-state'] });
})();
"""
