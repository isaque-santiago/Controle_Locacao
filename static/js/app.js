/* Comportamentos da interface (sem dependências): diálogos, abas, filtros em chips e tema.
   Usa delegação de eventos, então continua valendo para o que o HTMX troca na página. */
(function () {
  'use strict';

  // ---- Diálogos: data-abrir="id" abre; data-fechar fecha; clique no fundo fecha ----
  document.addEventListener('click', function (e) {
    var abrir = e.target.closest('[data-abrir]');
    if (abrir) {
      var alvo = document.getElementById(abrir.getAttribute('data-abrir'));
      if (alvo && alvo.showModal) alvo.showModal();
      return;
    }
    var fechar = e.target.closest('[data-fechar]');
    if (fechar) {
      var dialogo = fechar.closest('dialog');
      if (dialogo) dialogo.close();
      return;
    }
    if (e.target.tagName === 'DIALOG') e.target.close();
  });

  // ---- Abas: clique e setas, Home e End ----
  function irParaAba(lista, aba) {
    lista.querySelectorAll('[role="tab"]').forEach(function (a) {
      var selecionada = a === aba;
      a.setAttribute('aria-selected', selecionada ? 'true' : 'false');
      a.tabIndex = selecionada ? 0 : -1;
      var painel = document.getElementById(a.getAttribute('aria-controls'));
      if (painel) painel.hidden = !selecionada;
    });
    aba.focus();
  }
  document.addEventListener('click', function (e) {
    var aba = e.target.closest('[role="tab"]');
    if (aba) irParaAba(aba.closest('[role="tablist"]'), aba);
  });
  document.addEventListener('keydown', function (e) {
    var aba = e.target.closest && e.target.closest('[role="tab"]');
    if (!aba) return;
    var lista = aba.closest('[role="tablist"]');
    var abas = Array.prototype.slice.call(lista.querySelectorAll('[role="tab"]'));
    var i = abas.indexOf(aba);
    var proxima = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: abas.length - 1 }[e.key];
    if (proxima === undefined) return;
    e.preventDefault();
    irParaAba(lista, abas[(proxima + abas.length) % abas.length]);
  });

  // ---- Chips de filtro em botão: um pressionado por grupo. Chips em link (<a>) vêm prontos do servidor ----
  document.addEventListener('click', function (e) {
    var chip = e.target.closest('button.chip');
    if (!chip) return;
    var grupo = chip.closest('.chips');
    if (!grupo) return;
    grupo.querySelectorAll('.chip').forEach(function (c) {
      c.setAttribute('aria-pressed', c === chip ? 'true' : 'false');
    });
  });

  // ---- Tema: automático -> escuro -> claro. O servidor lê o cookie e já envia data-tema ----
  var ORDEM = ['', 'escuro', 'claro'];
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-alternar-tema]')) return;
    var raiz = document.documentElement;
    var atual = raiz.getAttribute('data-tema') || '';
    var proximo = ORDEM[(ORDEM.indexOf(atual) + 1) % ORDEM.length];
    if (proximo) raiz.setAttribute('data-tema', proximo); else raiz.removeAttribute('data-tema');
    var seguro = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = 'tema=' + proximo + '; path=/; max-age=' + (proximo ? 31536000 : 0) + '; SameSite=Lax' + seguro;
  });

  // ---- Depois de uma troca do HTMX, devolve o foco ao conteúdo principal (leitores de tela) ----
  document.body.addEventListener('htmx:afterSettle', function (e) {
    if (e.detail.target && e.detail.target.id === 'conteudo') e.detail.target.focus({ preventScroll: true });
  });
})();
