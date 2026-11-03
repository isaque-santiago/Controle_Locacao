"""Apoio dos fluxos de homologação: contexto de medição, envio de formulários e arquivos de teste.

Os fluxos que GRAVAM marcam o que criam com "E2E" na descrição, para serem reconhecidos (e limpos) depois."""

import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from e2e.ajudas import aguardar_app, esperar_dialogo, fechar_dialogo, ir_para
from e2e.config import PAGINAS
from e2e.verificacoes import (
    capturar,
    verificar_acessibilidade,
    verificar_dialogo,
    verificar_layout,
    verificar_saude,
)

MARCA = "E2E"
PERFIS_QUE_GRAVAM = ("chromium-desktop", "chromium-movel")
_LARGURA_REFERENCIA = {"chromium-movel": 390}
_LARGURA_REFERENCIA_PADRAO = 1440


def hoje() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def pagina_por_titulo(titulo: str):
    return next(p for p in PAGINAS if p.titulo == titulo)


def grava_neste_cenario(cenario) -> bool:
    """Os fluxos que gravam rodam uma vez por perfil (largura de referência, tema claro), só no Chromium."""
    referencia = _LARGURA_REFERENCIA.get(cenario.perfil, _LARGURA_REFERENCIA_PADRAO)
    return cenario.perfil in PERFIS_QUE_GRAVAM and cenario.largura == referencia and cenario.tema == "claro"


def imagem_de_teste(formato: str = "PNG", lado: int = 96, cor=(200, 120, 20)) -> dict:
    """Arquivo para `set_input_files`, gerado na hora (nada de foto real)."""
    buffer = io.BytesIO()
    Image.new("RGB", (lado, lado), cor).save(buffer, formato)
    extensao = "jpg" if formato == "JPEG" else "png"
    tipo = "image/jpeg" if formato == "JPEG" else "image/png"
    return {"name": f"e2e-teste.{extensao}", "mimeType": tipo, "buffer": buffer.getvalue()}


class FormularioRecusado(Exception):
    """O servidor devolveu o formulário com erros; a mensagem traz só os avisos do app (nunca valores digitados)."""


def esperar_ate(page: Page, js: str, timeout_ms: int = 15_000, passo_ms: int = 250) -> bool:
    """Repete `js` (expressão booleana) até valer. Tolera a troca de documento no meio da espera."""
    restante = timeout_ms
    while restante > 0:
        try:
            if page.evaluate(js):
                return True
        except PlaywrightError:
            pass  # a página está navegando: tenta de novo
        page.wait_for_timeout(passo_ms)
        restante -= passo_ms
    return False


@dataclass
class Contexto:
    page: Page
    cenario: object
    reg: Callable
    capturas: bool

    # ---- medição ----
    def visitar(self, titulo: str) -> None:
        if ir_para(self.page, pagina_por_titulo(titulo)):
            self.reg(
                "P2",
                "sessao-restaurada-por-novo-login",
                titulo,
                "A sessão não sobreviveu à navegação por URL; foi preciso entrar de novo.",
            )
        self.medir(titulo, titulo)

    def medir(self, onde: str, foto: str | None = None) -> None:
        verificar_layout(self.page, self.cenario, self.reg, onde)
        verificar_saude(self.page, self.reg, onde)
        verificar_acessibilidade(self.page, self.reg, onde)
        if self.capturas and foto:
            capturar(self.page, self.cenario, foto)

    def info(self, onde: str, texto: str) -> None:
        self.reg("INFO", "controle-nao-encontrado", onde, texto)

    # ---- ações ----
    def alvo(self, papel: str, nome: str | re.Pattern):
        """Primeiro controle visível com o papel e o nome acessível."""
        localizador = self.page.get_by_role(papel, name=nome).locator("visible=true")
        return localizador.first if localizador.count() else None

    def clicar(self, papel: str, nome: str | re.Pattern, onde: str) -> bool:
        alvo = self.alvo(papel, nome)
        if alvo is None:
            self.info(onde, f"Controle «{nome}» ({papel}) não encontrado (lista vazia ou rótulo alterado).")
            return False
        alvo.scroll_into_view_if_needed()
        alvo.click()
        aguardar_app(self.page)
        return True

    def abrir_dialogo(self, papel: str, nome, onde: str, foto: str, fechar: bool = True) -> bool:
        if not self.clicar(papel, nome, onde):
            return False
        if not esperar_dialogo(self.page):
            self.reg("P0", "dialogo-nao-abre", onde, f"«{nome}» não abriu o diálogo.")
            return False
        verificar_dialogo(self.page, self.reg, onde)
        self.medir(f"{onde} (diálogo)", foto)
        if fechar:
            fechar_dialogo(self.page)
        return True

    def textos(self, seletor: str) -> list[str]:
        return [" ".join(t.split()) for t in self.page.locator(seletor).all_inner_texts()]

    def avisos(self) -> list[str]:
        return self.textos("#avisos .aviso")

    def erros_do_formulario(self) -> list[str]:
        return self.textos("dialog[open] .msg-erro, dialog[open] .aviso.erro, main form .msg-erro, main form .aviso.erro")

    def enviar_dialogo(self, onde: str, foto: str | None = None) -> list[str]:
        """Envia o diálogo aberto e devolve os avisos da página seguinte. Levanta FormularioRecusado se houver erro."""
        self.medir(f"{onde} (preenchido)", foto)
        self.page.locator("dialog[open] .dialogo-rodape button[type=submit]").click()
        return self._esperar_resultado(onde)

    def enviar_formulario(self, botao, onde: str) -> list[str]:
        botao.click()
        return self._esperar_resultado(onde)

    def _esperar_resultado(self, onde: str) -> list[str]:
        resolvido = esperar_ate(
            self.page,
            "() => !!document.querySelector('#avisos .aviso, dialog[open] .msg-erro, dialog[open] .aviso.erro, "
            "main form .msg-erro, main form .aviso.erro') || (!document.querySelector('dialog[open]') && "
            "!document.querySelector('.htmx-request'))",
            timeout_ms=20_000,
        )
        aguardar_app(self.page)
        erros = self.erros_do_formulario()
        if erros:
            raise FormularioRecusado(f"{onde}: " + " | ".join(dict.fromkeys(erros))[:300])
        if not resolvido:
            raise FormularioRecusado(f"{onde}: o envio não terminou em 20 s")
        return self.avisos()

    def preencher(self, seletor: str, valor: str) -> None:
        self.page.locator(seletor).fill(valor)

    def escolher(self, seletor: str, indice: int = 0) -> str:
        """Seleciona a opção de posição `indice` e devolve o texto dela."""
        opcoes = self.page.locator(f"{seletor} option")
        texto = opcoes.nth(indice).inner_text()
        self.page.locator(seletor).select_option(index=indice)
        return " ".join(texto.split())

    def esperar_previa(self) -> None:
        """Os campos com hx-trigger recalculam trechos do formulário; espera terminar."""
        self.page.wait_for_timeout(500)
        aguardar_app(self.page)
