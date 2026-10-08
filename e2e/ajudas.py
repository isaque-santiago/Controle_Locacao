"""Funções de apoio: esperar o app (FastAPI + HTMX), entrar no sistema e medir a página."""

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from e2e.config import ALVO_MINIMO, Pagina, base_url, credenciais

SELETOR_INTERATIVOS = (
    'a[href], button, input:not([type="hidden"]), select, textarea, summary, '
    '[role="button"], [role="tab"], [role="radio"], [role="checkbox"], '
    '[role="switch"], [role="combobox"], [role="link"], [tabindex]:not([tabindex="-1"])'
)

# Classes que o HTMX põe enquanto uma requisição ou troca de conteúdo está em andamento.
_JS_HTMX_PARADO = "() => !document.querySelector('.htmx-request, .htmx-swapping, .htmx-settling, .htmx-added')"


# --------------------------------------------------------------------------
# Espera e navegação
# --------------------------------------------------------------------------
def aguardar_app(page: Page, timeout: int = 30_000) -> None:
    """Espera a página carregar e o HTMX terminar qualquer troca de conteúdo."""
    page.wait_for_load_state("load", timeout=timeout)
    for _ in range(2):
        page.wait_for_function(_JS_HTMX_PARADO, timeout=timeout)
        page.wait_for_timeout(150)
    try:
        page.evaluate("document.fonts.ready.then(() => true)")
    except Exception:
        pass


def tem_formulario_login(page: Page) -> bool:
    return page.locator('form[action="/login"]').count() > 0


def abrir_login(page: Page) -> None:
    page.goto(base_url() + "/login")
    aguardar_app(page)


def entrar(page: Page, email: str, senha: str) -> None:
    """Login pelo formulário. As credenciais vêm do ambiente e não são registradas."""
    abrir_login(page)
    if not tem_formulario_login(page):
        return  # já havia sessão ativa: o app redirecionou
    page.locator("form[action='/login'] input[name=identificador]").fill(email)
    page.locator("form[action='/login'] input[name=senha]").fill(senha)
    page.get_by_role("button", name="Entrar", exact=True).click()
    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=30_000)
    except PlaywrightTimeout:
        # Mostra só a mensagem do app (nunca o que foi digitado).
        aviso = page.locator("form[action='/login'] [role='alert'], form[action='/login'] .aviso").first
        motivo = aviso.inner_text().strip()[:120] if aviso.count() else "sem mensagem"
        raise RuntimeError(f"O login não foi concluído ({motivo}).") from None
    aguardar_app(page)


def ir_para(page: Page, pagina: Pagina) -> bool:
    """Abre a página pela URL; a sessão vale pelo cookie.

    Se o app devolver a tela de acesso (sessão expirada ou perdida), entra de novo e repete a navegação.
    Devolve True quando foi preciso reautenticar, para o teste registrar o achado sem perder a varredura."""
    destino = base_url() + pagina.caminho
    page.goto(destino)
    aguardar_app(page)
    if not tem_formulario_login(page):
        return False
    cred = credenciais()
    if cred is None:
        return False
    entrar(page, *cred)
    page.goto(destino)
    aguardar_app(page)
    return True


def textos_de_excecao(page: Page) -> list[str]:
    """Páginas de erro do app (404, 403, 500…), que usam o cartão `acesso-erro`."""
    return page.locator(".acesso-erro").all_inner_texts()


# --------------------------------------------------------------------------
# Medições (executadas no navegador)
# --------------------------------------------------------------------------
_JS_COMUM = r"""
const descrever = (el) => {
  const partes = [];
  let atual = el;
  for (let i = 0; atual && atual.nodeType === 1 && i < 4; i++) {
    let s = atual.tagName.toLowerCase();
    if (atual.id) s += '#' + atual.id;
    else if (atual.classList.length) s += '.' + Array.from(atual.classList).slice(0, 2).join('.');
    partes.unshift(s);
    if (atual.id) break;
    atual = atual.parentElement;
  }
  return partes.join(' > ');
};
const rotulo = (el) => {
  const t = el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.value || el.getAttribute('placeholder') || '';
  return t.replace(/\s+/g, ' ').trim().slice(0, 40);
};
const visivel = (el) => {
  const r = el.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return false;
  const cs = getComputedStyle(el);
  if (cs.visibility === 'hidden' || cs.display === 'none') return false;
  for (let p = el; p; p = p.parentElement) {
    if (p.getAttribute && p.getAttribute('aria-hidden') === 'true') return false;
    if (getComputedStyle(p).display === 'none') return false;
    // Diálogo fechado não aparece (o navegador o esconde sem display:none em alguns casos).
    if (p.tagName === 'DIALOG' && !p.open) return false;
  }
  return true;
};
// Elemento dentro de contêiner que rola na horizontal (rolagem legítima e localizada: chips, abas, tabelas).
const emRolagemHorizontal = (el) => {
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const ox = getComputedStyle(p).overflowX;
    if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
  }
  return false;
};
"""

