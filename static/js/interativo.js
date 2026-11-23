/* Interatividade do painel: busca global (paleta), gaveta de pré-visualização e atalhos de teclado.
   Sem dependências; usa delegação de eventos, então vale também para o que o HTMX troca na página.
   Tudo é melhoria progressiva: sem este arquivo, /busca e as fichas continuam funcionando como páginas. */
(function () {
  'use strict';

  function emCampoDeTexto(alvo) {
    var tag = alvo && alvo.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || !!(alvo && alvo.isContentEditable);
  }

  // ---- Busca global (paleta): Ctrl+K abre sempre; "/" abre quando a página não tem campo de busca próprio ----
  var dlgBusca = function () { return document.getElementById('dlg-busca'); };
  var campoBusca = function () { return document.getElementById('busca-global'); };
  var itensBusca = function () { return Array.prototype.slice.call(document.querySelectorAll('#busca-resultados [data-busca-item]')); };

  function prepararBusca() {
    var dialogo = dlgBusca(), campo = campoBusca();
    if (!dialogo || !campo) return;
    // Modo "ocultar dados pessoais" (?ocultar=1 no Dashboard): a paleta herda e o servidor mascara os resultados
    var oculto = dialogo.querySelector('[data-busca-ocultar]');
    if (oculto) oculto.disabled = new URLSearchParams(location.search).get('ocultar') !== '1';
    campo.focus();
    campo.select();
  }
  function abrirBusca() {
    var dialogo = dlgBusca();
    if (!dialogo || !dialogo.showModal) return false;
    if (!dialogo.open) dialogo.showModal();
    prepararBusca();
    return true;
  }
  function marcarItemBusca(indice) {
    var itens = itensBusca();
    var campo = campoBusca();
    itens.forEach(function (el, i) {
      var ativo = i === indice;
      el.classList.toggle('ativo', ativo);
      el.setAttribute('aria-selected', ativo ? 'true' : 'false');
      if (ativo) {
        if (campo) campo.setAttribute('aria-activedescendant', el.id);
        if (el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
      }
    });
    if (!itens.length && campo) campo.removeAttribute('aria-activedescendant');
  }
  function indiceAtivoBusca() {
    var itens = itensBusca();
    for (var i = 0; i < itens.length; i++) if (itens[i].classList.contains('ativo')) return i;
    return -1;
  }
  // Resultados novos: dá id a cada item (o campo aponta para o ativo por aria-activedescendant) e ativa o primeiro
  function prepararResultadosBusca() {
    itensBusca().forEach(function (el, i) { el.id = 'busca-item-' + i; });
    marcarItemBusca(itensBusca().length ? 0 : -1);
  }
  document.body.addEventListener('htmx:afterSwap', function (e) {
    var alvo = e.detail.target;
    if (alvo && (alvo.id === 'busca-resultados' || (alvo.closest && alvo.closest('#busca-resultados')))) prepararResultadosBusca();
  });
  document.addEventListener('click', function (e) {
    var gatilho = e.target.closest('[data-abrir="dlg-busca"]');
    if (gatilho) window.setTimeout(prepararBusca, 0);  // o app.js já abriu o diálogo; aqui só se prepara o campo
  });
  document.addEventListener('keydown', function (e) {
    // Dentro da paleta: setas, Home/End e Enter
    var campo = campoBusca();
    if (campo && e.target === campo) {
      var itens = itensBusca();
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!itens.length) return;
        e.preventDefault();
        var atual = indiceAtivoBusca();
        var proximo = e.key === 'ArrowDown' ? atual + 1 : atual - 1;
        marcarItemBusca((proximo + itens.length) % itens.length);
        return;
      }
      if (e.key === 'Enter' && !e.isComposing) {
        var i = indiceAtivoBusca();
        if (i >= 0) {  // há resultado: Enter abre a ficha do item marcado em vez de buscar de novo
          e.preventDefault();
          location.assign(itens[i].getAttribute('href'));
        }
      }
      return;
    }
    if (e.defaultPrevented || e.isComposing || e.altKey) return;
    // Ctrl+K (ou Cmd+K): abre a paleta de qualquer lugar, até de dentro de um campo
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'k') {
      if (document.querySelector('dialog[open]:not(#dlg-busca)')) return;
      e.preventDefault();
      abrirBusca();
      return;
    }
    // "/": o app.js leva ao campo de busca da página, se houver; sem ele, abre a paleta
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !emCampoDeTexto(e.target) && !document.querySelector('dialog[open]')) {
      if (document.querySelector('main input[type="search"]')) return;
      e.preventDefault();
      abrirBusca();
    }
  });

  // ---- Gaveta de pré-visualização: o app.js abre o diálogo quando o HTMX troca #gaveta-conteudo; aqui cuida-se do foco ----
  // Ao abrir, o foco vai ao título (leitor de tela anuncia o conteúdo); ao fechar, o conteúdo é esvaziado e o foco volta ao botão de origem.
  var origemGaveta = null;
  document.body.addEventListener('htmx:beforeRequest', function (e) {
    if (e.detail.target && e.detail.target.id === 'gaveta-conteudo') origemGaveta = e.detail.elt;
  });
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (!e.detail.target || e.detail.target.id !== 'gaveta-conteudo') return;
    var titulo = document.getElementById('gaveta-titulo');
    if (titulo) titulo.focus({ preventScroll: true });
  });
  document.addEventListener('close', function (e) {
    if (!e.target || e.target.id !== 'dlg-gaveta') return;
    var conteudo = document.getElementById('gaveta-conteudo');
    if (conteudo) conteudo.innerHTML = '';
    if (origemGaveta && origemGaveta.isConnected) origemGaveta.focus({ preventScroll: true });
    origemGaveta = null;
  }, true);
  // Navegar pela gaveta (link "Abrir ficha completa") não deve deixar o diálogo aberto no histórico
  window.addEventListener('pagehide', function () {
    var gaveta = document.getElementById('dlg-gaveta');
    if (gaveta && gaveta.open) gaveta.close();
  });

  // ---- Ação em linha concluída (ex.: pagar a cobrança): o servidor já atualizou a lista fora de banda e manda fechar o diálogo ----
  document.body.addEventListener('dialogo-concluido', function () {
    var dialogo = document.getElementById('dlg-form');
    if (!dialogo) return;
    dialogo.removeAttribute('data-alterado');  // concluiu: não há o que "descartar"
    if (dialogo.open) dialogo.close();
    var avisos = document.getElementById('avisos');
    if (avisos && avisos.scrollIntoView) avisos.scrollIntoView({ block: 'nearest' });
  });

  // ---- Atalhos de teclado: "g" e depois uma letra vai a uma página ("g v" Veículos, "g c" Clientes, "g o" Contratos...); "?" lista os atalhos ----
  // Os destinos vêm da janela de atalhos (links com data-atalho-ir), a mesma lista que o dono lê: uma fonte só.
  // Só sem modificadores, fora de campos de texto e sem diálogo aberto. A segunda tecla tem 1,5 s para chegar.
  var esperandoG = null;
  function cancelarG() { window.clearTimeout(esperandoG); esperandoG = null; }
  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (emCampoDeTexto(e.target) || document.querySelector('dialog[open]')) { cancelarG(); return; }
    if (esperandoG !== null) {
      cancelarG();
      var destino = document.querySelector('[data-atalho-ir="' + e.key.toLowerCase().replace(/"/g, '') + '"]');
      if (destino && e.key.length === 1) {
        e.preventDefault();
        location.assign(destino.getAttribute('href'));
      }
      return;
    }
    if (e.key === 'g') {
      esperandoG = window.setTimeout(cancelarG, 1500);
    } else if (e.key === '?') {
      var janela = document.getElementById('dlg-atalhos');
      if (janela && janela.showModal) { e.preventDefault(); janela.showModal(); }
    }
  });
})();
