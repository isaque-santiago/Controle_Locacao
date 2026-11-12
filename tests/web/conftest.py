"""Fakes e fixtures do app web: serviço de autenticação simulado e relógio controlável."""

import re
from dataclasses import dataclass
from datetime import date
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
        self.senhas: list[tuple[str, str]] = []
        self.senha_recusada = None
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

    def alterar_senha(self, access_token, nova):
        if self.senha_recusada:
            raise self.senha_recusada
        self.senhas.append((access_token, nova))

    def sair(self, access_token):
        self.saidas.append(access_token)


def _conteudo_hoje():
    return {"hoje": {
        "mes_texto": "2026-10",
        "cobranca": {
            "linhas": [
                {"contrato_id": "k1", "cobranca_id": "00000000-0000-0000-0000-0000000000a1", "cliente": "Joana <b>Prado</b>",
                 "placa": "QRS4T21", "dias_atraso": 44, "faixa": "inadimplente", "debito": Decimal("2100.00"), "hoje": Decimal("0.00"),
                 "encargos": Decimal("176.00"), "total": Decimal("2276.00")},
                {"contrato_id": "k2", "cobranca_id": "00000000-0000-0000-0000-0000000000a2", "cliente": "Marcos Teles", "placa": "BRA2E19",
                 "dias_atraso": 6, "faixa": "em_atraso", "debito": Decimal("290.00"), "hoje": Decimal("0.00"),
                 "encargos": Decimal("57.00"), "total": Decimal("347.00")},
                {"contrato_id": "k3", "cobranca_id": "00000000-0000-0000-0000-0000000000a3", "cliente": "Diego", "placa": "—",
                 "dias_atraso": 0, "faixa": "hoje", "debito": Decimal("0.00"), "hoje": Decimal("280.00"),
                 "encargos": Decimal("15.00"), "total": Decimal("295.00")},
            ],
            "total_linhas": 3, "a_cobrar": Decimal("2670.00"), "em_atraso": Decimal("2390.00"), "vencem_hoje": Decimal("280.00"),
            "encargos": Decimal("248.00"), "contratos_em_atraso": 1, "contratos_inadimplentes": 1, "contratos_so_hoje": 1,
            "faixas_atraso": [
                {"rotulo": "1 a 6 dias", "classe": "f1", "contratos": 0, "valor": Decimal("0.00"), "inicio": 0.0, "tamanho": 0.0},
                {"rotulo": "7 a 14 dias", "classe": "f2", "contratos": 1, "valor": Decimal("290.00"), "inicio": 0.0, "tamanho": 12.1},
                {"rotulo": "15 a 30 dias", "classe": "f3", "contratos": 0, "valor": Decimal("0.00"), "inicio": 12.1, "tamanho": 0.0},
                {"rotulo": "31 dias ou mais", "classe": "f4", "contratos": 1, "valor": Decimal("2100.00"), "inicio": 12.1, "tamanho": 87.9},
            ],
        },
        "faixas": {"em_atraso": "até 14 dias", "inadimplente": "15 dias ou mais"},
        "frota": {"total": 5, "contagem": {"alugada": 3, "disponivel": 1, "manutencao": 1, "inativa": 0}, "ativas": 5, "ocupacao": 60,
                  "segmentos": [{"classe": "cheio", "inicio": 0.0, "tamanho": 60.0}, {"classe": "oficina", "inicio": 60.0, "tamanho": 20.0},
                                {"classe": "livre", "inicio": 80.0, "tamanho": 20.0}],
                  "descricao": "Frota de 5 motos: 3 alugadas, 1 disponíveis, 1 em manutenção, 0 inativas"},
        "caixa": {"valor": Decimal("-3451.93"), "investimento": Decimal("800.00"),
                  "serie": {"pontos": "3.0,21.0 60.0,12.0 117.0,3.0", "ultimo": {"x": 117.0, "y": 3.0}, "largura": 120, "altura": 24,
                            "primeiro": Decimal("-450.00"), "final": Decimal("-3451.93"), "minimo": Decimal("-3451.93"), "maximo": Decimal("-450.00")}},
        "atencao_financeira": [],
        "proximos": {"dias": 7, "entra": Decimal("1250.00"), "n_entra": 5, "sai": Decimal("1536.23"), "n_sai": 1, "saldo": Decimal("-286.23")},
        "atencao": [
            SimpleNamespace(quantidade=1, titulo="Parcela de dívida atrasada", descricao="R$ 1.000,00 em atraso", tom="perigo", area="dividas"),
            SimpleNamespace(quantidade=2, titulo="Manutenção vencida", descricao="Óleo e mais 1", tom="perigo", area="manutencao"),
            SimpleNamespace(quantidade=1, titulo="Documento a vencer", descricao="próximos 30 dias", tom="atencao", area="documentos"),
            SimpleNamespace(quantidade=None, titulo="Despesa a repassar ao locatário", descricao="R$ 40,00", tom="atencao", area=None),
        ],
    }}


def _conteudo_dinheiro():
    return {"dinheiro": {
        "mes": date(2026, 10, 1), "mes_texto": "2026-10", "mes_rotulo": "outubro de 2026", "mes_anterior": "2026-09",
        "mes_seguinte": None, "mes_maximo": "2026-10", "e_mes_atual": True, "anterior": None,
        "atual": {"mes": date(2026, 10, 1), "receita": Decimal("3445.50"), "despesas": Decimal("5161.20"),
                  "investimento": Decimal("800.00"), "parcelas_divida": Decimal("1056.23"),
                  "retiradas": Decimal("0.00"), "aportes": Decimal("120.00"), "resultado": Decimal("-1715.70"),
                  "caixa": Decimal("-3451.93"), "margem": -50},
        "evolucao": [
            {"mes": date(2026, 9, 1), "rotulo": "set./26", "receita": Decimal("0.00"), "despesas": Decimal("450.00"),
             "resultado": Decimal("-450.00"), "caixa": Decimal("-450.00")},
            {"mes": date(2026, 10, 1), "rotulo": "out./26", "receita": Decimal("3445.50"),
             "despesas": Decimal("5161.20"), "resultado": Decimal("-1715.70"), "caixa": Decimal("-3451.93")},
        ],
        "previsto": Decimal("15650.00"), "percentual_previsto": 22, "esperado_ate_hoje": Decimal("9000.00"), "percentual_esperado": 57,
        "variacoes": None,
        "dividas": {"total": Decimal("32014.34"), "moto_fiado": Decimal("32014.34")},
        "receita_estimada": Decimal("27155.00"),
        "receita_semana": Decimal("3245.50"),
        "grafico": {
            "largura": 600, "altura": 208, "y_base": 180, "y_rotulo": 200,
            "colunas": [
                {"rotulo": "set./26", "x_rotulo": 150.0,
                 "receita": {"x": 102.0, "y": 180.0, "largura": 90.0, "altura": 0.0, "valor": Decimal("0.00")},
                 "despesas": {"x": 196.0, "y": 170.0, "largura": 90.0, "altura": 10.0, "valor": Decimal("450.00")}},
                {"rotulo": "out./26", "x_rotulo": 450.0,
                 "receita": {"x": 402.0, "y": 90.0, "largura": 90.0, "altura": 90.0, "valor": Decimal("3445.50")},
                 "despesas": {"x": 496.0, "y": 60.0, "largura": 90.0, "altura": 120.0, "valor": Decimal("5161.20")}},
            ],
        },
        "entradas": {
            "linhas": [{"conta": "Luiza", "valor": Decimal("865.50"), "proporcao": 100},
                       {"conta": "Sem conta informada", "valor": Decimal("2180.00"), "proporcao": 60}],
            "total": Decimal("3045.50"), "sem_conta": Decimal("2180.00"),
        },
        "categorias": {
            "linhas": [{"categoria": "manutencao", "rotulo": "Manutenção", "valor": Decimal("3735.00"), "proporcao": 100},
                       {"categoria": "outros", "rotulo": "Outros", "valor": Decimal("139.00"), "proporcao": 4}],
            "total": Decimal("3874.00"),
        },
    }}


