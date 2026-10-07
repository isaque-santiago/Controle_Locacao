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
        self.leituras = [
            {"km": 1000, "data": "2026-09-01", "origem": "manual"},
            {"km": 900, "data": "2026-08-01", "origem": "contrato"},
        ]
        self.plano_da_moto = [
            {
                "item": {"nome": "Troca de óleo"},
                "intervalo_km_efetivo": 3000, "intervalo_minimo_km_efetivo": None,
                "intervalo_dias_efetivo": None, "ultima_km": 500, "proxima_km": 3500, "proxima_data": None,
            }
        ]
        self.manutencoes = [
            {"data_entrada": "2026-08-28", "tipo": "preventiva", "descricao": "Óleo <i>e filtro</i>",
             "km": 900, "oficina": None, "custo_total": Decimal("85.00")},
        ]
        self.documentos = [
            {"id": "00000000-0000-0000-0000-0000000000d1", "tipo": "crlv", "ano_referencia": 2026, "descricao": None,
             "vencimento": "2020-01-01", "regularizado": False},
        ]
        self.cobrancas = [
            {"situacao": "aberta", "tipo": "locacao", "vencimento": "2026-10-10"},
            {"situacao": "aberta", "tipo": "locacao", "vencimento": "2026-10-03"},
        ]
        self.financeiro = [
            {"moto_id": self.motos[0]["id"], "receita_recebida": Decimal("1200"), "custo_manutencao": Decimal("85"),
             "custo_documentos": Decimal("0"), "resultado": Decimal("1115"), "custo_por_km": Decimal("0.09")},
        ]
        self.contratos.append(
            {"id": "k0", "moto_id": self.motos[0]["id"], "cliente_id": "c1", "status": "encerrado",
             "data_inicio": "2026-01-01", "data_encerramento": "2026-06-30", "valor_periodo": Decimal("300"),
             "periodicidade": "semanal", "caucao_valor": Decimal("0")}
        )
        self.contratos[0].update(
            data_inicio="2026-07-01", data_encerramento=None, valor_periodo=Decimal("320"),
            periodicidade="semanal", caucao_valor=Decimal("500"),
        )


@pytest.fixture(autouse=True)
def base_motos(monkeypatch):
    """Troca os serviços usados por src/web/dados_motos; a montagem dos dados roda de verdade."""
    from src.web import dados_motos

    base = BaseMotos()
    monkeypatch.setattr(
        dados_motos,
        "motos",
        SimpleNamespace(
            listar=lambda: base.motos,
            obter=lambda id_: next((m for m in base.motos if m["id"] == id_), None),
            historico=lambda id_: base.leituras,
        ),
    )
    monkeypatch.setattr(dados_motos, "contratos", SimpleNamespace(listar=lambda: base.contratos))
    monkeypatch.setattr(dados_motos, "clientes", SimpleNamespace(listar=lambda: base.clientes))
    monkeypatch.setattr(dados_motos, "alertas", SimpleNamespace(listar_manutencao=lambda: base.plano))
    monkeypatch.setattr(
        dados_motos,
        "manutencao",
        SimpleNamespace(
            listar_plano_moto=lambda id_: base.plano_da_moto,
            situacao_item_plano=lambda linha, km: "proxima",
            listar_manutencoes=lambda id_: base.manutencoes,
        ),
    )
    monkeypatch.setattr(dados_motos, "documentos", SimpleNamespace(listar_por_moto=lambda id_: base.documentos))
    monkeypatch.setattr(dados_motos, "cobrancas", SimpleNamespace(listar_por_contrato=lambda id_: base.cobrancas))
    monkeypatch.setattr(
        dados_motos, "relatorios", SimpleNamespace(resultado_por_moto=lambda i, f: {"resultado": base.financeiro})
    )
    return base


class AcoesMotosFalsas:
    """Registra as gravações em vez de falar com o banco; `falhar_com` faz a próxima gravação levantar."""

    def __init__(self, base):
        self.base = base
        self.chamadas: list[tuple] = []
        self.falhar_com: Exception | None = None

    def _gravar(self, nome, *args):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.chamadas.append((nome, *args))

    def criar_moto(self, dados):
        self._gravar("criar_moto", dados)
        return {"id": "00000000-0000-0000-0000-0000000000aa", **dados}

    def atualizar_moto(self, moto_id, dados):
        self._gravar("atualizar_moto", moto_id, dados)
        return {"id": moto_id, **dados}

    def registrar_km(self, moto_id, km, confirmar, chave):
        self._gravar("registrar_km", moto_id, km, confirmar, chave)
        return {}

    def alterar_situacao(self, moto_id, inativar):
        self._gravar("alterar_situacao", moto_id, inativar)
        return {}

    def obter_documento(self, documento_id):
        return next(
            ({**d, "moto_id": self.base.motos[0]["id"]} for d in self.base.documentos if d["id"] == documento_id),
            None,
        )

    def regularizar_documento(self, documento_id, data):
        self._gravar("regularizar_documento", documento_id, data)
        return {}


