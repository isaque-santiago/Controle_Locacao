"""Funções de apoio: esperar o Streamlit, entrar no sistema e medir a página."""

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from e2e.config import ALVO_MINIMO, Pagina, base_url, credenciais

SELETOR_INTERATIVOS = (
    'a[href], button, input:not([type="hidden"]), select, textarea, summary, '
    '[role="button"], [role="tab"], [role="radio"], [role="checkbox"], '
    '[role="switch"], [role="combobox"], [role="link"], [tabindex]:not([tabindex="-1"])'
)


# --------------------------------------------------------------------------
# Streamlit
# --------------------------------------------------------------------------
def aguardar_app(page: Page, timeout: int = 30_000) -> None:
    """Espera o Streamlit terminar a execução (sem o indicador 'Running')."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout)
    for _ in range(2):
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')",
            timeout=timeout,
        )
        page.wait_for_timeout(350)
    try:
        page.evaluate("document.fonts.ready.then(() => true)")
    except Exception:
        pass


def tem_formulario_login(page: Page) -> bool:
    return page.get_by_role("button", name="Entrar no painel").count() > 0


def abrir_login(page: Page) -> None:
    page.goto(base_url() + "/")
    aguardar_app(page)


def entrar(page: Page, email: str, senha: str) -> None:
    """Login pelo formulário. As credenciais vêm do ambiente e não são registradas."""
    abrir_login(page)
    if not tem_formulario_login(page):
        return
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha", exact=True).fill(senha)
    page.get_by_role("button", name="Entrar no painel").click()
    # Não espera o botão "desanexar": durante o rerun do Streamlit o React pode manter
    # brevemente o nó antigo e o novo no DOM ao mesmo tempo (mesmo texto/testid), o que
    # deixa get_by_role ambíguo por uma fração de segundo. O sinal confiável de que
    # logou é a barra lateral autenticada (botão "Sair").
    page.get_by_role("button", name="Sair").wait_for(state="visible", timeout=30_000)
    aguardar_app(page)
    # Dá tempo ao componente que grava o cookie de sessão antes das próximas navegações.
    page.wait_for_timeout(1_200)


def ir_para(page: Page, pagina: Pagina) -> bool:
    """Abre a página pela URL; a sessão é restaurada pelo cookie.

    Se o app devolver a tela de acesso (a restauração por cookie falhou), entra de novo e
    repete a navegação. Devolve True quando foi preciso reautenticar, para o teste registrar
    o achado sem perder o restante da varredura."""
    destino = f"{base_url()}/{pagina.caminho}"
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
    """Exceções do Streamlit renderizadas na página."""
    return page.locator('[data-testid="stException"]').all_inner_texts()


# --------------------------------------------------------------------------
# Medições (executadas no navegador)
# --------------------------------------------------------------------------
_JS_COMUM = r"""
const descrever = (el) => {
  const partes = [];
  let atual = el;
  for (let i = 0; atual && atual.nodeType === 1 && i < 4; i++) {
    let s = atual.tagName.toLowerCase();
    const tid = atual.getAttribute('data-testid');
    if (tid) s += '[' + tid + ']';
    else if (atual.classList.length) s += '.' + Array.from(atual.classList).slice(0, 2).join('.');
    partes.unshift(s);
    if (tid) break;
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
  }
  return true;
};
// Elemento dentro de contêiner que rola na horizontal (rolagem legítima e localizada).
const emRolagemHorizontal = (el) => {
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const ox = getComputedStyle(p).overflowX;
    if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
  }
  return false;
};
// Barra lateral recolhida fica fora da tela por transformação: não é problema de layout.
const emBarraRecolhida = (el) => {
  const sb = el.closest('[data-testid="stSidebar"]');
  return !!sb && sb.getAttribute('aria-expanded') === 'false';
};
"""

_JS_OVERFLOW = (
    "() => {"
    + _JS_COMUM
    + r"""
  const vw = document.documentElement.clientWidth;
  const doc = document.documentElement;
  const alvos = ['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]', '[data-testid="stMainBlockContainer"]'];
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
      if (!visivel(el) || emRolagemHorizontal(el) || emBarraRecolhida(el)) continue;
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
    if (!visivel(el) || emBarraRecolhida(el)) continue;
    if (el.disabled && el.tagName !== 'BUTTON') continue;
    const r = el.getBoundingClientRect();
    const info = { el: descrever(el), rotulo: rotulo(el), tag: el.tagName.toLowerCase(), papel: el.getAttribute('role') || '' };
    if ((r.right > vw + 1 || r.left < -1) && !emRolagemHorizontal(el)) {
      fora.push({ ...info, esquerda: Math.round(r.left), direita: Math.round(r.right) });
      continue;
    }
    // Links dentro de texto corrido são isentos do alvo mínimo.
    if (el.tagName === 'A' && el.parentElement && ['P', 'LI', 'TD', 'SPAN'].includes(el.parentElement.tagName)) continue;
    // Botão auxiliar de 1 px do react-aria ("Descartar"): fora da ordem de tabulação, não é alvo de toque.
    if (el.tagName === 'BUTTON' && el.getAttribute('tabindex') === '-1' && el.style.width === '1px') continue;
    // Entradas escondidas por trás de rótulo estilizado (upload) medem o botão visível, não o <input>.
    if (el.tagName === 'INPUT' && el.type === 'file' && getComputedStyle(el).opacity === '0') continue;
    // Campos de texto/seleção: o alvo é a caixa estilizada do Streamlit, não o <input> interno.
    // Radio/checkbox medem o rótulo que os contém; data e seleção medem o grupo (dia/mês/ano ou caixa de seleção).
    const composto = '[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stTextAreaRootElement"], [data-baseweb="select"], [data-testid="stDateInputField"], .react-aria-ComboBox';
    const caixa = (el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type))
      ? (el.closest('label') || el)
      : (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.getAttribute('role') === 'spinbutton')
        ? (el.closest(composto) || el)
        : el;
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
  const d = document.querySelector('[role="dialog"]');
  if (!d) return null;
  const r = d.getBoundingClientRect();
  const botoes = [];
  for (const b of d.querySelectorAll('button')) {
    if (!visivel(b)) continue;
    const rb = b.getBoundingClientRect();
    botoes.push({ rotulo: rotulo(b), esquerda: Math.round(rb.left), direita: Math.round(rb.right) });
  }
  // A rolagem pode estar no diálogo, em um descendente ou no contêiner (overlay) que o envolve.
  let rola = false;
  const candidatos = [d, ...d.querySelectorAll('*')];
  for (let p = d.parentElement; p && p !== document.documentElement; p = p.parentElement) candidatos.push(p);
  for (const el of candidatos) {
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


def medir_overflow(page: Page) -> dict:
    return page.evaluate(_JS_OVERFLOW)


def medir_interativos(page: Page) -> dict:
    return page.evaluate(_JS_INTERATIVOS, [SELETOR_INTERATIVOS, ALVO_MINIMO])


def medir_dialogo(page: Page) -> dict | None:
    return page.evaluate(_JS_DIALOGO)


def esperar_dialogo(page: Page, timeout: int = 8_000) -> bool:
    try:
        page.wait_for_selector('[role="dialog"]', timeout=timeout)
        aguardar_app(page)
        return True
    except PlaywrightTimeout:
        return False


def fechar_dialogo(page: Page) -> None:
    """Fecha sem salvar (Esc). Nenhum fluxo da Etapa 0 grava dados."""
    if page.locator('[role="dialog"]').count():
        page.keyboard.press("Escape")
        try:
            page.wait_for_selector('[role="dialog"]', state="detached", timeout=4_000)
        except PlaywrightTimeout:
            pass
        aguardar_app(page)