def _conteudo_frota():
    return {"frota": {
        "total": 5, "contagem": {"alugada": 3, "disponivel": 1, "manutencao": 1, "inativa": 0}, "ocupacao": 60, "ativas": 5,
        "rosca": [
            {"classe": "cheio", "inicio": 0.0, "tamanho": 60.0},
            {"classe": "oficina", "inicio": 60.0, "tamanho": 20.0},
            {"classe": "livre", "inicio": 80.0, "tamanho": 20.0},
        ],
        "descricao_medidor": "Frota de 5 motos: 3 alugadas, 1 disponíveis, 1 em manutenção, 0 inativas",
        "legenda": [
            SimpleNamespace(status="alugada", quantidade=3, rotulo="3 alugadas", percentual=60),
            SimpleNamespace(status="disponivel", quantidade=1, rotulo="1 disponíveis", percentual=20),
            SimpleNamespace(status="manutencao", quantidade=1, rotulo="1 em manutenção", percentual=20),
            SimpleNamespace(status="inativa", quantidade=0, rotulo="0 inativas", percentual=None),
        ],
        "ordens_concluidas": 1, "manutencao_aberta": {"quantidade": 0, "total": Decimal("0")},
        "manutencao_mes": Decimal("85.00"), "mes_rotulo": "outubro de 2026",
        "receita_por_moto": Decimal("689.10"), "tempo_parado": {"dias": 12, "percentual": Decimal("8.0")},
        "paradas": {"total": 2, "linhas": [
            {"moto_id": "m3", "placa": "OSL8828", "motivo": "Em manutenção", "desde": date(2026, 9, 28), "dias": 8},
            {"moto_id": "m4", "placa": "PMP2B63", "motivo": "Disponível", "desde": None, "dias": None}]},
        "veiculos": [
            {"moto_id": "m1", "placa": "POU7015", "locatario": "JOSE <u>HENRIQUE</u>", "receita": Decimal("8200.00"),
             "despesas": Decimal("900.00"), "resultado": Decimal("7300.00")},
            {"moto_id": "m2", "placa": "—", "locatario": "—", "receita": Decimal("0.00"),
             "despesas": Decimal("120.00"), "resultado": Decimal("-120.00")},
        ],
    }}


def painel_falso(aba="hoje", compacto=False, ocultar=False, ajustes=None, **extra):
    """O dicionário que `dados_painel.carregar` devolve para a aba pedida, com dados fictícios.

    `ajustes` troca campos de dentro do bloco da aba (`{"hoje": {"caixa": None}}`); `extra` troca chaves do topo."""
    from src.domain import financeiro

    conteudo = {"hoje": _conteudo_hoje, "dinheiro": _conteudo_dinheiro, "frota": _conteudo_frota}[aba]()
    for chave, mudancas in (ajustes or {}).items():
        conteudo[chave] = {**conteudo[chave], **mudancas}
    bloco = conteudo.get("dinheiro", {})
    links = financeiro.links_do_painel(
        bloco.get("mes_texto"), bloco.get("mes_anterior"), bloco.get("mes_seguinte"), compacto, ocultar, aba)
    return {
        "data_extenso": "terça-feira, 6 de outubro de 2026", "aba": aba, "compacto": compacto, "ocultar": ocultar, "links": links,
        "abas": [{"chave": c, "rotulo": r, "href": "/" + links["abas"][c], "ativa": c == aba} for c, r in financeiro.ABAS],
        **conteudo, **extra,
    }


@pytest.fixture(autouse=True)
def dados_painel_falsos(monkeypatch):
    """Nenhum teste de rota fala com o Supabase: a camada de dados do Dashboard é trocada por dados fictícios da aba pedida."""
    from src.domain import financeiro
    from src.web import dados_painel

    monkeypatch.setattr(dados_painel, "carregar", lambda *a, **k: painel_falso(
        aba=financeiro.aba_do_painel(k.get("aba")), compacto=bool(k.get("compacto")), ocultar=bool(k.get("ocultar"))))


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
        self.vinculos = []  # linhas de contrato_motos: motos vinculadas (além da principal) de cada contrato
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
    monkeypatch.setattr(
        dados_motos, "contratos", SimpleNamespace(listar=lambda: base.contratos, listar_vinculos=lambda: base.vinculos)
    )
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


class BaseContratos:
    """Dados fictícios dos serviços usados por src/web/dados_contratos."""

    def __init__(self):
        self.id = "00000000-0000-0000-0000-0000000000d1"
        self.cliente = {"id": "00000000-0000-0000-0000-0000000000c1", "nome": "Maria <b>Silva</b>", "cpf": "52998224725", "status": "ativo"}
        self.moto = {"id": "00000000-0000-0000-0000-0000000000a1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG 160",
                     "km_atual": 12000, "status": "alugada"}
        self.cliente_bloqueado = {"id": "00000000-0000-0000-0000-0000000000c2", "nome": "Pedro Bloqueado", "cpf": "11144477735", "status": "bloqueado"}
        self.moto_livre = {"id": "00000000-0000-0000-0000-0000000000a2", "placa": "QRS4T21", "marca": "Yamaha", "modelo": "Factor",
                           "km_atual": 5000, "status": "disponivel", "valor_locacao_sugerido": Decimal("300")}
        self.moto_livre2 = {"id": "00000000-0000-0000-0000-0000000000a3", "placa": "ABC1D23", "marca": "Honda", "modelo": "Pop 110",
                            "km_atual": 800, "status": "disponivel", "valor_locacao_sugerido": Decimal("200")}
        self.vinculadas = {}
        self.com_vinculada = True  # motos_do_contrato devolve a QRS4T21 como vinculada
        self.contratos = [
            {"id": self.id, "cliente_id": self.cliente["id"], "moto_id": self.moto["id"], "status": "ativo",
             "data_inicio": "2026-08-01", "data_fim_prevista": None, "data_encerramento": None, "periodicidade": "semanal",
             "valor_periodo": Decimal("280"), "caucao_valor": Decimal("400"), "km_inicial": 10500},
            {"id": "00000000-0000-0000-0000-0000000000d2", "cliente_id": self.cliente["id"], "moto_id": self.moto["id"],
             "status": "encerrado", "data_inicio": "2026-01-01", "data_fim_prevista": "2026-06-30", "data_encerramento": "2026-06-30",
             "periodicidade": "mensal", "valor_periodo": Decimal("900"), "caucao_valor": Decimal("0"), "km_inicial": 8000},
        ]
        self.cobrancas = [
            {"id": "b1", "vencimento": "2026-08-01", "tipo": "caucao", "valor": Decimal("400"), "saldo": Decimal("0"), "situacao": "paga", "valor_pago": Decimal("400")},
            {"id": "b2", "vencimento": "2026-08-08", "tipo": "locacao", "valor": Decimal("280"), "saldo": Decimal("280"), "situacao": "atrasada", "valor_pago": Decimal("0")},
            {"id": "b3", "vencimento": "2026-10-20", "tipo": "locacao", "valor": Decimal("280"), "saldo": Decimal("280"), "situacao": "aberta", "valor_pago": Decimal("0")},
        ]
        self.pagamentos = {"b1": [{"data_pagamento": "2026-08-01"}]}
        self.vistorias = [{"tipo": "entrega", "data": "2026-08-01", "km": 10500, "nivel_combustivel": "cheio",
                           "checklist": {"freio_dianteiro": "avaria", "farol": "ok", "espelho_retrovisor": "avaria"}}]
        self.vistorias_vinculada = []  # vistorias da moto vinculada (QRS4T21) do contrato
        self.manutencoes = [
            {"data_entrada": "2026-09-10", "tipo": "preventiva", "descricao": "Óleo <i>e filtro</i>", "km": 11000,
             "cobrar_do_cliente": True, "custo_total": Decimal("85")},
            {"data_entrada": "2026-05-10", "tipo": "corretiva", "descricao": "Antes do contrato", "km": 9000,
             "cobrar_do_cliente": False, "custo_total": Decimal("50")},
        ]