_JS_OVERFLOW = (
    "() => {"
    + _JS_COMUM
    + r"""
  const vw = document.documentElement.clientWidth;
  const doc = document.documentElement;
  const alvos = ['.app', '.coluna', 'main'];
  const contenedores = [];
  for (const sel of alvos) {
    const el = document.querySelector(sel);
    if (el && el.scrollWidth > el.clientWidth + 1) {
      contenedores.push({ seletor: sel, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth });
    }
  }
  const culpados = [];
  if (doc.scrollWidth > doc.clientWidth + 1 || contenedores.length) {
    for (const el of document.querySelectorAll('body *')) {
      if (!visivel(el) || emRolagemHorizontal(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 || r.left < -1) {
        culpados.push({ el: descrever(el), direita: Math.round(r.right), esquerda: Math.round(r.left), texto: rotulo(el) });
      }
    }
  }
  return {
    documento: { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth },
    contenedores,
    culpados: culpados.slice(0, 8),
    total_culpados: culpados.length,
  };
}"""
)

_JS_INTERATIVOS = (
    "(args) => {"
    + _JS_COMUM
    + r"""
  const [seletor, alvoMin] = args;
  const vw = document.documentElement.clientWidth;
  const fora = [];
  const pequenos = [];
  const vistos = new Set();
  for (const el of document.querySelectorAll(seletor)) {
    if (!visivel(el)) continue;
    if (el.disabled && el.tagName !== 'BUTTON') continue;
    const r = el.getBoundingClientRect();
    const info = { el: descrever(el), rotulo: rotulo(el), tag: el.tagName.toLowerCase(), papel: el.getAttribute('role') || '' };
    if ((r.right > vw + 1 || r.left < -1) && !emRolagemHorizontal(el)) {
      fora.push({ ...info, esquerda: Math.round(r.left), direita: Math.round(r.right) });
      continue;
    }
    // Link do pular-para-o-conteúdo só aparece com o foco; os de texto corrido são isentos do alvo mínimo.
    if (el.classList.contains('pular')) continue;
    if (el.tagName === 'A' && el.parentElement && ['P', 'LI', 'TD', 'SPAN', 'DD'].includes(el.parentElement.tagName)
        && !el.closest('.nav-lista, .folha-lista, .barra-inferior')) continue;
    // Entradas escondidas por trás de rótulo estilizado (upload) medem o botão visível, não o <input>.
    if (el.tagName === 'INPUT' && el.type === 'file' && getComputedStyle(el).opacity === '0') continue;
    // Radio/checkbox medem o rótulo que os contém.
    const caixa = (el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type)) ? (el.closest('label') || el) : el;
    const rc = caixa.getBoundingClientRect();
    if (rc.width < alvoMin - 0.5 || rc.height < alvoMin - 0.5) {
      const chave = info.el + '|' + info.rotulo;
      if (vistos.has(chave)) continue;
      vistos.add(chave);
      pequenos.push({ ...info, largura: Math.round(rc.width), altura: Math.round(rc.height) });
    }
  }
  return { fora, pequenos };
}"""
)

_JS_DIALOGO = (
    "() => {"
    + _JS_COMUM
    + r"""
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const d = document.querySelector('dialog[open]');
  if (!d) return null;
  const r = d.getBoundingClientRect();
  const botoes = [];
  for (const b of d.querySelectorAll('button')) {
    if (!visivel(b)) continue;
    const rb = b.getBoundingClientRect();
    botoes.push({ rotulo: rotulo(b), esquerda: Math.round(rb.left), direita: Math.round(rb.right) });
  }
  // A rolagem pode estar no diálogo ou em um descendente (o corpo do diálogo).
  let rola = false;
  for (const el of [d, ...d.querySelectorAll('*')]) {
    if (el.scrollHeight > el.clientHeight + 1 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowY)) { rola = true; break; }
  }
  return {
    caixa: { esquerda: Math.round(r.left), direita: Math.round(r.right), topo: Math.round(r.top), base: Math.round(r.bottom) },
    viewport: { largura: vw, altura: vh },
    rola,
    botoes,
  };
}"""
)


