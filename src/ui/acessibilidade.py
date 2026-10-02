"""Ajustes de acessibilidade na marcação que o Streamlit gera e o app não controla.

A auditoria automatizada (axe-core, Etapa 9) e o teste de teclado acusaram problemas na marcação do
próprio Streamlit que nenhum parâmetro de `st.*` corrige:

- `aria-expanded` no `<section>` da barra lateral e no campo de data (atributo não permitido nesses
  elementos). O estado da barra continua em `data-expandida`, que os testes de navegador usam;
- barra lateral recolhida (celular): os links continuam na ordem de tabulação, fora da tela. Com a barra
  recolhida ela vira `inert` (some da tabulação e dos leitores de tela) e volta ao abrir;
- a lista de navegação (`<ul>`) tem `<div>` como filhos diretos e, dentro deles, `<header>` ao lado dos
  `<li>`: o `<ul>` vira apresentação e cada grupo vira a lista;
- o componente invisível de cookies (iframe sem conteúdo visual) era uma parada de Tab fora da tela:
  recebe `tabindex="-1"` e `aria-hidden`;
- sem marcos de página (landmarks): a região principal ganha `role="main"` e a barra lateral
  `role="complementary"` com nome.

`tema.aplicar` injeta este script junto com o do estado ocupado, num único `st.html` (cada
`st.html` é um bloco com espaçamento próprio e mudaria a altura da página).

O script só mexe em atributos, é idempotente e não faz nada se a marcação mudar numa versão futura do
Streamlit (os seletores deixam de casar).
"""

SCRIPT_A11Y = """
(function () {
  if (window.__locacaoA11y) return;
  window.__locacaoA11y = true;
  var agendado = false;
  function papel(el, valor) {
    if (el && el.getAttribute('role') !== valor) el.setAttribute('role', valor);
  }
  function ajustar() {
    agendado = false;
    var barra = document.querySelector('[data-testid="stSidebar"]');
    if (barra) {
      if (barra.hasAttribute('aria-expanded')) {
        barra.setAttribute('data-expandida', barra.getAttribute('aria-expanded'));
        barra.removeAttribute('aria-expanded');
      }
      var recolhida = barra.getAttribute('data-expandida') === 'false';
      if (barra.inert !== recolhida) barra.inert = recolhida;
      papel(barra, 'complementary');
      if (!barra.hasAttribute('aria-label')) barra.setAttribute('aria-label', 'Menu e conta');
    }
    papel(document.querySelector('[data-testid="stMain"]'), 'main');
    document.querySelectorAll('[data-testid="stDateInputField"][aria-expanded]').forEach(function (campo) {
      campo.removeAttribute('aria-expanded');
    });
    document.querySelectorAll('iframe[title^="streamlit_cookies_controller"]').forEach(function (quadro) {
      if (quadro.getAttribute('tabindex') !== '-1') quadro.setAttribute('tabindex', '-1');
      if (quadro.getAttribute('aria-hidden') !== 'true') quadro.setAttribute('aria-hidden', 'true');
    });
    var nav = document.querySelector('ul[data-testid="stSidebarNavItems"]');
    if (!nav) return;
    papel(nav, 'presentation');
    nav.querySelectorAll(':scope > div').forEach(function (grupo) {
      papel(grupo, 'list');
      papel(grupo.querySelector(':scope > header'), 'presentation');
    });
  }
  function agendar() {
    if (agendado) return;
    agendado = true;
    requestAnimationFrame(ajustar);
  }
  new MutationObserver(agendar).observe(document.body, {
    childList: true, subtree: true, attributes: true, attributeFilter: ['aria-expanded'],
  });
  agendar();
})();
"""