@pytest.fixture(autouse=True)
def base_contratos(monkeypatch):
    from src.web import dados_contratos
    from src.web.rotas import contratos_encerramento
    from datetime import date

    base = BaseContratos()
    from src.services.contratos import previa_agenda

    # "Hoje" é 15/10/2026 nos fluxos de Contratos: as cobranças fictícias vencem em 20/10/2026 e, com o relógio real,
    # os testes passariam a falhar assim que essa data chegasse. As rotas importam o próprio `hoje_br`.
    for modulo in (dados_contratos, contratos_encerramento):
        monkeypatch.setattr(modulo, "hoje_br", lambda: date(2026, 10, 15))

    pessoas = [base.cliente, base.cliente_bloqueado]
    frota = [base.moto, base.moto_livre, base.moto_livre2]
    monkeypatch.setattr(dados_contratos, "contratos", SimpleNamespace(
        listar=lambda: base.contratos, previa_agenda=previa_agenda, contar_vinculadas=lambda: base.vinculadas,
        motos_do_contrato=lambda id_: [dict(base.moto, moto_id=base.moto["id"], principal=True)]
        + ([dict(base.moto_livre, moto_id=base.moto_livre["id"], principal=False)] if base.com_vinculada else [])))
    monkeypatch.setattr(dados_contratos, "clientes", SimpleNamespace(
        listar=lambda: pessoas, obter=lambda id_: next((c for c in pessoas if c["id"] == id_), None)))
    monkeypatch.setattr(dados_contratos, "motos", SimpleNamespace(
        listar=lambda: frota, obter=lambda id_: next((m for m in frota if m["id"] == id_), None)))
    monkeypatch.setattr(dados_contratos, "cobrancas", SimpleNamespace(
        listar_por_contrato=lambda id_: base.cobrancas,
        historicos_pagamentos=lambda ids: {i: base.pagamentos.get(i, []) for i in ids}))
    monkeypatch.setattr(dados_contratos, "vistorias", SimpleNamespace(
        listar_por_contrato=lambda id_, moto_id=None, todas=False: base.vistorias_vinculada if moto_id else base.vistorias))
    monkeypatch.setattr(dados_contratos, "manutencao", SimpleNamespace(listar_manutencoes=lambda id_: base.manutencoes))
    return base


