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
  // Abas com data-remoto carregam o painel pelo HTMX (um painel só): o JS não esconde painéis e,
  // ao navegar por setas, só move o foco; Enter ou Espaço (clique) é que abre a aba.
  function irParaAba(lista, aba, soFoco) {
    var remota = aba.hasAttribute('data-remoto');
    lista.querySelectorAll('[role="tab"]').forEach(function (a) {
      var selecionada = a === aba;
      if (!(remota && soFoco)) a.setAttribute('aria-selected', selecionada ? 'true' : 'false');
      a.tabIndex = selecionada ? 0 : -1;
      if (remota) return;
      var painel = document.getElementById(a.getAttribute('aria-controls'));
      if (painel) painel.hidden = !selecionada;
    });
    aba.focus();
  }
  document.addEventListener('click', function (e) {
    var aba = e.target.closest('[role="tab"]');
    // Abas remotas: quem marca a aba selecionada é a resposta do servidor (o HTMX troca as abas junto do painel)
    if (aba && !aba.hasAttribute('data-remoto')) irParaAba(aba.closest('[role="tablist"]'), aba);
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
    var destino = abas[(proxima + abas.length) % abas.length];
    irParaAba(lista, destino, destino.hasAttribute('data-remoto'));
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

  // ---- Troca parcial do HTMX: se o elemento focado vai ser substituído (chip, paginação, seletor),
  // devolve o foco ao equivalente na lista nova; sem equivalente, ao próprio trecho trocado ----
  var focoAntes = null;
  var focoPorId = null;
  document.body.addEventListener('htmx:beforeSwap', function (e) {
    var ativo = document.activeElement;
    var alvo = e.detail.target;
    var dentro = ativo && ativo !== document.body && alvo && alvo.contains(ativo) && alvo !== ativo;
    var grupo = dentro ? ativo.closest('nav') : null;
    focoPorId = ativo && ativo !== document.body && ativo.id ? ativo.id : null;
    focoAntes = dentro ? { id: ativo.id, href: ativo.getAttribute('href'), texto: (ativo.textContent || '').trim(), grupo: grupo ? grupo.className : '' } : null;
  });
  document.body.addEventListener('htmx:afterSettle', function (e) {
    if (focoPorId && (!document.activeElement || document.activeElement === document.body)) {
      var mesmo = document.getElementById(focoPorId);
      if (mesmo) mesmo.focus({ preventScroll: true });
    }
    focoPorId = null;
    if (!focoAntes) return;
    var alvo = e.detail.target;
    var igual = null;
    if (focoAntes.id) igual = document.getElementById(focoAntes.id);
    if (!igual && focoAntes.href) {
      igual = Array.prototype.slice.call(alvo.querySelectorAll('a[href]')).filter(function (a) {
        return a.getAttribute('href') === focoAntes.href;
      })[0];
    }
    if (!igual && focoAntes.grupo) {
      // Mesmo botão no mesmo grupo (ex.: "Próxima" da paginação, cujo endereço mudou)
      igual = Array.prototype.slice.call(alvo.querySelectorAll('nav.' + focoAntes.grupo.split(' ')[0] + ' a, nav.' + focoAntes.grupo.split(' ')[0] + ' button:not([disabled])')).filter(function (b) {
        return (b.textContent || '').trim() === focoAntes.texto;
      })[0];
    }
    focoAntes = null;
    if (igual) igual.focus({ preventScroll: true });
    else if (alvo.hasAttribute('tabindex')) alvo.focus({ preventScroll: true });
  });

  // ---- Diálogos de formulário carregados pelo HTMX: abrem quando o conteúdo chega e se esvaziam ao fechar ----
  document.body.addEventListener('htmx:afterSwap', function (e) {
    var alvo = e.detail.target;
    var dialogo = alvo && alvo.closest ? alvo.closest('dialog') : null;
    if (dialogo && !dialogo.open) {
      dialogo.showModal();
      // Foco no primeiro campo (com o conteúdo selecionado, para digitar por cima do valor atual)
      var primeiro = dialogo.querySelector('input:not([type="hidden"]):not([type="checkbox"]), select, textarea');
      if (primeiro) {
        primeiro.focus();
        if (primeiro.select && primeiro.type !== 'date') primeiro.select();
      }
    }
  });
  document.addEventListener('close', function (e) {
    var dialogo = e.target;
    if (dialogo && dialogo.id === 'dlg-form') {
      var conteudo = document.getElementById('dlg-form-conteudo');
      if (conteudo) conteudo.innerHTML = '';
    }
  }, true);
  // Formulário devolvido com erro: leva o foco ao primeiro campo inválido
  document.body.addEventListener('htmx:afterSettle', function () {
    var invalido = document.querySelector('#form-dialogo [aria-invalid="true"]');
    if (invalido) invalido.focus();
  });

  // ---- Depois de uma troca do HTMX, devolve o foco ao conteúdo principal (leitores de tela) ----
  document.body.addEventListener('htmx:afterSettle', function (e) {
    if (e.detail.target && e.detail.target.id === 'conteudo') e.detail.target.focus({ preventScroll: true });
  });
})();
