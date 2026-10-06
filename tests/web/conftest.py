"""Fakes e fixtures do app web: serviço de autenticação simulado e relógio controlável."""

import re
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.domain.acesso_locatario import identificador_para_email
from src.services.autenticacao import (
    CredenciaisInvalidas,
    SessaoSupabaseInvalida,
    TokensUsuario,
)
from src.web.app import criar_app

CPF_LOCATARIO = "123.456.789-09"
VALIDADE_TOKEN = 3600


class Relogio:
    def __init__(self, agora: float = 1_000_000.0):
        self.agora = agora

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@dataclass
class ClienteFalso:
    access_token: str


class ServicoFalso:
    """Imita ServicoAutenticacao sem falar com o Supabase."""

    def __init__(self, relogio: Relogio):
        self.relogio = relogio
        self.usuarios = {
            "dono@exemplo.com": ("senha-dono", "dono"),
            identificador_para_email(CPF_LOCATARIO): ("senha-locatario", "locatario"),
            "sem-papel@exemplo.com": ("senha-x", None),
        }
        self.entradas = 0
        self.renovacoes = 0
        self.saidas: list[str] = []
        self.renovacao_recusada = False
        self._emitidos = 0
        self._papel_do_token: dict[str, str | None] = {}

    def _emitir(self, email: str, papel) -> TokensUsuario:
        self._emitidos += 1
        token = f"access-{self._emitidos}"
        self._papel_do_token[token] = papel
        return TokensUsuario(
            usuario_id=f"id-{email}",
            email=email,
            access_token=token,
            refresh_token=f"refresh-{self._emitidos}",
            expira_em=self.relogio() + VALIDADE_TOKEN,
        )

    def entrar(self, identificador, senha):
        self.entradas += 1
        email = identificador_para_email(identificador).strip().lower()
        cadastro = self.usuarios.get(email)
        if cadastro is None or cadastro[0] != senha:
            raise CredenciaisInvalidas()
        return self._emitir(email, cadastro[1])

    def renovar(self, refresh_token):
        self.renovacoes += 1
        if self.renovacao_recusada:
            raise SessaoSupabaseInvalida()
        return self._emitir("dono@exemplo.com", "dono")

    def cliente(self, access_token):
        return ClienteFalso(access_token)

    def papel(self, cliente):
        return self._papel_do_token[cliente.access_token]

    def sair(self, access_token):
        self.saidas.append(access_token)


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def servico(relogio):
    return ServicoFalso(relogio)


@pytest.fixture
def app(servico, relogio):
    return criar_app(servico=servico, relogio=relogio, desenvolvimento=False)


@pytest.fixture
def cliente(app):
    # Sem seguir redirecionamentos: os testes conferem o destino. Erros do servidor viram 500.
    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


def extrair_csrf(html: str) -> str:
    achado = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert achado, "token CSRF não encontrado na página"
    return achado.group(1)


def entrar(cliente, identificador="dono@exemplo.com", senha="senha-dono", proximo="/"):
    """Faz login pela tela (com o CSRF do formulário) e devolve a resposta do POST."""
    pagina = cliente.get("/login")
    return cliente.post(
        "/login",
        data={
            "identificador": identificador,
            "senha": senha,
            "proximo": proximo,
            "csrf_token": extrair_csrf(pagina.text),
        },
    )


def csrf_da_sessao(cliente) -> str:
    return extrair_csrf(cliente.get("/").text)
