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
      fecharDialogo(fechar.closest('dialog'));
      return;
    }
    if (e.target.tagName === 'DIALOG') fecharDialogo(e.target);
  });

  // ---- Formulário em diálogo (#dlg-form): avisa antes de fechar com alterações não enviadas ----
  // O marcador fica no <dialog>: sobrevive à troca do formulário com erro de validação e some ao abrir outro conteúdo.
  var dlgForm = function () { return document.getElementById('dlg-form'); };
  function fecharDialogo(dialogo) {
    if (!dialogo) return;
    if (dialogo.id !== 'dlg-form' || !dialogo.hasAttribute('data-alterado')) { dialogo.close(); return; }
    var origem = document.createElement('span');
    origem.setAttribute('data-confirmar-titulo', 'Descartar alterações?');
    origem.setAttribute('data-confirmar-rotulo', 'Descartar');
    pedirConfirmacao(origem, 'O que você preencheu e não enviou será perdido.', function () { dialogo.removeAttribute('data-alterado'); dialogo.close(); });
  }
  function marcarAlterado(e) {
    var dialogo = dlgForm();
    if (dialogo && e.target.closest && e.target.closest('#dlg-form form')) dialogo.setAttribute('data-alterado', '');
  }
  document.addEventListener('input', marcarAlterado);
  document.addEventListener('change', marcarAlterado);
  document.addEventListener('cancel', function (e) {  // Esc
    if (e.target.id === 'dlg-form' && e.target.hasAttribute('data-alterado')) {
      e.preventDefault();
      fecharDialogo(e.target);
    }
  }, true);
  document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target && e.detail.target.id === 'dlg-form-conteudo' && dlgForm()) dlgForm().removeAttribute('data-alterado');
  });
  document.addEventListener('close', function (e) {
    if (e.target && e.target.id === 'dlg-form') e.target.removeAttribute('data-alterado');
  }, true);

  // ---- Fotos grandes: reduz no navegador antes do envio (campos input[data-reduzir-foto]) ----
  // A foto de câmera em resolução máxima (64 MP, 10 a 15 MB) passa do limite de 10 MB do servidor. Só mexe em JPEG/PNG acima de
  // 4 MB: redesenha com no máximo 3000 px no lado maior e salva em JPEG (o redesenho aplica a orientação e não leva os metadados).
  var FOTO_LIMITE_BYTES = 4 * 1024 * 1024, FOTO_LADO_MAXIMO = 3000, FOTO_QUALIDADE = 0.85;
  var megas = function (bytes) { return (bytes / 1048576).toFixed(1).replace('.', ',') + ' MB'; };

  function reduzirFoto(arquivo) {
    if (!/^image\/(jpeg|png)$/.test(arquivo.type) || arquivo.size <= FOTO_LIMITE_BYTES || !window.createImageBitmap) {
      return Promise.resolve(arquivo);
    }
    return createImageBitmap(arquivo, { imageOrientation: 'from-image' }).then(function (imagem) {
      var escala = Math.min(1, FOTO_LADO_MAXIMO / Math.max(imagem.width, imagem.height));
      var tela = document.createElement('canvas');
      tela.width = Math.round(imagem.width * escala);
      tela.height = Math.round(imagem.height * escala);
      var contexto = tela.getContext('2d');
      contexto.fillStyle = '#fff';  // PNG com transparência vira fundo branco no JPEG
      contexto.fillRect(0, 0, tela.width, tela.height);
      contexto.drawImage(imagem, 0, 0, tela.width, tela.height);
      if (imagem.close) imagem.close();
      return new Promise(function (resolver) {
        tela.toBlob(function (blob) {
          if (!blob || blob.size >= arquivo.size) { resolver(arquivo); return; }
          resolver(new File([blob], arquivo.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg', lastModified: arquivo.lastModified }));
        }, 'image/jpeg', FOTO_QUALIDADE);
      });
    }).catch(function () { return arquivo; });  // HEIC e outros formatos que o navegador não abre seguem como estão
  }

  document.addEventListener('change', function (e) {
    var campo = e.target;
    if (!campo.matches || !campo.matches('input[type="file"][data-reduzir-foto]') || !campo.files || !window.DataTransfer) return;
    var originais = Array.prototype.slice.call(campo.files);
    if (!originais.some(function (a) { return a.size > FOTO_LIMITE_BYTES; })) return;
    var botoes = campo.form ? Array.prototype.filter.call(campo.form.querySelectorAll('button[type="submit"]'), function (b) { return !b.disabled; }) : [];
    var status = campo.parentNode.querySelector('[data-foto-status]');
    if (!status) {
      status = document.createElement('small');
      status.setAttribute('data-foto-status', '');
      status.setAttribute('role', 'status');
      campo.parentNode.insertBefore(status, campo.nextSibling);
    }
    botoes.forEach(function (b) { b.disabled = true; });  // o envio espera a redução terminar
    status.textContent = 'Reduzindo foto grande…';
    Promise.all(originais.map(reduzirFoto)).then(function (novos) {
      var lista = new DataTransfer();
      novos.forEach(function (f) { lista.items.add(f); });
      campo.files = lista.files;
      var antes = originais.reduce(function (s, a) { return s + a.size; }, 0);
      var depois = novos.reduce(function (s, a) { return s + a.size; }, 0);
      status.textContent = depois < antes ? 'Foto reduzida de ' + megas(antes) + ' para ' + megas(depois) + '.' : '';
    }).catch(function () { status.textContent = ''; }).then(function () {
      botoes.forEach(function (b) { b.disabled = false; });
    });
  });

  // ---- Envio de formulário comum (página inteira): bloqueia clique duplo e mostra o indicador no botão ----
  // Formulários do HTMX usam hx-sync/hx-disabled-elt; downloads não recarregam a página, então o bloqueio expira.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.classList || form.hasAttribute('hx-post')) return;
    if (form.hasAttribute('data-confirmar') && !form.hasAttribute('data-confirmado')) return;  // ainda vai perguntar
    if (form.hasAttribute('data-enviando')) { e.preventDefault(); return; }
    form.setAttribute('data-enviando', '');
    window.setTimeout(function () { form.removeAttribute('data-enviando'); }, 10000);
  });
  window.addEventListener('pageshow', function () {
    document.querySelectorAll('form[data-enviando]').forEach(function (f) { f.removeAttribute('data-enviando'); });
  });

  // ---- Confirmação de ações destrutivas ----
  // Elementos HTMX usam hx-confirm="texto"; formulários comuns usam data-confirmar="texto". Opcionais no
  // elemento: data-confirmar-titulo, data-confirmar-rotulo (botão de confirmar) e data-confirmar-neutro
  // (botão sem destaque de perigo). Em vez do confirm() do navegador, abre o <dialog id="dlg-confirmar">.
  var confirmarPendente = null;
  function pedirConfirmacao(origem, texto, aoConfirmar) {
    var dialogo = document.getElementById('dlg-confirmar');
    if (!dialogo || !dialogo.showModal) return window.confirm(texto) && (aoConfirmar(), true);
    var ok = document.getElementById('dlg-confirmar-ok');
    document.getElementById('dlg-confirmar-titulo').textContent = origem.getAttribute('data-confirmar-titulo') || 'Confirmar ação';
    document.getElementById('dlg-confirmar-texto').textContent = texto;
    ok.textContent = origem.getAttribute('data-confirmar-rotulo') || 'Confirmar';
    ok.classList.toggle('btn-perigo', !origem.hasAttribute('data-confirmar-neutro'));
    confirmarPendente = aoConfirmar;
    if (!dialogo.open) dialogo.showModal();
    return true;
  }
  document.addEventListener('click', function (e) {
    if (!e.target.closest('#dlg-confirmar-ok')) return;
    var acao = confirmarPendente;
    confirmarPendente = null;
    document.getElementById('dlg-confirmar').close();
    if (acao) acao();
  });
  document.addEventListener('close', function (e) {
    if (e.target && e.target.id === 'dlg-confirmar') confirmarPendente = null;
  }, true);
  // HTMX: intercepta a pergunta do hx-confirm e só dispara a requisição depois do "Confirmar"
  document.body.addEventListener('htmx:confirm', function (e) {
    if (!e.detail.question) return;
    e.preventDefault();
    pedirConfirmacao(e.detail.elt, e.detail.question, function () { e.detail.issueRequest(true); });
  });
  // Formulário comum: pergunta antes de enviar; depois do "Confirmar", reenvia sem perguntar de novo
  document.addEventListener('submit', function (e) {
    var form = e.target;
    var texto = form.getAttribute && form.getAttribute('data-confirmar');
    if (!texto || form.hasAttribute('data-confirmado')) return;
    e.preventDefault();
    var botao = e.submitter;
    pedirConfirmacao(form, texto, function () {
      form.setAttribute('data-confirmado', '');
      if (form.requestSubmit) form.requestSubmit(botao); else form.submit();
    });
  });

  // ---- Menu da conta e filtros colapsáveis (<details data-conta|data-filtro>): fecha ao clicar fora ou com Esc ----
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details[data-conta][open], details[data-filtro][open]').forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute('open');
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('details[data-conta][open], details[data-filtro][open]').forEach(function (d) { d.removeAttribute('open'); });
  });

  // ---- Mostrar/ocultar senha: data-alternar-senha="id-do-campo" ----
  document.addEventListener('click', function (e) {
    var botao = e.target.closest('[data-alternar-senha]');
    if (!botao) return;
    var campo = document.getElementById(botao.getAttribute('data-alternar-senha'));
    if (!campo) return;
    var mostrar = campo.type === 'password';
    campo.type = mostrar ? 'text' : 'password';
    botao.setAttribute('aria-pressed', mostrar ? 'true' : 'false');
    botao.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
  });

  // ---- Copiar texto: data-copiar="id-do-campo" copia o valor; data-copiar-aviso="id" recebe o resultado ----
  document.addEventListener('click', function (e) {
    var botao = e.target.closest('[data-copiar]');
    if (!botao) return;
    var campo = document.getElementById(botao.getAttribute('data-copiar'));
    var aviso = document.getElementById(botao.getAttribute('data-copiar-aviso'));
    if (!campo) return;
    function avisar(texto) { if (aviso) aviso.textContent = texto; }
    function selecionar() { campo.focus(); campo.select(); avisar('Texto selecionado: use Ctrl+C para copiar.'); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(campo.value).then(function () { avisar('Mensagem copiada.'); }, selecionar);
    } else {
      selecionar();
    }
  });

  // ---- Busca numa lista: <input data-filtrar-opcoes="id-do-select" data-filtrar-aviso="id-do-texto-de-contagem"> ----
  // Cada palavra digitada vale um ponto para a opção que a tem (sem diferenciar maiúsculas nem acentos; pontuação e espaço dentro
  // da placa não atrapalham: "hyf1f47" acha "HYF-1F47"). Aparecem as opções com ao menos um ponto, as que têm mais pontos primeiro;
  // assim "Gabriel Santos HYF1F47" acha o grupo "Gabriel - [HYF-1F47]" mesmo sem o sobrenome. A opção vazia e a que veio selecionada
  // do servidor ficam sempre no topo, para o formulário não mudar de valor sem querer; o que a pessoa escolher à mão também fica.
  // Se só uma opção tem todas as palavras, ela é selecionada. As opções saem do <select> e voltam (em vez de `hidden`, que o Safari
  // do iPhone ignora).
  var estadoBusca = new WeakMap();
  var PALAVRAS_FRACAS = { de: 1, da: 1, do: 1, das: 1, dos: 1, e: 1, la: 1 };
  function semAcento(texto) { return String(texto || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
  function palavrasDaBusca(texto) {
    return semAcento(texto).split(/[^a-z0-9]+/).filter(function (p) { return p.length > 1 && !PALAVRAS_FRACAS[p]; });
  }
  function filtrarOpcoes(campo) {
    var lista = document.getElementById(campo.getAttribute('data-filtrar-opcoes'));
    if (!lista) return;
    var aviso = document.getElementById(campo.getAttribute('data-filtrar-aviso'));
    if (!estadoBusca.has(lista)) {
      var inicial = Array.prototype.filter.call(lista.options, function (o) { return o.defaultSelected; })[0];
      var todas = Array.prototype.slice.call(lista.options).map(function (o, i) {
        var texto = semAcento(o.text);
        return { opcao: o, posicao: i, texto: texto, compacto: texto.replace(/[^a-z0-9]/g, '') };
      });
      estadoBusca.set(lista, { todas: todas, original: inicial ? inicial.value : '', auto: null, textoInicial: aviso ? aviso.textContent : '' });
    }
    var e = estadoBusca.get(lista);
    var atual = lista.value;
    var manual = (atual !== '' && atual !== e.original && atual !== e.auto) ? atual : null;  // escolhida pela pessoa
    var palavras = palavrasDaBusca(campo.value);
    for (var k = 0; k < e.todas.length; k++) {
      var item = e.todas[k], pontos = 0;
      if (item.opcao.value !== '') {
        palavras.forEach(function (p) { if (item.texto.indexOf(p) !== -1 || item.compacto.indexOf(p) !== -1) pontos++; });
      }
      item.pontos = pontos;
    }
    var buscando = palavras.length > 0;
    var casam = e.todas.filter(function (i) { return i.pontos > 0; });
    var completos = e.todas.filter(function (i) { return buscando && i.pontos === palavras.length; });
    var visiveis = e.todas.filter(function (i) {
      return !buscando || i.opcao.value === '' || i.opcao.value === e.original || i.opcao.value === manual || i.pontos > 0;
    });
    visiveis.sort(function (a, b) {
      function topo(i) { return i.opcao.value === '' ? 0 : (i.opcao.value === e.original ? 1 : 2); }
      if (!buscando) return a.posicao - b.posicao;
      return topo(a) - topo(b) || b.pontos - a.pontos || a.posicao - b.posicao;
    });
    while (lista.options.length) lista.remove(0);
    visiveis.forEach(function (i) { lista.add(i.opcao); });
    if (manual) {
      lista.value = manual;
    } else if (completos.length === 1) {
      lista.value = completos[0].opcao.value;
      e.auto = lista.value;
    } else {
      lista.value = e.original;
      e.auto = null;
    }
    if (aviso) {
      if (!buscando) aviso.textContent = e.textoInicial;
      else if (!casam.length) aviso.textContent = 'Nenhum grupo encontrado. Confira o nome ou a placa, ou cole o ID do grupo no campo abaixo.';
      else aviso.textContent = casam.length + (casam.length === 1 ? ' grupo encontrado' : ' grupos encontrados') +
        (completos.length && completos.length < casam.length ? ' (os que têm todas as palavras vêm primeiro)' : '') + '.';
    }
  }
  document.addEventListener('input', function (ev) {
    if (ev.target.matches && ev.target.matches('[data-filtrar-opcoes]')) filtrarOpcoes(ev.target);
  });
  // Enter no campo de busca não envia o formulário (a busca é só para achar a opção).
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches && e.target.matches('[data-filtrar-opcoes]')) e.preventDefault();
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

  // ---- Cartões recolhíveis no celular: [data-recolher] (botão do cabeçalho) abre/fecha o [data-recolhivel] que o contém ----
  document.addEventListener('click', function (e) {
    var gatilho = e.target.closest('[data-recolher]');
    if (!gatilho || gatilho.disabled) return;
    var cartao = gatilho.closest('[data-recolhivel]');
    if (!cartao) return;
    var aberto = cartao.classList.toggle('aberto');
    gatilho.setAttribute('aria-expanded', aberto ? 'true' : 'false');
  });
  // Em telas largas tudo fica aberto: o botão vira texto comum (desabilitado e fora da ordem de tabulação)
  var larga = window.matchMedia('(min-width: 720px)');
  function sincronizarRecolhiveis() {
    document.querySelectorAll('[data-recolher]').forEach(function (b) {
      b.disabled = larga.matches;
      if (larga.matches) b.removeAttribute('aria-expanded');
      else b.setAttribute('aria-expanded', b.closest('[data-recolhivel]').classList.contains('aberto') ? 'true' : 'false');
    });
  }
  document.addEventListener('DOMContentLoaded', sincronizarRecolhiveis);
  document.addEventListener('htmx:afterSettle', sincronizarRecolhiveis);
  if (larga.addEventListener) larga.addEventListener('change', sincronizarRecolhiveis);

  // ---- Grupos de selos (.selos): uma linha só. O que não cabe fica atrás de um botão "+N" que abre e fecha ----
  // O primeiro item (a placa, no caso da coluna Moto) nunca é escondido. Reavalia quando a largura muda (redimensionar, cartão aberto).
  function ajustarSelos(grupo) {
    var itens = Array.prototype.filter.call(grupo.children, function (el) { return !el.classList.contains('selos-mais'); });
    var antigo = grupo.querySelector('.selos-mais');
    if (antigo) grupo.removeChild(antigo);
    itens.forEach(function (el) { el.classList.remove('selos-oculto'); });
    grupo.style.width = '';
    if (itens.length < 2 || !grupo.offsetWidth) return;
    var topo = itens[0].offsetTop;
    var transborda = itens.some(function (el) { return el.offsetTop > topo + 2; });
    if (!transborda) return;
    // Trava a largura natural (com tudo à mostra): esconder selos não pode encolher a coluna e disparar nova medição
    grupo.style.width = grupo.getBoundingClientRect().width + 'px';
    var aberto = grupo.classList.contains('aberto');
    var botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'selo neutro selos-mais';
    botao.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    grupo.appendChild(botao);
    if (aberto) {
      botao.textContent = 'Mostrar menos';
      botao.title = 'Recolher os selos';
      return;
    }
    var ocultos = 0;
    function rotular() {
      botao.textContent = '+' + ocultos;
      botao.title = 'Mostrar mais ' + ocultos + (ocultos === 1 ? ' selo' : ' selos');
      botao.setAttribute('aria-label', botao.title);
    }
    rotular();
    for (var i = itens.length - 1; i > 0; i--) {
      // O topo é relido a cada volta: a célula centraliza o conteúdo na vertical e ele se move quando a altura do grupo muda
      var base = itens[0].offsetTop + 2;
      if (itens[i].offsetTop <= base && botao.offsetTop <= base) break;
      itens[i].classList.add('selos-oculto');
      ocultos++;
      rotular();
    }
  }
  var observadorSelos = window.ResizeObserver ? new ResizeObserver(function (registros) {
    registros.forEach(function (r) {
      var grupo = r.target, largura = Math.round(r.contentRect.width);
      if (grupo._larguraSelos === largura) return;
      grupo._larguraSelos = largura;
      ajustarSelos(grupo);
    });
  }) : null;
  function prepararSelos(raiz) {
    (raiz || document).querySelectorAll('.selos').forEach(function (g) {
      if (observadorSelos && !g._observadoSelos) { g._observadoSelos = true; observadorSelos.observe(g); }
      else ajustarSelos(g);
    });
  }
  document.addEventListener('click', function (e) {
    var botao = e.target.closest('.selos-mais');
    if (!botao) return;
    var grupo = botao.parentNode;
    grupo.classList.toggle('aberto');
    ajustarSelos(grupo);
  });
  document.addEventListener('DOMContentLoaded', function () { prepararSelos(); });
  document.addEventListener('htmx:afterSettle', function () { prepararSelos(); });
  window.addEventListener('load', function () { prepararSelos(); });
  var tempoSelos;
  window.addEventListener('resize', function () {
    clearTimeout(tempoSelos);
    tempoSelos = setTimeout(function () { document.querySelectorAll('.selos').forEach(ajustarSelos); }, 150);
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

  // ---- Foco por teclado em faixas com rolagem horizontal (chips, abas): garante que o item focado apareça inteiro ----
  document.addEventListener('focusin', function (e) {
    var item = e.target.closest && e.target.closest('.chips > *, .abas > *');
    if (item && item.scrollIntoView) item.scrollIntoView({ block: 'nearest', inline: 'nearest' });
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
    focoAntes = dentro ? { alvoId: alvo.id, id: ativo.id, href: ativo.getAttribute('href'), texto: (ativo.textContent || '').trim(), grupo: grupo ? grupo.className : '' } : null;
  });
  document.body.addEventListener('htmx:afterSettle', function (e) {
    if (focoPorId && (!document.activeElement || document.activeElement === document.body)) {
      var mesmo = document.getElementById(focoPorId);
      if (mesmo) mesmo.focus({ preventScroll: true });
    }
    focoPorId = null;
    if (!focoAntes) return;
    var alvo = e.detail.target;
    // Troca por outerHTML: o alvo antigo saiu do DOM, o equivalente novo tem o mesmo id
    if (!alvo.isConnected && focoAntes.alvoId) alvo = document.getElementById(focoAntes.alvoId) || alvo;
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
    if (invalido) {
      invalido.focus();
      return;
    }
    // Diálogo que troca de etapa (ex.: escolher o contrato -> formulário): o botão clicado saiu da página
    // e o foco se perderia; leva-o ao primeiro campo da nova etapa.
    var dialogo = document.getElementById('dlg-form');
    var formulario = document.getElementById('form-dialogo');
    if (dialogo && dialogo.open && formulario && !dialogo.contains(document.activeElement)) {
      var primeiro = formulario.querySelector('input:not([type="hidden"]):not([type="checkbox"]), select, textarea');
      if (primeiro) primeiro.focus();
    }
  });

  // Página inteira devolvida com erro de formulário (assistente de contrato, sem HTMX): foco no primeiro campo inválido
  var invalidoNaPagina = document.querySelector('main form [aria-invalid="true"]');
  if (invalidoNaPagina) invalidoNaPagina.focus();

  // ---- Formulários: validação imediata e navegação por seções ----
  // O servidor continua sendo quem decide (e src/domain, as regras): aqui só se antecipa o óbvio (obrigatório e formato) ao sair do
  // campo (blur) e ao enviar. Os formulários ganham novalidate para que as mensagens sejam as do app, não as bolhas do navegador.
  // Formulário validado: o do diálogo (#form-dialogo) ou qualquer um com .formulario.
  var CAMPO_IGNORADO = 'input[type="hidden"], input[type="submit"], input[type="button"], input[type="reset"], input[type="image"]';
  function formularioValidado(form) {
    return !!form && form.tagName === 'FORM' && (form.id === 'form-dialogo' || !!form.querySelector('.formulario'));
  }
  function campoDoFormulario(el) {
    if (!el || !el.matches || !el.matches('input, select, textarea') || el.matches(CAMPO_IGNORADO)) return false;
    return formularioValidado(el.form) && !!el.closest('.campo');
  }
  function visivel(el) { return !el.disabled && !el.closest('[hidden]') && el.getClientRects().length > 0; }
  function mensagemDoCampo(el) {
    var valor = el.type === 'file' ? (el.files && el.files.length ? 'x' : '') : el.value;
    if (el.required && (el.type === 'checkbox' ? !el.checked : !String(valor).trim())) {
      return el.tagName === 'SELECT' ? 'Escolha uma opção.' : (el.type === 'file' ? 'Escolha um arquivo.' : 'Preencha este campo.');
    }
    if (!valor) return '';
    var v = el.validity;
    if (v.typeMismatch) return el.type === 'email' ? 'Informe um e-mail válido, como nome@exemplo.com.' : 'Confira o formato deste campo.';
    if (v.badInput) return el.type === 'date' ? 'Informe uma data válida.' : 'Confira o valor deste campo.';
    if (v.patternMismatch) return el.title || 'Confira o formato deste campo.';
    if (v.tooLong) return 'Use no máximo ' + el.maxLength + ' caracteres.';
    if (v.rangeUnderflow || v.rangeOverflow) return 'Confira o valor: está fora do limite permitido.';
    return '';
  }
  function ligarDescricao(el, id, ligar) {
    var ids = (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(function (x) { return x && x !== id; });
    if (ligar) ids.push(id);
    if (ids.length) el.setAttribute('aria-describedby', ids.join(' ')); else el.removeAttribute('aria-describedby');
  }
  function iconeSvg(nome, classe) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'i ' + classe);
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    var uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    uso.setAttribute('href', '#i-' + nome);
    svg.appendChild(uso);
    return svg;
  }
  function limparEstado(el) {
    var campo = el.closest('.campo');
    if (!campo) return;
    campo.classList.remove('com-erro', 'ok');
    campo.querySelectorAll('.msg-erro').forEach(function (m) { ligarDescricao(el, m.id, false); m.remove(); });
    el.removeAttribute('aria-invalid');
    var ok = campo.querySelector('.campo-ok');
    if (ok) ok.remove();
  }
  function mostrarErro(el, texto) {
    limparEstado(el);
    var campo = el.closest('.campo');
    var id = (el.id || el.name) + '-erro';
    var msg = document.createElement('small');
    msg.className = 'msg-erro';
    msg.id = id;
    var span = document.createElement('span');
    span.textContent = texto;
    msg.appendChild(iconeSvg('alerta', ''));
    msg.appendChild(span);
    campo.appendChild(msg);
    campo.classList.add('com-erro');
    el.setAttribute('aria-invalid', 'true');
    ligarDescricao(el, id, true);
  }
  function mostrarOk(el) {
    limparEstado(el);
    var campo = el.closest('.campo');
    var rotulo = campo.querySelector(':scope > label');
    campo.classList.add('ok');
    if (rotulo && el.type !== 'checkbox') rotulo.appendChild(iconeSvg('check', 'campo-ok'));
  }
  // Confere um campo. `final` (saída do campo ou envio): marca também o que está certo. Devolve true se válido.
  function validarCampo(el, final) {
    if (!visivel(el)) return true;
    var texto = mensagemDoCampo(el);
    if (texto) { mostrarErro(el, texto); return false; }
    // Sem erro do cliente: só marca "ok" o que tem valor e alguma regra (obrigatório, tipo ou padrão); erro que veio do servidor sai quando o valor é editado
    if (final) {
      var temValor = el.type === 'checkbox' ? el.checked : !!String(el.value).trim();
      var regra = el.required || el.type === 'email' || el.pattern || el.type === 'date';
      if (temValor && regra && el.type !== 'file') mostrarOk(el); else limparEstado(el);
    }
    return true;
  }
  function prepararFormularios(raiz) {
    (raiz || document).querySelectorAll('form').forEach(function (form) {
      if (!formularioValidado(form)) return;
      form.noValidate = true;
      montarNavegacao(form);
      atualizarNavegacao(form);
    });
  }
  document.addEventListener('focusout', function (e) {
    if (e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-fechar]')) return;  // indo para Cancelar/Fechar
    if (campoDoFormulario(e.target) && e.target.type !== 'checkbox') validarCampo(e.target, true);
  });
  // Ao corrigir: o erro some assim que o valor passa na conferência do cliente (o servidor reconfere no envio)
  function aoEditar(e) {
    var el = e.target;
    if (!campoDoFormulario(el)) return;
    var campo = el.closest('.campo');
    if (campo.classList.contains('com-erro') && !mensagemDoCampo(el)) { limparEstado(el); atualizarNavegacao(el.form); }
    else if (campo.classList.contains('ok') && mensagemDoCampo(el)) validarCampo(el, true);
  }
  document.addEventListener('input', aoEditar);
  document.addEventListener('change', aoEditar);
  // Envio: confere tudo, leva o foco ao primeiro campo inválido e não deixa a requisição sair (captura: antes do HTMX e do bloqueio de clique duplo)
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!formularioValidado(form) || (e.submitter && e.submitter.hasAttribute('formnovalidate'))) return;
    var primeiro = null;
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!campoDoFormulario(el)) return;
      if (!validarCampo(el, true) && !primeiro) primeiro = el;
    });
    atualizarNavegacao(form);
    if (!primeiro) return;
    e.preventDefault();
    e.stopPropagation();
    var corpo = form.querySelector('.dialogo-corpo');
    if (corpo) {
      // Só o corpo do formulário rola (scrollIntoView também empurraria o diálogo inteiro e esconderia o cabeçalho)
      primeiro.focus({ preventScroll: true });
      var c = corpo.getBoundingClientRect(), r = primeiro.getBoundingClientRect();
      if (r.top < c.top + 8 || r.bottom > c.bottom - 8) rolarCorpo(corpo, corpo.scrollTop + r.top - c.top - 72, false);
    } else {
      primeiro.focus();
    }
  }, true);
  function rolarCorpo(corpo, topo, suave) {
    corpo.scrollTo({ top: Math.max(0, topo), behavior: suave && !(reduzMovimento && reduzMovimento.matches) ? 'smooth' : 'auto' });
  }

  // Celular, formulário em tela cheia: faixa fixa no alto com "Seção X de Y", barra de progresso e um botão por seção.
  // As seções com campo inválido ganham um ponto de alerta. Em telas largas a faixa fica oculta (CSS).
  var reduzMovimento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  function montarNavegacao(form) {
    var dialogo = form.closest('dialog.cheio');
    var secoes = form.querySelectorAll('[data-secao]');
    if (!dialogo || secoes.length < 2 || form.querySelector('.form-nav')) return;
    var cab = form.querySelector('.dialogo-cab');
    if (!cab) return;
    var nav = document.createElement('nav');
    nav.className = 'form-nav';
    nav.setAttribute('aria-label', 'Seções do formulário');
    var estado = document.createElement('p');
    estado.className = 'form-nav-estado';
    estado.setAttribute('aria-live', 'polite');
    var barra = document.createElement('progress');
    barra.setAttribute('aria-hidden', 'true');
    barra.max = secoes.length;
    barra.value = 1;
    var lista = document.createElement('div');
    lista.className = 'form-nav-lista';
    Array.prototype.forEach.call(secoes, function (secao, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'form-nav-item';
      b.setAttribute('data-ir', String(i));
      b.textContent = secao.querySelector('h3').textContent;
      lista.appendChild(b);
    });
    nav.appendChild(estado);
    nav.appendChild(barra);
    nav.appendChild(lista);
    cab.insertAdjacentElement('afterend', nav);
    var corpo = form.querySelector('.dialogo-corpo');
    var pendente = false;
    if (corpo) corpo.addEventListener('scroll', function () {
      if (pendente) return;
      pendente = true;
      window.requestAnimationFrame(function () { pendente = false; atualizarNavegacao(form); });
    }, { passive: true });
    atualizarNavegacao(form);
  }
  function atualizarNavegacao(form) {
    var nav = form && form.querySelector ? form.querySelector('.form-nav') : null;
    if (!nav) return;
    var secoes = form.querySelectorAll('[data-secao]');
    var corpo = form.querySelector('.dialogo-corpo');
    var atual = 0;
    if (corpo) {
      var limite = corpo.getBoundingClientRect().top + 24;
      var fim = corpo.scrollTop + corpo.clientHeight >= corpo.scrollHeight - 4;
      secoes.forEach(function (s, i) { if (s.getBoundingClientRect().top <= limite) atual = i; });
      if (fim) atual = secoes.length - 1;
    }
    nav.querySelector('.form-nav-estado').textContent = 'Seção ' + (atual + 1) + ' de ' + secoes.length + ': ' + secoes[atual].querySelector('h3').textContent;
    nav.querySelector('progress').value = atual + 1;
    nav.querySelectorAll('.form-nav-item').forEach(function (b, i) {
      b.classList.toggle('tem-erro', !!secoes[i].querySelector('.com-erro'));
      if (i === atual) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
      if (i === atual && b.scrollIntoView && b.parentNode.scrollWidth > b.parentNode.clientWidth) {
        var lista = b.parentNode;
        lista.scrollLeft = b.offsetLeft - (lista.clientWidth - b.offsetWidth) / 2;
      }
    });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.form-nav-item') : null;
    if (!b) return;
    var form = b.closest('form');
    var secao = form.querySelectorAll('[data-secao]')[Number(b.getAttribute('data-ir'))];
    var corpo = form.querySelector('.dialogo-corpo');
    if (secao && corpo) rolarCorpo(corpo, corpo.scrollTop + secao.getBoundingClientRect().top - corpo.getBoundingClientRect().top - 8, true);
  });
  document.addEventListener('DOMContentLoaded', function () { prepararFormularios(); });
  document.body.addEventListener('htmx:afterSettle', function () { prepararFormularios(); });
  prepararFormularios();

  // ---- Falha de rede do HTMX (sem conexão ou tempo esgotado): avisa em #avisos; some quando uma requisição der certo ----
  function avisarFalhaDeRede(texto) {
    // Com um diálogo aberto, a página fica atrás do fundo escuro: o aviso vai para dentro do diálogo
    var dialogo = document.querySelector('dialog[open]');
    var area = document.getElementById('avisos');
    if (dialogo) {
      area = dialogo.querySelector('[data-avisos-dialogo]');
      if (!area) {
        area = document.createElement('div');
        area.setAttribute('data-avisos-dialogo', '');
        area.setAttribute('aria-live', 'polite');
        dialogo.insertBefore(area, dialogo.firstChild);
      }
    }
    if (!area) return;
    document.querySelectorAll('[data-falha-rede]').forEach(function (a) { a.remove(); });
    var aviso = document.createElement('div');
    aviso.className = 'aviso erro';
    aviso.setAttribute('role', 'alert');
    aviso.setAttribute('data-falha-rede', '');
    aviso.innerHTML = '<svg class="i" aria-hidden="true" focusable="false"><use href="#i-alerta"/></svg><div></div>';
    aviso.lastChild.textContent = texto;
    area.appendChild(aviso);
    if (!dialogo) prepararToasts();  // na página, vira toast; dentro de diálogo continua inline
    else area.scrollIntoView({ block: 'nearest' });
  }
  document.body.addEventListener('htmx:sendError', function () {
    avisarFalhaDeRede('Sem conexão com o servidor. Verifique a internet e tente de novo.');
  });
  document.body.addEventListener('htmx:timeout', function () {
    avisarFalhaDeRede('O servidor demorou demais para responder. Tente de novo.');
  });
  document.body.addEventListener('htmx:afterRequest', function (e) {
    if (!e.detail.successful) return;
    document.querySelectorAll('[data-falha-rede]').forEach(function (a) { a.remove(); });
  });

  // ---- Carregamento: a classe "carregando" no <html> acende a barra do topo enquanto houver requisição do HTMX ----
  var pendentes = new Set();
  function atualizarBarra() { document.documentElement.classList.toggle('carregando', pendentes.size > 0); }
  document.body.addEventListener('htmx:beforeRequest', function (e) {
    pendentes.add(e.detail.xhr);
    // O trecho que vai ser trocado fica "ocupado" (leitores de tela anunciam; o CSS esmaece a lista)
    if (e.detail.target && e.detail.target.setAttribute) e.detail.target.setAttribute('aria-busy', 'true');
    atualizarBarra();
  });
  ['htmx:afterRequest', 'htmx:sendError', 'htmx:timeout', 'htmx:sendAbort'].forEach(function (nome) {
    document.body.addEventListener(nome, function (e) {
      pendentes.delete(e.detail.xhr);
      if (e.detail.target && e.detail.target.removeAttribute) e.detail.target.removeAttribute('aria-busy');
      atualizarBarra();
    });
  });
  // Voltar pelo histórico (bfcache) não deve reabrir a página com a barra acesa
  window.addEventListener('pageshow', function () { pendentes.clear(); atualizarBarra(); });

  // ---- Lembrar filtros da lista ----
  // Em listas com <form id="filtros" data-lembrar-filtros>, guarda na aba (sessionStorage) a busca, o filtro, a ordem e o "por
  // página" da URL. Ao voltar da ficha ("Voltar", menu lateral) para o endereço puro da lista, reabre com o que estava.
  // "Limpar filtros" (que deixa a URL sem parâmetros) apaga o que foi guardado; sair da conta também.
  var PREFIXO_FILTROS = 'filtros-lista:';
  function lembrarFiltros() {
    var lista = document.getElementById('filtros');
    if (!lista || !lista.hasAttribute('data-lembrar-filtros')) return;
    var chave = PREFIXO_FILTROS + location.pathname;
    try {
      if (location.search) sessionStorage.setItem(chave, location.search);
      else sessionStorage.removeItem(chave);
    } catch (erro) { /* armazenamento indisponível: a lista só não lembra */ }
  }
  (function restaurarFiltros() {
    var lista = document.getElementById('filtros');
    if (!lista || !lista.hasAttribute('data-lembrar-filtros') || location.search) return lembrarFiltros();
    try {
      var salvo = sessionStorage.getItem(PREFIXO_FILTROS + location.pathname);
      if (salvo) location.replace(location.pathname + salvo);
    } catch (erro) { /* idem */ }
  })();
  // "Limpar filtros" (no indicador ou no estado vazio) também esvazia o campo de busca, que fica fora do #resultado trocado pelo HTMX
  document.addEventListener('click', function (e) {
    var botao = e.target.closest && e.target.closest('.aviso-filtro a, .vazio a');
    var busca = document.getElementById('busca');
    if (botao && busca && botao.textContent.trim() === 'Limpar filtros') busca.value = '';
  });
  document.body.addEventListener('htmx:pushedIntoHistory', lembrarFiltros);
  document.body.addEventListener('htmx:historyRestore', lembrarFiltros);
  document.addEventListener('submit', function (e) {
    if (!e.target.action || new URL(e.target.action).pathname !== '/logout') return;
    try {
      Object.keys(sessionStorage).filter(function (k) { return k.indexOf(PREFIXO_FILTROS) === 0; })
        .forEach(function (k) { sessionStorage.removeItem(k); });
    } catch (erro) { /* idem */ }
  });

  // ---- Atalhos de teclado (só sem modificadores, fora de campos de texto e sem diálogo aberto) ----
  // "/" leva o foco à busca da página; "n" aciona o botão marcado com data-atalho-novo (o "Novo ..." da lista).
  document.addEventListener('keydown', function (e) {
    if (e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key !== '/' && e.key !== 'n') return;
    var alvo = e.target;
    var tag = alvo && alvo.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (alvo && alvo.isContentEditable)) return;
    if (document.querySelector('dialog[open]')) return;
    if (e.key === '/') {
      var busca = document.querySelector('main input[type="search"]');
      if (!busca) return;
      e.preventDefault();
      busca.focus();
      busca.select();
    } else {
      var novo = document.querySelector('main [data-atalho-novo]');
      if (!novo) return;
      e.preventDefault();
      novo.click();
    }
  });

  // ---- Aviso de sessão prestes a expirar ----
  // O servidor expira a sessão após data-sessao-limite segundos sem requisições. Cinco minutos antes, abre o diálogo de
  // confirmação com "Continuar conectado" (POST /sessao/renovar); se o prazo passar, avisa que expirou e leva ao login.
  // Qualquer requisição do HTMX bem-sucedida conta como atividade e reinicia a contagem.
  var limiteSessao = parseInt(document.body.getAttribute('data-sessao-limite') || '0', 10);
  if (limiteSessao > 0) {
    var ultimaAtividade = Date.now();
    var avisoEm = Math.max(limiteSessao - 300, Math.floor(limiteSessao / 2)) * 1000;
    var relogioSessao = null;
    var estadoSessao = 'ativa';  // 'ativa' | 'avisada' | 'expirada'
    var origemAviso = document.createElement('span');
    origemAviso.setAttribute('data-confirmar-neutro', '');

    function csrfDaPagina() {
      try { return JSON.parse(document.body.getAttribute('hx-headers') || '{}')['X-CSRF-Token'] || ''; } catch (erro) { return ''; }
    }
    function avisarSessaoExpirada() {
      estadoSessao = 'expirada';
      origemAviso.setAttribute('data-confirmar-titulo', 'Sessão expirada');
      origemAviso.setAttribute('data-confirmar-rotulo', 'Entrar de novo');
      pedirConfirmacao(origemAviso, 'Sua sessão expirou por inatividade. Entre de novo para continuar.', function () { location.assign('/login?expirou=1'); });
    }
    function avisarSessaoPrestesAExpirar() {
      estadoSessao = 'avisada';
      origemAviso.setAttribute('data-confirmar-titulo', 'Sessão prestes a expirar');
      origemAviso.setAttribute('data-confirmar-rotulo', 'Continuar conectado');
      pedirConfirmacao(origemAviso, 'Por inatividade, sua sessão termina em poucos minutos. Quer continuar conectado?', function () {
        fetch('/sessao/renovar', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrfDaPagina() } })
          .then(function (r) { if (r.ok && !r.redirected) reiniciarSessao(); else avisarSessaoExpirada(); },
                function () { avisarSessaoExpirada(); });
      });
    }
    function agendarSessao() {
      window.clearTimeout(relogioSessao);
      var parado = Date.now() - ultimaAtividade;
      if (parado >= limiteSessao * 1000) { if (estadoSessao !== 'expirada') avisarSessaoExpirada(); return; }
      if (parado >= avisoEm) {
        if (estadoSessao === 'ativa') avisarSessaoPrestesAExpirar();
        relogioSessao = window.setTimeout(agendarSessao, limiteSessao * 1000 - parado + 500);
      } else {
        relogioSessao = window.setTimeout(agendarSessao, avisoEm - parado);
      }
    }
    function reiniciarSessao() {
      ultimaAtividade = Date.now();
      if (estadoSessao === 'avisada') {
        var dialogo = document.getElementById('dlg-confirmar');
        if (dialogo && dialogo.open) dialogo.close();
      }
      if (estadoSessao !== 'expirada') estadoSessao = 'ativa';
      agendarSessao();
    }
    document.body.addEventListener('htmx:afterRequest', function (e) { if (e.detail.successful) reiniciarSessao(); });
    // Aba em segundo plano: os temporizadores atrasam, então reconfere o prazo ao voltar
    document.addEventListener('visibilitychange', function () { if (!document.hidden) agendarSessao(); });
    agendarSessao();
  }

  // ---- Campo com data-envia-ao-mudar: envia o formulário assim que o valor muda (ex.: seletor de mês) ----
  document.addEventListener('change', function (e) {
    var campo = e.target;
    if (!campo.hasAttribute || !campo.hasAttribute('data-envia-ao-mudar') || !campo.form || !campo.value) return;
    if (campo.form.requestSubmit) campo.form.requestSubmit(); else campo.form.submit();
  });
  // ---- Depois de uma troca do HTMX, devolve o foco ao conteúdo principal (leitores de tela) ----
  document.body.addEventListener('htmx:afterSettle', function (e) {
    if (e.detail.target && e.detail.target.id === 'conteudo') e.detail.target.focus({ preventScroll: true });
  });
  // ---- Números que contam: [data-contar] (valor dos KPIs) sobe de 0 até o valor que o servidor já escreveu no HTML ----
  // Só visual: o texto final é sempre o original (restaurado no fim), então se o JS falhar ou o movimento estiver reduzido o
  // número certo já está na tela. Só conta quando há exatamente um número no texto ("R$ 1.234,56", "72% ocupada", "5 veículos").
  var NUMERO_PT = /\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?/g;
  var DURACAO_CONTAGEM = 700;
  var movimentoReduzido = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  function dividirNumero(texto) {
    var achados = texto.match(NUMERO_PT);
    if (!achados || achados.length !== 1 || texto.length > 40) return null;
    var numero = achados[0];
    if (/^0\d/.test(numero)) return null;  // "007", códigos
    var posicao = texto.indexOf(numero);
    var virgula = numero.indexOf(',');
    var valor = parseFloat(numero.replace(/\./g, '').replace(',', '.'));  // só para exibição; o texto final volta a ser o do servidor
    if (!isFinite(valor) || valor === 0) return null;
    return { antes: texto.slice(0, posicao), depois: texto.slice(posicao + numero.length), valor: valor, casas: virgula < 0 ? 0 : numero.length - virgula - 1 };
  }
  function contarAte(elemento) {
    var original = elemento.textContent;
    var partes = dividirNumero(original);
    if (!partes || !window.requestAnimationFrame) return;
    var inicio = null;
    function quadro(agora) {
      if (inicio === null) inicio = agora;
      var t = Math.min((agora - inicio) / DURACAO_CONTAGEM, 1);
      if (t >= 1 || !elemento.isConnected) { elemento.textContent = original; return; }
      var atual = partes.valor * (1 - Math.pow(1 - t, 3));
      elemento.textContent = partes.antes + atual.toLocaleString('pt-BR', { minimumFractionDigits: partes.casas, maximumFractionDigits: partes.casas }) + partes.depois;
      window.requestAnimationFrame(quadro);
    }
    window.requestAnimationFrame(quadro);
  }
  function iniciarContagens() {
    document.querySelectorAll('[data-contar]:not([data-contado])').forEach(function (el) {
      el.setAttribute('data-contado', '');
      if (movimentoReduzido.matches || document.hidden || el.children.length) return;
      contarAte(el);
    });
  }
  document.addEventListener('DOMContentLoaded', iniciarContagens);
  document.addEventListener('htmx:afterSettle', iniciarContagens);

  // ---- Toasts: os .aviso dentro de #avisos (pilha fixa no canto) ganham botão de fechar e somem sozinhos ----
  // Sem JS o aviso continua na tela. Passar o mouse ou focar dentro pausa a contagem (WCAG 2.2.1); erros ficam mais tempo.
  var TEMPO_TOAST = { sucesso: 5000, info: 6000, atencao: 9000, erro: 12000 };
  var MAXIMO_TOASTS = 4;
  function tempoDoToast(aviso) {
    for (var tipo in TEMPO_TOAST) if (aviso.classList.contains(tipo)) return TEMPO_TOAST[tipo];
    return TEMPO_TOAST.info;
  }
  function fecharToast(aviso) {
    if (!aviso.isConnected || aviso._saindo) return;
    aviso._saindo = true;
    window.clearTimeout(aviso._relogio);
    if (movimentoReduzido.matches) { aviso.remove(); return; }
    aviso.classList.add('saindo');
    var remover = function () { if (aviso.isConnected) aviso.remove(); };
    aviso.addEventListener('animationend', remover);
    window.setTimeout(remover, 400);
  }
  function agendarToast(aviso) {
    window.clearTimeout(aviso._relogio);
    aviso._relogio = window.setTimeout(function () { fecharToast(aviso); }, tempoDoToast(aviso));
  }
  function prepararToasts() {
    var area = document.getElementById('avisos');
    if (!area) return;
    area.querySelectorAll('.aviso:not([data-toast])').forEach(function (aviso) {
      aviso.setAttribute('data-toast', '');
      aviso.insertAdjacentHTML('beforeend', '<button type="button" class="aviso-fechar" aria-label="Fechar aviso"><svg class="i" aria-hidden="true" focusable="false"><use href="#i-fechar"/></svg></button>');
      aviso.addEventListener('mouseenter', function () { window.clearTimeout(aviso._relogio); });
      aviso.addEventListener('focusin', function () { window.clearTimeout(aviso._relogio); });
      aviso.addEventListener('mouseleave', function () { if (!aviso.contains(document.activeElement)) agendarToast(aviso); });
      aviso.addEventListener('focusout', function () { agendarToast(aviso); });
      agendarToast(aviso);
    });
    var ativos = area.querySelectorAll('.aviso:not(.saindo)');
    for (var i = 0; i < ativos.length - MAXIMO_TOASTS; i++) fecharToast(ativos[i]);  // mais de 4: some o mais antigo
  }
  document.addEventListener('click', function (e) {
    var botao = e.target.closest('.aviso-fechar');
    if (botao) fecharToast(botao.closest('.aviso'));
  });
  // Resposta fora de banda que troca o #avisos inteiro: os toasts que ainda estão na tela passam para o novo, em vez de sumirem
  document.body.addEventListener('htmx:oobBeforeSwap', function (e) {
    var alvo = e.detail.target;
    if (!alvo || alvo.id !== 'avisos' || !e.detail.fragment) return;
    var novo = e.detail.fragment.querySelector ? e.detail.fragment.querySelector('#avisos') : null;
    if (!novo) return;
    var antigos = Array.prototype.slice.call(alvo.querySelectorAll('.aviso[data-toast]:not(.saindo)'));
    antigos.reverse().forEach(function (a) { novo.insertBefore(a, novo.firstChild); });
  });
  document.addEventListener('DOMContentLoaded', prepararToasts);
  document.addEventListener('htmx:afterSettle', prepararToasts);
  document.addEventListener('htmx:oobAfterSwap', prepararToasts);

  // ---- Menu lateral: o traço do item ativo desliza, ao abrir a página, do item da página anterior até o item tocado ----
  (function () {
    var nav = document.querySelector('.lateral nav');
    if (!nav) return;
    var CHAVE = 'nav-marcador';
    var marcador = document.createElement('span');
    marcador.className = 'nav-marcador';
    marcador.setAttribute('aria-hidden', 'true');
    nav.appendChild(marcador);
    function guardar(valor) { try { sessionStorage.setItem(CHAVE, valor); } catch (e) { /* sem armazenamento: só não continua de onde parou */ } }
    function lido() { try { return sessionStorage.getItem(CHAVE); } catch (e) { return null; } }
    function itens() { return Array.prototype.slice.call(nav.querySelectorAll('.nav-item')); }
    function porCaminho(caminho) { return itens().filter(function (a) { return a.getAttribute('href') === caminho; })[0] || null; }
    function posicionar(item) {
      var r = item.getBoundingClientRect(), n = nav.getBoundingClientRect();
      marcador.style.height = Math.max(r.height - 16, 0) + 'px';
      marcador.style.transform = 'translateY(' + (r.top - n.top + 8) + 'px)';
      marcador.classList.add('visivel');
    }
    var ativo = nav.querySelector('.nav-item[aria-current="page"]');
    if (!ativo || !nav.offsetParent) return;
    document.documentElement.classList.add('com-marcador');
    var anterior = porCaminho(lido());
    posicionar(anterior || ativo);
    if (anterior && anterior !== ativo) {
      marcador.getBoundingClientRect();
      window.setTimeout(function () { marcador.classList.add('desliza'); posicionar(ativo); }, 60);
    } else {
      window.setTimeout(function () { marcador.classList.add('desliza'); }, 60);
    }
    guardar(ativo.getAttribute('href'));
  })();
})();