_JS_FOCO = (
    "([modo, SELETOR]) => {"
    + _JS_COMUM
    + r"""
  if (modo === 'iniciar') {
    window.__contadorFoco = 0;
    window.__yFoco = null;
    window.__regiaoFoco = null;
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    window.scrollTo(0, 0);
    document.body.setAttribute('tabindex', '-1');
    document.body.focus();
    document.body.removeAttribute('tabindex');
    return null;
  }
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) {
    return { fim_do_documento: true, chave: 'fim', el: 'body', rotulo: '', indicador: true, dentro: true, regressao: 0 };
  }
  if (!el.__idFoco) el.__idFoco = ++window.__contadorFoco;
  const rotuloAcessivel = () => {
    const direto = el.getAttribute('aria-label') || el.getAttribute('title') || '';
    if (direto.trim()) return direto.trim();
    const por = el.getAttribute('aria-labelledby');
    if (por) {
      const t = por.split(/\s+/).map(i => (document.getElementById(i) || {}).innerText || '').join(' ').trim();
      if (t) return t;
    }
    if (el.labels && el.labels.length) {
      const t = Array.from(el.labels).map(l => l.innerText).join(' ').trim();
      if (t) return t;
    }
    return (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim();
  };
  const r = el.getBoundingClientRect();
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const dentro = r.width > 0 && r.height > 0 && r.left >= -1 && r.right <= vw + 1 && r.top >= -1 && r.bottom <= vh + 1;
  // Indicador: contorno ou sombra no próprio elemento ou em até 3 ancestrais (o campo desenha o foco na caixa).
  let indicador = false;
  for (let p = el, i = 0; p && i < 4 && !indicador; p = p.parentElement, i++) {
    const cs = getComputedStyle(p);
    const contorno = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)|transparent/.test(cs.outlineColor);
    if (contorno || cs.boxShadow !== 'none') indicador = true;
  }
  const regiao = el.closest('dialog') ? 'dialogo' : (el.closest('.lateral, .barra-inferior, .topo-movel') ? 'barra' : 'principal');
  const y = r.top + (regiao === 'principal' ? window.scrollY : 0);
  let regressao = 0;
  if (window.__regiaoFoco === regiao && window.__yFoco !== null && y < window.__yFoco - 200) {
    regressao = Math.round(window.__yFoco - y);
  }
  window.__regiaoFoco = regiao;
  window.__yFoco = y;
  // Último elemento tabulável da página: o Firefox mantém nele o foco ao sair da página (o Chromium volta ao
  // <body>), então "o foco não avança" ali é o fim do documento, não uma armadilha.
  const tabulaveis = Array.from(document.querySelectorAll(SELETOR)).filter(e => visivel(e) && !e.disabled);
  const ultimo = tabulaveis.length === 0 || tabulaveis[tabulaveis.length - 1] === el || !tabulaveis.some(e => e !== el && (el.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING));
  return {
    ultimo,
    parcial: r.width > 0 && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw,
    fim_do_documento: false,
    chave: String(el.__idFoco),
    el: descrever(el),
    rotulo: rotuloAcessivel().slice(0, 50),
    indicador, dentro, regressao,
    // Campo de data nativo: Tab percorre dia, mês e ano no MESMO elemento.
    segmentos: el.tagName === 'INPUT' && ['date', 'time', 'datetime-local', 'month', 'week'].includes(el.type) ? 5 : 1,
  };
}"""
)

_JS_TEXTO_CORTADO = (
    "() => {"
    + _JS_COMUM
    + r"""
  const achados = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!visivel(el)) continue;
    const cs = getComputedStyle(el);
    const corta = (v) => v === 'hidden' || v === 'clip';
    if (!corta(cs.overflowX) && !corta(cs.overflowY)) continue;
    if (cs.textOverflow === 'ellipsis') continue;
    const texto = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!texto) continue;
    const largo = corta(cs.overflowX) && el.scrollWidth > el.clientWidth + 2;
    const alto = corta(cs.overflowY) && el.scrollHeight > el.clientHeight + 2;
    if (!largo && !alto) continue;
    // Texto só para leitor de tela (clip de 1 px, classe so-leitor): cortar é o objetivo.
    if ((largo ? el.clientWidth : el.clientHeight) <= 2) continue;
    achados.push({
      el: descrever(el), texto: texto.slice(0, 40),
      conteudo: largo ? el.scrollWidth : el.scrollHeight, caixa: largo ? el.clientWidth : el.clientHeight,
    });
  }
  return achados;
}"""
)


def medir_overflow(page: Page) -> dict:
    return page.evaluate(_JS_OVERFLOW)


def medir_foco_por_teclado(page: Page, modo: str) -> dict | None:
    """`iniciar` põe o início de tabulação no topo; `ler` descreve o elemento focado agora."""
    return page.evaluate(_JS_FOCO, [modo, SELETOR_INTERATIVOS])


def medir_texto_cortado(page: Page) -> list[dict]:
    return page.evaluate(_JS_TEXTO_CORTADO)


def medir_interativos(page: Page) -> dict:
    return page.evaluate(_JS_INTERATIVOS, [SELETOR_INTERATIVOS, ALVO_MINIMO])


def medir_dialogo(page: Page) -> dict | None:
    return page.evaluate(_JS_DIALOGO)


def esperar_dialogo(page: Page, timeout: int = 8_000) -> bool:
    try:
        page.wait_for_selector("dialog[open]", timeout=timeout)
        aguardar_app(page)
        return True
    except PlaywrightTimeout:
        return False


def fechar_dialogo(page: Page) -> None:
    """Fecha sem salvar (Esc)."""
    if page.locator("dialog[open]").count():
        page.keyboard.press("Escape")
        try:
            page.wait_for_selector("dialog[open]", state="detached", timeout=4_000)
        except PlaywrightTimeout:
            pass
        aguardar_app(page)