class AcoesContratosFalsas:
    """Registra a criação em vez de falar com o banco; `falhar_com` faz a próxima gravação levantar."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.encerramentos: list[tuple] = []
        self.vistorias_vinculadas: list = []  # vistorias das vinculadas de cada chamada (criar ou encerrar)
        self.falhar_com: Exception | None = None

    def criar_contrato_com_vistoria(self, dados, vistoria, vistorias_vinculadas=None):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.chamadas.append((dados, vistoria))
        self.vistorias_vinculadas.append(vistorias_vinculadas)
        return {"contrato_id": "00000000-0000-0000-0000-0000000000e1"}

    def encerrar_contrato_com_vistoria(self, contrato_id, data, vistoria, valor_danos, descricao_danos, vistorias_vinculadas=None):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.encerramentos.append((contrato_id, data, vistoria, valor_danos, descricao_danos))
        self.vistorias_vinculadas.append(vistorias_vinculadas)
        return {}


@pytest.fixture(autouse=True)
def acoes_contratos_falsas(monkeypatch):
    from src.web import acoes_contratos

    falsas = AcoesContratosFalsas()
    monkeypatch.setattr(acoes_contratos, "criar_contrato_com_vistoria", falsas.criar_contrato_com_vistoria)
    monkeypatch.setattr(acoes_contratos, "encerrar_contrato_com_vistoria", falsas.encerrar_contrato_com_vistoria)
    return falsas


class BaseCobrancas:
    """Dados fictícios dos serviços usados por src/web/dados_cobrancas (hoje = 07/10/2026)."""

    def __init__(self):
        self.clientes = [{"id": "cl1", "nome": "Ana <b>Souza</b>"}, {"id": "cl2", "nome": "Bruno Lima"}]
        self.motos = [{"id": "m1", "placa": "BRA2E19"}, {"id": "m2", "placa": "QRS4T21"}]

        def c(id_, cliente, moto, venc, situacao, saldo="204", valor="204", **extra):
            return {"id": id_, "contrato_id": "k1", "cliente_id": cliente, "moto_id": moto, "tipo": "locacao",
                    "vencimento": venc, "valor": Decimal(valor), "saldo": Decimal(saldo), "situacao": situacao, **extra}

        self.cobrancas = [
            c("h1", "cl1", "m1", "2026-10-07", "aberta"),
            c("a1", "cl1", "m1", "2026-10-01", "atrasada", saldo="280", valor="280"),
            c("a2", "cl2", "m2", "2026-09-20", "atrasada", saldo="300", valor="300"),
            c("p1", "cl2", "m2", "2026-10-10", "aberta", numero=1),
            c("p2", "cl1", "m1", "2026-10-14", "aberta", numero=2),
            c("f1", "cl1", "m1", "2026-10-30", "aberta"),
            c("g1", "cl1", "m1", "2026-09-01", "paga", saldo="0", valor="280"),
            c("g2", "cl2", "m2", "2026-09-08", "paga", saldo="0", valor="300"),
        ]
        self.pagamentos = {
            "g1": [{"cobranca_id": "g1", "data_pagamento": "2026-09-02", "forma": "pix"}],
            "g2": [{"cobranca_id": "g2", "data_pagamento": "2026-09-09", "forma": "dinheiro"}],
        }


@pytest.fixture(autouse=True)
def base_cobrancas(monkeypatch):
    from datetime import date

    from src.services.cobrancas import calcular_encargos_cobranca
    from src.web import dados_cobrancas

    from src.web.rotas import cobrancas_cancelamento, cobrancas_mensagem, cobrancas_pagamento

    base = BaseCobrancas()
    # "Hoje" é 07/10/2026 em todo o fluxo de Cobranças (lista, mensagem e pagamento): as rotas importam o próprio
    # `hoje_br`, então o relógio congelado precisa valer em cada módulo, e não só na camada de dados.
    for modulo in (dados_cobrancas, cobrancas_cancelamento, cobrancas_mensagem, cobrancas_pagamento):
        monkeypatch.setattr(modulo, "hoje_br", lambda: date(2026, 10, 7))
    monkeypatch.setattr(dados_cobrancas, "clientes", SimpleNamespace(
        listar=lambda: base.clientes, obter=lambda id_: next((c for c in base.clientes if c["id"] == id_), None)))
    monkeypatch.setattr(dados_cobrancas, "motos", SimpleNamespace(
        listar=lambda: base.motos, obter=lambda id_: next((m for m in base.motos if m["id"] == id_), None)))
    monkeypatch.setattr(dados_cobrancas, "cobrancas", SimpleNamespace(
        listar=lambda: base.cobrancas,
        configuracao_encargos=lambda: {"multa_atraso_valor": "15", "encargo_diario_valor": "7"},
        calcular_encargos_cobranca=calcular_encargos_cobranca,
        historicos_pagamentos=lambda ids: {i: base.pagamentos.get(i, []) for i in ids},
    ))
    return base


class BaseManutencao:
    """Dados fictícios da parte somente leitura de Manutenção."""

    def __init__(self):
        self.motos = [
            {"id": "m1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG", "km_atual": 18420, "status": "alugada"},
            {"id": "m2", "placa": "QRS4T21", "marca": "Yamaha", "modelo": "Factor", "km_atual": 9000, "status": "disponivel"},
        ]
        self.alertas = [
            {"moto_id": "m1", "placa": "BRA2E19", "item": "Pneu <traseiro>", "km_atual": 18420,
             "proxima_km": 19000, "proxima_data": None, "km_restantes": 580, "dias_restantes": None,
             "situacao": "proxima"},
            {"moto_id": "m1", "placa": "BRA2E19", "item": "Filtro de ar", "km_atual": 18420,
             "proxima_km": 18000, "proxima_data": None, "km_restantes": -420, "dias_restantes": None,
             "situacao": "vencida"},
            {"moto_id": "m2", "placa": "QRS4T21", "item": "Em dia", "km_atual": 9000,
             "proxima_km": 12000, "proxima_data": None, "km_restantes": 3000, "dias_restantes": None,
             "situacao": "em_dia"},
        ]
        self.manutencoes = [
            {"id": "h1", "moto_id": "m1", "tipo": "preventiva", "status": "aberta",
             "data_entrada": "2026-09-01", "descricao": "Revisão <geral>", "oficina": "Central",
             "km": 18000, "custo_total": Decimal("95.00")},
            {"id": "h2", "moto_id": "m2", "tipo": "corretiva", "status": "concluida",
             "data_entrada": "2026-08-01", "descricao": "Buzina", "oficina": None,
             "km": 8900, "custo_total": Decimal("60.00")},
        ]
        self.catalogo = [
            {"id": "i1", "nome": "Kit de tração", "intervalo_km": 5000, "intervalo_minimo_km": 3000,
             "intervalo_dias": None, "ativo": True},
            {"id": "i2", "nome": "Item antigo", "intervalo_km": None, "intervalo_minimo_km": None,
             "intervalo_dias": 90, "ativo": False},
        ]


@pytest.fixture(autouse=True)
def base_manutencao(monkeypatch):
    from src.web import dados_manutencao

    base = BaseManutencao()
    monkeypatch.setattr(dados_manutencao, "motos", SimpleNamespace(listar=lambda: base.motos))
    monkeypatch.setattr(dados_manutencao, "alertas", SimpleNamespace(listar_manutencao=lambda: base.alertas))
    monkeypatch.setattr(dados_manutencao, "manutencao", SimpleNamespace(
        listar_manutencoes=lambda: base.manutencoes,
        listar_catalogo=lambda: base.catalogo,
        obter_manutencao=lambda id_: next((m for m in base.manutencoes if m["id"] == id_), None),
    ))
    return base


class AcoesManutencaoFalsas:
    def __init__(self):
        self.registros = []
        self.finalizacoes = []
        self.itens_criados = []
        self.itens_atualizados = []
        self.falhar_com = None

    def registrar(self, dados, chave):
        if self.falhar_com:
            raise self.falhar_com
        self.registros.append((dados, chave))
        return {"id": "man1"}

    def finalizar(self, manutencao_id, status, data, km):
        if self.falhar_com:
            raise self.falhar_com
        self.finalizacoes.append((manutencao_id, status, data, km))
        return {"manutencao_id": manutencao_id}

    def criar_item(self, dados):
        if self.falhar_com:
            raise self.falhar_com
        self.itens_criados.append(dados)
        return {"id": "i3", **dados}

    def atualizar_item(self, item_id, dados):
        if self.falhar_com:
            raise self.falhar_com
        self.itens_atualizados.append((item_id, dados))
        return {"id": item_id, **dados}


@pytest.fixture(autouse=True)
def acoes_manutencao_falsas(monkeypatch):
    from src.web import acoes_manutencao

    falsas = AcoesManutencaoFalsas()
    monkeypatch.setattr(acoes_manutencao, "registrar", falsas.registrar)
    monkeypatch.setattr(acoes_manutencao, "finalizar", falsas.finalizar)
    monkeypatch.setattr(acoes_manutencao, "criar_item", falsas.criar_item)
    monkeypatch.setattr(acoes_manutencao, "atualizar_item", falsas.atualizar_item)
    return falsas


class AcoesCobrancasFalsas:
    """Registra os pagamentos em vez de falar com o banco; `falhar_com` faz a próxima gravação levantar."""

    def __init__(self):
        self.pagamentos: list[tuple] = []
        self.cancelamentos: list[tuple] = []
        self.falhar_com: Exception | None = None

    def registrar_pagamento(self, cobranca_id, data, principal, extras, forma, observacoes, chave_operacao):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.pagamentos.append((cobranca_id, data, principal, extras, forma, observacoes, chave_operacao))
        return {}

    def cancelar_cobranca(self, cobranca_id, motivo):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.cancelamentos.append((cobranca_id, motivo))
        return {"cobranca_id": cobranca_id, "status": "cancelada"}


@pytest.fixture(autouse=True)
def acoes_cobrancas_falsas(monkeypatch):
    from src.web import acoes_cobrancas

    falsas = AcoesCobrancasFalsas()
    monkeypatch.setattr(acoes_cobrancas, "registrar_pagamento", falsas.registrar_pagamento)
    monkeypatch.setattr(acoes_cobrancas, "cancelar_cobranca", falsas.cancelar_cobranca)
    return falsas


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


CONTRATO_VISTORIAS = "00000000-0000-0000-0000-0000000000d1"
VISTORIA_ENTREGA = "00000000-0000-0000-0000-0000000000f1"
VISTORIA_DEVOLUCAO = "00000000-0000-0000-0000-0000000000f2"


class BaseVistorias:
    def __init__(self):
        self.cliente = {"id": "c1", "nome": "Maria <b>Silva</b>"}
        self.moto = {"id": "m1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG 160", "km_atual": 12000}
        self.vinculada = {"id": "00000000-0000-0000-0000-0000000000b9", "placa": "QRS4T21", "marca": "Yamaha", "modelo": "Factor", "km_atual": 5000}
        self.vinculos = []  # linhas de contrato_motos: motos vinculadas (além da principal) de cada contrato
        self.contrato_sem_vistorias = "00000000-0000-0000-0000-0000000000d3"
        self.contratos = [
            {"id": CONTRATO_VISTORIAS, "cliente_id": "c1", "moto_id": "m1", "data_inicio": "2026-08-01", "data_encerramento": None, "status": "ativo"},
            {"id": "00000000-0000-0000-0000-0000000000d2", "cliente_id": "c1", "moto_id": "m1",
             "data_inicio": "2026-01-01", "data_encerramento": "2026-06-30", "status": "encerrado"},
            {"id": self.contrato_sem_vistorias, "cliente_id": "c1", "moto_id": "m1", "status": "ativo",
             "data_inicio": "2026-09-01", "data_encerramento": None},
        ]
        self.entrega = {"id": VISTORIA_ENTREGA, "moto_id": "m1", "contrato_id": CONTRATO_VISTORIAS, "tipo": "entrega", "data": "2026-08-01", "km": 10500,
                        "nivel_combustivel": "cheio", "avarias": None,
                        "checklist": {"farol_dianteiro": "ok", "freio_dianteiro": "ok", "Rack <i>extra</i>": "ok"},
                        "fotos": [{"storage_path": "v1/a.jpg", "legenda": "Lado <direito>"}, {"storage_path": "v1/quebrada.jpg"}]}
        self.devolucao = {"id": VISTORIA_DEVOLUCAO, "moto_id": "m1", "contrato_id": CONTRATO_VISTORIAS, "tipo": "devolucao", "data": "2026-09-01", "km": 11000,
                          "nivel_combustivel": "1/2", "avarias": None,
                          "checklist": {"farol_dianteiro": "ok", "freio_dianteiro": "avaria", "Rack <i>extra</i>": "ausente"},
                          "fotos": []}
        self.antiga = {"id": "00000000-0000-0000-0000-0000000000f3", "moto_id": "m1", "contrato_id": "00000000-0000-0000-0000-0000000000d2", "tipo": "entrega",
                       "data": "2026-01-01", "km": 8000, "nivel_combustivel": "1/4", "avarias": "Risco no tanque",
                       "checklist": {}, "fotos": []}
        self.registradas = [self.entrega, self.devolucao, self.antiga]


def _url(foto):
    if "quebrada" in foto["storage_path"]:
        raise RuntimeError("falha ao assinar")
    return "https://projeto.supabase.co/assinada/" + foto["storage_path"] + "?token=x"


@pytest.fixture(autouse=True)
def base_vistorias(monkeypatch):
    from src.web import dados_vistorias

    base = BaseVistorias()

    def da_moto(contrato_id, moto_id=None):
        """Vistorias do contrato da moto pedida (por padrão, a principal do contrato)."""
        principal = next((c["moto_id"] for c in base.contratos if c["id"] == contrato_id), None)
        return [v for v in base.registradas if v["contrato_id"] == contrato_id and v["moto_id"] == (moto_id or principal)]

    def comparar(contrato_id, moto_id=None):
        por_tipo = {v["tipo"]: v for v in da_moto(contrato_id, moto_id)}
        return {"entrega": por_tipo.get("entrega"), "devolucao": por_tipo.get("devolucao"), "diferencas": None}

    monkeypatch.setattr(dados_vistorias, "vistorias", SimpleNamespace(
        listar=lambda: base.registradas, comparar_entrega_devolucao=comparar,
        listar_por_contrato=lambda id_, moto_id=None, todas=False: da_moto(id_, moto_id),
        obter=lambda id_: next((v for v in base.registradas if v["id"] == id_), None),
        url_foto=lambda caminho: _url({"storage_path": caminho})))
    monkeypatch.setattr(dados_vistorias, "contratos", SimpleNamespace(
        listar=lambda: base.contratos, listar_vinculos=lambda: base.vinculos))
    monkeypatch.setattr(dados_vistorias, "clientes", SimpleNamespace(
        listar=lambda: [base.cliente], obter=lambda id_: base.cliente if id_ == "c1" else None))
    monkeypatch.setattr(dados_vistorias, "motos", SimpleNamespace(
        listar=lambda: [base.moto, base.vinculada],
        obter=lambda id_: next((m for m in (base.moto, base.vinculada) if m["id"] == id_), None)))
    return base


class BaseDocumentos:
    """Dados fictícios dos serviços usados por src/web/dados_documentos (datas relativas a hoje)."""

    def __init__(self):
        from datetime import timedelta

        from src.domain.valores import hoje_br

        hoje = hoje_br()
        self.moto = {"id": "m1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG 160", "status": "alugada", "km_atual": 12000}
        self.outra = {"id": "m2", "placa": "QRS4T21", "marca": "Yamaha", "modelo": "Factor", "status": "disponivel", "km_atual": 5000}
        self.inativa = {"id": "m3", "placa": "ZZZ9Z99", "marca": "Honda", "modelo": "Pop", "status": "inativa", "km_atual": 1}
        self.alerta_dias = 30

        def doc(id_, moto_id, tipo, dias, **extra):
            return {"id": id_, "moto_id": moto_id, "tipo": tipo, "ano_referencia": 2026, "descricao": None,
                    "vencimento": (hoje + timedelta(days=dias)).isoformat(), "valor": Decimal("150"), "regularizado": False,
                    "arquivo_path": None, "observacoes": None, **extra}

        self.hoje = hoje
        self.documentos = [
            doc("00000000-0000-0000-0000-0000000000e1", "m1", "ipva", -10, descricao="IPVA <b>2026</b>", arquivo_path="m1/e1/a.pdf"),
            doc("00000000-0000-0000-0000-0000000000e2", "m1", "seguro", 10),
            doc("00000000-0000-0000-0000-0000000000e3", "m2", "licenciamento", 200),
            doc("00000000-0000-0000-0000-0000000000e4", "m2", "ipva", -400, regularizado=True, data_regularizacao="2025-01-01"),
            doc("00000000-0000-0000-0000-0000000000e5", "m2", "outro", -3, valor=None),
        ]
        self.url_assinada = "https://projeto.supabase.co/storage/v1/object/sign/documentos/"
        # envio do locatário aguardando conferência do documento e2 (seguro a vencer)
        self.envios = [{"id": "00000000-0000-0000-0000-0000000000b1", "documento_id": "00000000-0000-0000-0000-0000000000e2",
                        "cliente_id": "c1", "arquivo_path": "portal/c1/arq.pdf", "observacao": "Paguei <b>hoje</b>", "status": "enviado",
                        "motivo_recusa": None, "enviado_em": "2026-11-10T15:30:00+00:00", "conferido_em": None,
                        "clientes": {"nome": "Maria Souza"}}]
        self.historico = {}


@pytest.fixture(autouse=True)
def base_documentos(monkeypatch):
    from src.web import dados_documentos

    base = BaseDocumentos()
    frota = [base.moto, base.outra, base.inativa]
    monkeypatch.setattr(dados_documentos, "motos", SimpleNamespace(listar=lambda: frota, obter=lambda id_: next((m for m in frota if m["id"] == id_), None)))
    monkeypatch.setattr(dados_documentos, "configuracoes", SimpleNamespace(obter=lambda: {"alerta_documento_dias": base.alerta_dias}))
    monkeypatch.setattr(dados_documentos, "documentos", SimpleNamespace(
        listar_todos=lambda: base.documentos,
        obter=lambda id_: next((d for d in base.documentos if d["id"] == id_), None),
        url_comprovante=lambda caminho: base.url_assinada + caminho + "?token=x",
        comprovantes_aguardando=lambda: list(base.envios),
        comprovante_aguardando=lambda id_: next((e for e in base.envios if e["documento_id"] == id_ and e["status"] == "enviado"), None),
        historico_de_comprovantes=lambda id_: base.historico.get(id_, [e for e in base.envios if e["documento_id"] == id_])))
    return base


class BaseRelatorios:
    """Dados fictícios do serviço usado por src/web/dados_relatorios."""

    def __init__(self):
        from src.domain.valores import hoje_br

        self.hoje = hoje_br()
        self.consultas = []
        self.resultado = [
            {"moto_id": "m1", "placa": "BRA2E19", "modelo": "CG 160", "receita_recebida": Decimal("1000"),
             "custo_manutencao": Decimal("100"), "custo_documentos": Decimal("50"), "resultado": Decimal("850"),
             "km_rodados": 500, "custo_por_km": Decimal("0.20")},
            {"moto_id": "m2", "placa": "QRS4T21", "modelo": "Factor <i>150</i>", "receita_recebida": Decimal("200"),
             "custo_manutencao": Decimal("300"), "custo_documentos": Decimal("0"), "resultado": Decimal("-100"),
             "km_rodados": 0, "custo_por_km": None},
        ]
        self.fluxo = [
            {"mes": "2026-09", "receita_recebida": Decimal("900"), "custo_manutencao": Decimal("100"),
             "custo_documentos": Decimal("0"), "resultado": Decimal("800")},
            {"mes": self.hoje.isoformat()[:7], "receita_recebida": Decimal("300"), "custo_manutencao": Decimal("300"),
             "custo_documentos": Decimal("50"), "resultado": Decimal("-50")},
        ]
        self.inadimplencia = {
            "linhas": [
                {"cliente": "Maria <b>Silva</b>", "placa": "BRA2E19", "vencimento": "2026-09-01", "dias_atraso": 37,
                 "saldo": Decimal("280"), "total_com_encargos": Decimal("554")},
                {"cliente": "Pedro", "placa": "", "vencimento": "2026-10-01", "dias_atraso": 7,
                 "saldo": Decimal("100"), "total_com_encargos": Decimal("164")},
            ],
            "total_atraso": Decimal("380"), "clientes": 2, "percentual_carteira": Decimal("13.6"),
        }


@pytest.fixture(autouse=True)
def base_relatorios(monkeypatch):
    from src.services import relatorios as servico
    from src.web import dados_relatorios

    base = BaseRelatorios()

    def resultado_por_moto(inicio, fim):
        if fim < inicio:
            raise ValueError("A data final deve ser igual ou posterior à inicial.")
        base.consultas.append((inicio, fim))
        return {"resultado": base.resultado, "fluxo": base.fluxo}

    monkeypatch.setattr(dados_relatorios, "relatorios", SimpleNamespace(
        resultado_por_moto=resultado_por_moto, inadimplencia=lambda hoje: base.inadimplencia,
        exportar_csv=servico.exportar_csv, exportar_excel=servico.exportar_excel))
    return base


class BaseConfiguracoes:
    """Dados fictícios dos serviços usados por src/web/dados_configuracoes e acoes_configuracoes."""

    def __init__(self):
        self.config = {
            "id": 1, "multa_atraso_valor": Decimal("15.00"), "encargo_diario_valor": Decimal("7.00"),
            "multa_troca_oleo_valor": Decimal("0"), "alerta_manutencao_km": 300, "alerta_manutencao_dias": 15,
            "alerta_documento_dias": 30, "alerta_cnh_dias": 30, "dias_inadimplencia": 15,
        }
        self.gravados = []
        self.backups = 0
        self.falhar_com = None


@pytest.fixture(autouse=True)
def base_configuracoes(monkeypatch):
    from src.web import acoes_configuracoes, dados_configuracoes

    base = BaseConfiguracoes()

    def atualizar(dados):
        if base.falhar_com:
            raise base.falhar_com
        base.gravados.append(dados)
        base.config = {**base.config, **dados}
        return base.config

    def backup():
        base.backups += 1
        return b"PK\x03\x04conteudo-do-backup"

    monkeypatch.setattr(dados_configuracoes, "configuracoes", SimpleNamespace(obter=lambda: base.config, backup=backup))
    monkeypatch.setattr(acoes_configuracoes, "configuracoes", SimpleNamespace(atualizar=atualizar))
    return base


DOC_PORTAL_VENCIDO = "00000000-0000-0000-0000-0000000000a1"
DOC_PORTAL_AGUARDANDO = "00000000-0000-0000-0000-0000000000a2"
DOC_PORTAL_RECUSADO = "00000000-0000-0000-0000-0000000000a3"
CONTRATO_PORTAL = "00000000-0000-0000-0000-0000000000f1"
CONTRATO_PORTAL_SEM_PLANO = "00000000-0000-0000-0000-0000000000f2"


class BasePortal:
    """Dados fictícios do portal (RPC rpc_portal_locatario) e das gravações da troca de óleo."""

    def __init__(self):
        self.dados = {
            "cliente_id": "00000000-0000-0000-0000-0000000000c9", "nome": "Ana <b>Souza</b> Lima",
            "alerta_km": 300, "alerta_dias": 15, "multa_valor": Decimal("50"),
            "contratos": [
                {"contrato_id": CONTRATO_PORTAL, "placa": "BRA2E19", "modelo": "CG <i>160</i>", "km_atual": 12000,
                 "ultima_km": 11000, "ultima_data": "2026-09-01", "intervalo_km": 1500, "intervalo_dias": 90,
                 "trocas": [{"criado_em": "2026-09-01T10:00:00+00:00", "km": 11000, "multada": False},
                            {"criado_em": "2026-06-01T10:00:00+00:00", "km": 9400, "multada": True}]},
                {"contrato_id": CONTRATO_PORTAL_SEM_PLANO, "placa": "QRS4T21", "modelo": "Factor", "km_atual": 5000,
                 "ultima_km": None, "ultima_data": None, "intervalo_km": None, "intervalo_dias": None, "trocas": []},
            ],
        }
        self.registros = []
        self.documentos = [
            {"documento_id": DOC_PORTAL_VENCIDO, "placa": "BRA2E19", "modelo": "CG", "tipo": "ipva", "descricao": None, "ano_referencia": 2026,
             "vencimento": "2026-10-05", "situacao": "vencido", "envio_status": None, "envio_em": None, "envio_motivo": None},
            {"documento_id": DOC_PORTAL_AGUARDANDO, "placa": "BRA2E19", "modelo": "CG", "tipo": "seguro", "descricao": None, "ano_referencia": 2026,
             "vencimento": "2026-11-20", "situacao": "a_vencer", "envio_status": "enviado", "envio_em": "2026-11-10T15:30:00+00:00", "envio_motivo": None},
            {"documento_id": DOC_PORTAL_RECUSADO, "placa": "BRA2E19", "modelo": "CG", "tipo": "licenciamento", "descricao": None, "ano_referencia": 2026,
             "vencimento": "2026-12-30", "situacao": "em_dia", "envio_status": "recusado", "envio_em": "2026-11-09T12:00:00+00:00", "envio_motivo": "Foto cortada"},
        ]
        self.comprovantes_enviados = []
        self.erro_nos_documentos = None
        self.trocas_de_senha = []
        self.resultado = {"excedeu": False, "multa_valor": None}
        self.falhar_com = None


@pytest.fixture(autouse=True)
def base_portal(monkeypatch):
    from src.web import acoes_portal, dados_portal

    base = BasePortal()

    def registrar(cliente_id, contrato, km_texto, foto, nota, multa):
        if base.falhar_com:
            raise base.falhar_com
        base.registros.append((cliente_id, contrato["contrato_id"], km_texto, foto, nota, multa))
        return base.resultado

    def documentos():
        if base.erro_nos_documentos:
            raise base.erro_nos_documentos
        return [dict(d) for d in base.documentos]

    def enviar_comprovante(cliente_id, documento_id, nome, conteudo, observacao):
        if base.falhar_com:
            raise base.falhar_com
        base.comprovantes_enviados.append((cliente_id, documento_id, nome, conteudo, observacao))
        return {"id": "e1", "status": "enviado"}

    monkeypatch.setattr(dados_portal, "portal_locatario", SimpleNamespace(dados_portal=lambda: base.dados, documentos_do_locatario=documentos))
    monkeypatch.setattr(acoes_portal, "portal_locatario", SimpleNamespace(
        registrar_troca_oleo=registrar, registrar_troca_senha=lambda: base.trocas_de_senha.append(True),
        enviar_comprovante_documento=enviar_comprovante))
    return base



def _linha_divida(id, credor, tipo="compra_parcelada", saldo="3000.00", situacao="em_aberto", **extra):
    return {
        "divida_id": id, "credor": credor, "tipo": tipo, "tipo_rotulo": {"compra_parcelada": "Compra parcelada",
        "moto_fiado": "Moto fiado", "emprestimo": "Empréstimo"}.get(tipo, tipo), "moto_id": None, "placa": None,
        "valor_original": Decimal("14000.00"), "total_pago": Decimal("11000.00"), "saldo": Decimal(saldo),
        "saldo_confirmado": False, "proxima_vencimento": date(2026, 11, 28), "proxima_valor": Decimal("1000.00"),
        "parcelas_abertas": 3, "parcelas_atrasadas": 0, "situacao": situacao, **extra,
    }


DIVIDA_ID = "00000000-0000-0000-0000-0000000000d1"
PARCELA_ID = "00000000-0000-0000-0000-0000000000e8"
PARCELA_PAGA_ID = "00000000-0000-0000-0000-0000000000e7"
PAGAMENTO_ID = "00000000-0000-0000-0000-0000000000f7"
PAGAMENTO_DIRETO_ID = "00000000-0000-0000-0000-0000000000f8"
CONTA_ID = "00000000-0000-0000-0000-0000000000c1"
MOTO_DIVIDA_ID = "00000000-0000-0000-0000-0000000000a1"
DIVIDA_FIADO_ID = "00000000-0000-0000-0000-0000000000d2"


def ficha_divida_exemplo():
    return {
        "divida": {"id": DIVIDA_ID, "credor": "Celta <b>Zero</b>", "tipo": "compra_parcelada", "descricao": "Compra a prazo",
                   "valor_original": "14000.00", "valor_entrada": "5000.00", "numero_parcelas": 9, "valor_parcela": "1000.00",
                   "dia_vencimento": 28, "confirmado_em": None, "observacoes": "Combinado <i>de boca</i>"},
        "tipo_rotulo": "Compra parcelada", "saldo": Decimal("3000.00"), "total_pago": Decimal("11000.00"),
        "saldo_confirmado": None, "diferenca": None,
        "moto": {"id": "m1", "marca": "Chevrolet", "modelo": "Celta", "placa": "OID7656"},
        "parcelas": [
            {"vencimento_id": "v7", "numero": 7, "vencimento": "2026-10-28", "valor": "1000.00", "valor_pago": "1000.00",
             "saldo": "0.00", "situacao": "paga", "dias_atraso": 0},
            {"vencimento_id": PARCELA_ID, "numero": 8, "vencimento": "2026-11-28", "valor": "1000.00", "valor_pago": "0.00",
             "saldo": "1000.00", "situacao": "a_vencer", "dias_atraso": 0},
            {"vencimento_id": "v9", "numero": 9, "vencimento": "2026-10-01", "valor": "1000.00", "valor_pago": "400.00",
             "saldo": "600.00", "situacao": "atrasada", "dias_atraso": 34},
        ],
        "pagamentos": [
            {"id": "g1", "data": "2026-10-28", "valor": "1000.00", "data_estimada": False, "parcela_numero": 7, "observacoes": None},
            {"id": "g2", "data": "2026-05-01", "valor": "5000.00", "data_estimada": True, "parcela_numero": None,
             "observacoes": "Entrada da compra"},
        ],
    }


def ficha_divida_fiado():
    """Moto fiado: sem parcelas, então o pagamento é direto."""
    return {
        "divida": {"id": DIVIDA_FIADO_ID, "credor": "Nilson", "tipo": "moto_fiado", "descricao": None, "valor_original": "9675.00",
                   "valor_entrada": "0", "numero_parcelas": None, "valor_parcela": None, "dia_vencimento": None,
                   "confirmado_em": None, "observacoes": None},
        "tipo_rotulo": "Moto fiado", "saldo": Decimal("7600.00"), "total_pago": Decimal("2075.00"),
        "saldo_confirmado": None, "diferenca": None, "moto": None, "parcelas": [], "pagamentos": [],
    }


class BaseDividas:
    """Dados fictícios dos serviços usados por src/web/dados_dividas e acoes_dividas."""

    def __init__(self):
        self.linhas = [
            _linha_divida("d1", "Celta <b>Zero</b>", placa="OID7656"),
            _linha_divida("d2", "Nilson", tipo="moto_fiado", saldo="7600.00", situacao="atrasada", parcelas_atrasadas=2,
                          proxima_vencimento=date(2026, 10, 10), saldo_confirmado=True),
            _linha_divida("d3", "Etios", tipo="emprestimo", saldo="0.00", situacao="quitada", proxima_vencimento=None,
                          proxima_valor=None, parcelas_abertas=0),
        ]
        self.totais = {"total_em_aberto": Decimal("10600.00"), "moto_fiado": Decimal("7600.00"), "dividas_em_aberto": 2,
                       "parcelas_atrasadas": 2, "proximo_vencimento": date(2026, 10, 10), "proximo_credor": "Nilson"}
        self.fichas = {DIVIDA_ID: ficha_divida_exemplo()}
        self.parcelas = {PARCELA_ID: {
            "vencimento_id": PARCELA_ID, "divida_id": DIVIDA_ID, "credor": "Celta <b>Zero</b>", "numero": 8,
            "vencimento": "2026-11-28", "valor": "1000.00", "valor_pago": "0.00", "saldo": "1000.00", "situacao": "a_vencer"}}
        self.parcelas["v7"] = {**self.parcelas[PARCELA_ID], "vencimento_id": "00000000-0000-0000-0000-0000000000e7",
                               "numero": 7, "valor_pago": "1000.00", "saldo": "0.00", "situacao": "paga"}
        self.parcelas[PARCELA_PAGA_ID] = self.parcelas.pop("v7")
        self.contas = [{"id": CONTA_ID, "nome": "Quezia <i>Silva</i>"}]
        self.pagamentos = []
        self.motos = [{"id": MOTO_DIVIDA_ID, "placa": "OID7656", "modelo": "Celta <b>LS</b>"}]
        self.compras = []
        self.dividas_criadas = []
        self.pagamentos_diretos = []
        self.edicoes = []
        self.apagadas = []
        self.parcelas_editadas = []
        self.pagamentos_editados = []
        self.registros_pagamento = {
            PAGAMENTO_ID: {"id": PAGAMENTO_ID, "divida_id": DIVIDA_ID, "vencimento_id": "v9", "data": "2026-10-28", "valor": "400.00",
                           "conta_id": CONTA_ID, "observacoes": "pix <b>antigo</b>", "data_estimada": True},
            PAGAMENTO_DIRETO_ID: {"id": PAGAMENTO_DIRETO_ID, "divida_id": DIVIDA_FIADO_ID, "vencimento_id": None, "data": "2026-10-10",
                                  "valor": "300.00", "conta_id": None, "observacoes": None, "data_estimada": False},
        }
        self.saldos = []
        self.fichas[DIVIDA_FIADO_ID] = ficha_divida_fiado()
        self.falhar_com = None


@pytest.fixture(autouse=True)
def base_dividas(monkeypatch):
    from src.web import dados_dividas

    from src.web import acoes_dividas

    base = BaseDividas()

    def pagar_parcela(vencimento_id, data, valor, conta_id, observacoes):
        if base.falhar_com:
            raise base.falhar_com
        base.pagamentos.append((vencimento_id, data, valor, conta_id, observacoes))
        return {"pagamento_id": "novo", "parcela_paga": True, "saldo_da_parcela": 0}

    def criar_compra(**dados):
        if base.falhar_com:
            raise base.falhar_com
        base.compras.append(dados)
        return {"divida_id": DIVIDA_ID, "parcelas": dados["numero_parcelas"], "saldo": 3000}

    monkeypatch.setattr(dados_dividas, "dividas", SimpleNamespace(motos_para_selecao=lambda: base.motos,
        resumo=lambda: {"linhas": base.linhas, "totais": base.totais}, ficha=lambda id: base.fichas.get(id),
        parcela=lambda id: base.parcelas.get(id), contas_ativas=lambda: base.contas,
        pagamento=lambda id: base.registros_pagamento.get(id)))
    def criar_divida(**dados):
        if base.falhar_com:
            raise base.falhar_com
        base.dividas_criadas.append(dados)
        return {"id": DIVIDA_ID, **dados}

    def pagar_divida(divida_id, data, valor, conta_id, observacoes):
        if base.falhar_com:
            raise base.falhar_com
        base.pagamentos_diretos.append((divida_id, data, valor, conta_id, observacoes))
        return {"id": "pg"}

    def atualizar_divida(divida_id, dados):
        if base.falhar_com:
            raise base.falhar_com
        base.edicoes.append((divida_id, dados))
        return {"id": divida_id, **dados}

    def confirmar_saldo(divida_id, saldo, data):
        if base.falhar_com:
            raise base.falhar_com
        base.saldos.append((divida_id, saldo, data))
        return {"id": divida_id}

    def apagar_divida(divida_id):
        if base.falhar_com:
            raise base.falhar_com
        base.apagadas.append(divida_id)

    def atualizar_parcela(vencimento_id, vencimento, valor):
        if base.falhar_com:
            raise base.falhar_com
        base.parcelas_editadas.append((vencimento_id, vencimento, valor))
        return {"id": vencimento_id}

    def atualizar_pagamento(pagamento_id, data, valor, conta_id, observacoes, data_estimada):
        if base.falhar_com:
            raise base.falhar_com
        base.pagamentos_editados.append((pagamento_id, data, valor, conta_id, observacoes, data_estimada))
        return {"id": pagamento_id}

    monkeypatch.setattr(acoes_dividas, "dividas", SimpleNamespace(
        atualizar_parcela=atualizar_parcela, atualizar_pagamento=atualizar_pagamento, apagar_divida=apagar_divida, pagar_parcela=pagar_parcela, criar_compra_parcelada=criar_compra, criar_divida=criar_divida, pagar_divida=pagar_divida,
        atualizar_divida=atualizar_divida, confirmar_saldo=confirmar_saldo))
    return base


CLIENTE_ZAP = "00000000-0000-0000-0000-0000000000c1"
MENSAGEM_FALHOU = "00000000-0000-0000-0000-0000000000e1"
MENSAGEM_PENDENTE = "00000000-0000-0000-0000-0000000000e2"
MENSAGEM_ENVIADA = "00000000-0000-0000-0000-0000000000e3"


class BaseWhatsapp:
    """Dados fictícios do serviço de WhatsApp usado por src/web/dados_whatsapp e acoes_whatsapp."""

    def __init__(self):
        def msg(id, status, **extra):
            base = {"id": id, "cliente_id": CLIENTE_ZAP, "cliente": "Maria Souza", "numero": "5511988887777",
                    "texto": "Olá, Maria! Segue um aviso:\n\n*Pagamento em atraso*", "status": status, "tentativas": 0, "erro": None,
                    "enviar_apos": "2026-11-06T11:00:00+00:00", "criado_em": "2026-11-06T11:00:00+00:00", "tipos": ["atraso"]}
            return {**base, **extra}

        self.mensagens = [
            msg(MENSAGEM_FALHOU, "falhou", tentativas=3, erro="A Evolution recusou o pedido (400)."),
            msg(MENSAGEM_PENDENTE, "pendente", tipos=["cnh_proxima", "oleo_vencida"]),
            msg(MENSAGEM_ENVIADA, "enviada", tentativas=1, criado_em="2026-11-05T11:00:00+00:00"),
        ]
        self.cancelados, self.reenviados, self.bloqueios, self.desbloqueios, self.controles = [], [], [], [], []
        self.falhar_com = None


@pytest.fixture(autouse=True)
def base_whatsapp(monkeypatch):
    from src.web import acoes_whatsapp, dados_whatsapp

    base = BaseWhatsapp()

    def checar():
        if base.falhar_com:
            raise base.falhar_com

    def cancelar(i):
        checar()
        base.cancelados.append(i)

    def reenviar(i):
        checar()
        base.reenviados.append(i)

    def bloquear(i, motivo):
        checar()
        base.bloqueios.append((i, motivo))

    def desbloquear(i):
        checar()
        base.desbloqueios.append(i)

    def controles(dados):
        checar()
        base.controles.append(dados)
        return dados

    servico = SimpleNamespace(
        listar_recentes=lambda *a, **k: list(base.mensagens),
        listar_do_cliente=lambda cliente_id, *a, **k: [m for m in base.mensagens if m["cliente_id"] == cliente_id],
        cancelar=cancelar, reenviar=reenviar, bloquear=bloquear, desbloquear=desbloquear, atualizar_controles=controles,
    )
    monkeypatch.setattr(dados_whatsapp, "whatsapp_painel", servico)
    monkeypatch.setattr(acoes_whatsapp, "whatsapp_painel", servico)
    return base
