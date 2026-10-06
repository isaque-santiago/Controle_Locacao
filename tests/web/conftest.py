"""Fakes e fixtures do app web: serviço de autenticação simulado e relógio controlável."""

import re
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

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


DADOS_PAINEL = {
    "data_extenso": "terça-feira, 6 de outubro de 2026",
    "frota_total": 5,
    "contagem": {"alugada": 3, "disponivel": 1, "manutencao": 1, "inativa": 0},
    "ocupacao": 60,
    "segmentos_medidor": ["cheio", "cheio", "cheio", "oficina", ""],
    "descricao_medidor": "Frota de 5 motos: 3 alugadas, 1 disponíveis, 1 em manutenção, 0 inativas",
    "legenda": [
        SimpleNamespace(status="alugada", quantidade=3, rotulo="3 alugadas"),
        SimpleNamespace(status="disponivel", quantidade=1, rotulo="1 disponíveis"),
        SimpleNamespace(status="manutencao", quantidade=1, rotulo="1 em manutenção"),
        SimpleNamespace(status="inativa", quantidade=0, rotulo="0 inativas"),
    ],
    "recebido": Decimal("1480.00"),
    "previsto": Decimal("2000.00"),
    "percentual_recebido": 74,
    "atrasado": Decimal("320.00"),
    "clientes_atrasados": 1,
    "manutencao_mes": Decimal("85.00"),
    "ordens_concluidas": 1,
    "hoje": [
        {"id": "c1", "cliente": "Joana <b>Prado</b>", "placa": "QRS4T21", "vencimento": "2026-10-01",
         "valor": Decimal("320.00"), "atrasada": True, "dias_atraso": 5},
        {"id": "c2", "cliente": "Marcos Teles", "placa": "BRA2E19", "vencimento": "2026-10-06",
         "valor": Decimal("290.00"), "atrasada": False, "dias_atraso": 0},
    ],
    "alertas": [
        SimpleNamespace(quantidade=2, titulo="Manutenção vencida", descricao="Óleo e mais 1", tom="perigo", area="manutencao"),
        SimpleNamespace(quantidade=1, titulo="Documento a vencer", descricao="próximos 30 dias", tom="atencao", area="documentos"),
    ],
}


@pytest.fixture(autouse=True)
def dados_painel_falsos(monkeypatch):
    """Nenhum teste de rota fala com o Supabase: a camada de dados do Dashboard é trocada."""
    from src.web import dados_painel

    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: DADOS_PAINEL)


def _moto(i, status="disponivel", **extra):
    return {
        "id": f"00000000-0000-0000-0000-{i:012d}",
        "placa": f"ABC{i % 10}D{i % 100:02d}",
        "marca": "Honda",
        "modelo": f"CG {100 + i}",
        "cor": "Vermelha",
        "ano_fabricacao": 2023,
        "ano_modelo": 2023,
        "km_atual": 1000 * i,
        "status": status,
        **extra,
    }


class BaseMotos:
    """Dados fictícios que os serviços de motos devolvem nos testes das rotas."""

    def __init__(self):
        self.motos = [
            _moto(1, "alugada"),
            _moto(2, "disponivel", marca="Yamaha", modelo="Factor"),
            _moto(3, "inativa"),
        ]
        self.contratos = [
            {"id": "k1", "moto_id": self.motos[0]["id"], "cliente_id": "c1", "status": "ativo"},
        ]
        self.clientes = [{"id": "c1", "nome": "Joana <b>Prado</b>"}]
        self.plano = [
            {"moto_id": self.motos[0]["id"], "situacao": "vencida", "km_restantes": -120, "dias_restantes": None},
        ]


@pytest.fixture(autouse=True)
def base_motos(monkeypatch):
    """Troca os serviços usados por src/web/dados_motos; a montagem dos dados roda de verdade."""
    from src.web import dados_motos

    base = BaseMotos()
    monkeypatch.setattr(dados_motos, "motos", SimpleNamespace(listar=lambda: base.motos))
    monkeypatch.setattr(dados_motos, "contratos", SimpleNamespace(listar=lambda: base.contratos))
    monkeypatch.setattr(dados_motos, "clientes", SimpleNamespace(listar=lambda: base.clientes))
    monkeypatch.setattr(dados_motos, "alertas", SimpleNamespace(listar_manutencao=lambda: base.plano))
    return base


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