@pytest.fixture(autouse=True)
def acoes_motos_falsas(monkeypatch, base_motos):
    from src.web import acoes_motos

    falsas = AcoesMotosFalsas(base_motos)
    for nome in (
        "criar_moto", "atualizar_moto", "registrar_km", "alterar_situacao",
        "obter_documento", "regularizar_documento",
    ):
        monkeypatch.setattr(acoes_motos, nome, getattr(falsas, nome))
    return falsas


class BaseClientes:
    def __init__(self):
        self.id = "00000000-0000-0000-0000-0000000000c1"
        self.clientes = [{"id": self.id, "nome": "Maria <b>Silva</b>", "cpf": "52998224725",
                          "telefone": "11987654321", "whatsapp": "11987654321", "email": "maria@example.com",
                          "endereco": "Rua Um", "cnh_numero": "123", "cnh_categoria": "A",
                          "cnh_validade": "2027-10-06", "status": "ativo", "observacoes": None}]
        self.motos = [{"id": "m1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG"}]
        self.contratos = [{"id": "k1", "cliente_id": self.id, "moto_id": "m1", "status": "ativo",
                           "data_inicio": "2026-01-01", "data_encerramento": None,
                           "valor_periodo": Decimal("300"), "caucao_valor": Decimal("500"), "periodicidade": "semanal"}]
        self.cobrancas = [{"id": "b1", "vencimento": "2026-10-01", "tipo": "locacao", "valor": Decimal("300"),
                            "saldo": Decimal("100"), "situacao": "atrasada"},
                           {"id": "b2", "vencimento": "2026-10-08", "tipo": "locacao", "valor": Decimal("300"),
                            "saldo": Decimal("300"), "situacao": "aberta"}]
        self.troca_id = "00000000-0000-0000-0000-0000000000f1"
        self.trocas = [{"id": self.troca_id, "criado_em": "2026-09-20T10:00:00+00:00", "km": 12500, "km_excedente": 300,
                        "cobranca_id": "b9", "foto_painel_path": "c1/painel.jpg", "nota_fiscal_path": "c1/nota.jpg"}]


@pytest.fixture(autouse=True)
def base_clientes(monkeypatch):
    from src.web import dados_clientes
    base = BaseClientes()
    monkeypatch.setattr(dados_clientes, "clientes", SimpleNamespace(listar=lambda: base.clientes, obter=lambda id_: next((c for c in base.clientes if c["id"] == id_), None)))
    monkeypatch.setattr(dados_clientes, "contratos", SimpleNamespace(listar=lambda: base.contratos))
    monkeypatch.setattr(dados_clientes, "motos", SimpleNamespace(listar=lambda: base.motos))
    monkeypatch.setattr(dados_clientes, "configuracoes", SimpleNamespace(obter=lambda: {"alerta_cnh_dias": 30}))
    monkeypatch.setattr(dados_clientes, "portal_locatario", SimpleNamespace(listar_trocas=lambda id_: base.trocas))
    monkeypatch.setattr(dados_clientes, "cobrancas", SimpleNamespace(
        listar_por_contrato=lambda id_: base.cobrancas,
        historicos_pagamentos=lambda ids: {id_: [] for id_ in ids},
    ))
    return base


@pytest.fixture(autouse=True)
def acoes_clientes_falsas(monkeypatch, base_clientes):
    from src.web import acoes_clientes
    chamadas = []
    def criar(dados):
        chamadas.append(("criar", dados)); return {"id": base_clientes.id, **dados}
    def atualizar(cliente_id, dados):
        chamadas.append(("atualizar", cliente_id, dados)); return {"id": cliente_id, **dados}
    def acesso(nome, senha="Senha-Temp-123"):
        def chamar(cliente_id):
            chamadas.append((nome, cliente_id))
            return {"email": "52998224725@locatario.local", "senha": senha}
        return chamar
    def remover(cliente_id):
        chamadas.append(("remover_acesso", cliente_id))
    monkeypatch.setattr(acoes_clientes, "criar_cliente", criar)
    monkeypatch.setattr(acoes_clientes, "atualizar_cliente", atualizar)
    monkeypatch.setattr(acoes_clientes, "criar_acesso_portal", acesso("criar_acesso"))
    monkeypatch.setattr(acoes_clientes, "redefinir_senha_portal", acesso("redefinir_senha"))
    monkeypatch.setattr(acoes_clientes, "remover_acesso_portal", remover)
    monkeypatch.setattr(acoes_clientes, "url_arquivo_troca", lambda caminho: f"https://storage.exemplo/assinada/{caminho}?token=x")
    return chamadas


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
