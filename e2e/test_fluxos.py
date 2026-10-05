"""Fluxos mínimos de homologação (Etapa 9) 2 a 10.

Na Etapa 0 os cenários percorrem cada fluxo até o ponto de gravar: abrem páginas,
diálogos e assistentes e verificam o layout, mas fecham SEM salvar. A submissão real
(criar contrato, registrar pagamento etc.) entra nas Etapas 5 e 9, quando os
formulários estiverem migrados. Controles não encontrados viram achado INFO
(lista vazia ou rótulo alterado), nunca falha do teste."""

import re
from dataclasses import dataclass
from typing import Callable

import pytest

from e2e.ajudas import aguardar_app, esperar_dialogo, fechar_dialogo, ir_para
from e2e.config import PAGINAS
from e2e.verificacoes import (
    achados_bloqueantes,
    capturar,
    verificar_acessibilidade,
    verificar_dialogo,
    verificar_layout,
    verificar_saude,
)

pytestmark = pytest.mark.autenticado


def _pagina(titulo):
    return next(p for p in PAGINAS if p.titulo == titulo)


@dataclass
class Contexto:
    page: object
    cenario: object
    reg: Callable
    capturas: bool

    def visitar(self, titulo: str) -> None:
        if ir_para(self.page, _pagina(titulo)):
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

    def botao(self, padrao: str):
        alvo = self.page.get_by_role("button", name=re.compile(padrao, re.I)).first
        return alvo if alvo.count() else None

    def clicar(self, padrao: str, onde: str) -> bool:
        alvo = self.botao(padrao)
        if alvo is None:
            self.reg(
                "INFO",
                "controle-nao-encontrado",
                onde,
                f"Botão /{padrao}/ não encontrado (lista vazia ou rótulo alterado).",
            )
            return False
        alvo.scroll_into_view_if_needed()
        alvo.click()
        aguardar_app(self.page)
        return True

    def abrir_dialogo(self, padrao: str, onde: str, foto: str) -> None:
        if not self.clicar(padrao, onde):
            return
        if not esperar_dialogo(self.page):
            self.reg("P0", "dialogo-nao-abre", onde, f"O botão /{padrao}/ não abriu o diálogo.")
            return
        verificar_dialogo(self.page, self.reg, onde)
        self.medir(f"{onde} (diálogo)", foto)
        fechar_dialogo(self.page)


# --------------------------------------------------------------------------
# Fluxos
# --------------------------------------------------------------------------
def fluxo_dashboard(c: Contexto) -> None:
    c.visitar("Dashboard")


def _abrir_ficha_e_voltar(c: Contexto, pagina: str, voltar: str) -> None:
    c.visitar(pagina)
    busca = c.page.get_by_role("textbox").first
    if busca.count():
        busca.fill("a")
        busca.press("Enter")
        aguardar_app(c.page)
        c.medir(f"{pagina} (busca)", f"{pagina}-busca")
    if c.clicar(r"\b(abrir|ver contrato)\b", pagina):
        c.medir(f"{pagina} (ficha)", f"{pagina}-ficha")
        c.clicar(voltar, f"{pagina} (ficha)")


def fluxo_buscar_e_abrir_fichas(c: Contexto) -> None:
    _abrir_ficha_e_voltar(c, "Motos", r"voltar para motos")
    _abrir_ficha_e_voltar(c, "Clientes", r"voltar para clientes")


def fluxo_contrato(c: Contexto) -> None:
    c.visitar("Contratos")
    if c.clicar(r"novo contrato", "Contratos"):
        c.medir("Contratos (assistente)", "contratos-assistente")
        c.clicar(r"voltar para contratos", "Contratos (assistente)")


def fluxo_pagamento(c: Contexto) -> None:
    c.visitar("Cobranças")
    c.abrir_dialogo(r"\bpagar\b", "Cobranças", "cobrancas-pagamento")


def fluxo_manutencao(c: Contexto) -> None:
    c.visitar("Manutenção")
    c.abrir_dialogo(r"registrar manutenção", "Manutenção", "manutencao-registrar")


def fluxo_documento(c: Contexto) -> None:
    c.visitar("Documentos")
    c.abrir_dialogo(r"novo documento", "Documentos", "documentos-novo")


def fluxo_vistoria(c: Contexto) -> None:
    c.visitar("Vistorias")
    c.abrir_dialogo(r"registrar vistoria", "Vistorias", "vistorias-registrar")


def fluxo_relatorios(c: Contexto) -> None:
    c.visitar("Relatórios")
    abas = c.page.get_by_role("tab")
    for i in range(abas.count()):
        nome = abas.nth(i).inner_text().strip()
        abas.nth(i).click()
        aguardar_app(c.page)
        c.medir(f"Relatórios · aba {nome}", f"relatorios-{nome}")


def fluxo_configuracoes(c: Contexto) -> None:
    c.visitar("Configurações")


# O fluxo 1 (entrar e navegar) é coberto por test_login.py e test_paginas.py.
FLUXOS = {
    "02-dashboard-e-alertas": fluxo_dashboard,
    "03-buscar-filtrar-abrir-moto-e-cliente": fluxo_buscar_e_abrir_fichas,
    "04-criar-contrato": fluxo_contrato,
    "05-registrar-pagamento": fluxo_pagamento,
    "06-registrar-e-concluir-manutencao": fluxo_manutencao,
    "07-cadastrar-e-regularizar-documento": fluxo_documento,
    "08-registrar-abrir-e-comparar-vistorias": fluxo_vistoria,
    "09-filtrar-e-exportar-relatorios": fluxo_relatorios,
    "10-alterar-configuracoes-e-backup": fluxo_configuracoes,
}


@pytest.mark.parametrize("nome_fluxo", list(FLUXOS))
def test_fluxo(nome_fluxo, pagina_logada, cenario, registrar, coletor, request):
    reg = registrar(cenario, fluxo=nome_fluxo)
    contexto = Contexto(pagina_logada, cenario, reg, request.config.getoption("--capturas"))
    try:
        FLUXOS[nome_fluxo](contexto)
    except Exception as erro:
        reg("P0", "fluxo-interrompido", nome_fluxo, f"{type(erro).__name__}: {str(erro)[:200]}")
    finally:
        fechar_dialogo(pagina_logada)

    if request.config.getoption("--e2e-estrito"):
        bloqueantes = achados_bloqueantes(coletor, cenario, fluxo=nome_fluxo)
        assert not bloqueantes, [f"{a.pagina}: {a.descricao}" for a in bloqueantes]
