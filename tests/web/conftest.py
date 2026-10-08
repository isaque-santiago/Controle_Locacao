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
        self.manutencoes = [
            {"data_entrada": "2026-09-10", "tipo": "preventiva", "descricao": "Óleo <i>e filtro</i>", "km": 11000,
             "cobrar_do_cliente": True, "custo_total": Decimal("85")},
            {"data_entrada": "2026-05-10", "tipo": "corretiva", "descricao": "Antes do contrato", "km": 9000,
             "cobrar_do_cliente": False, "custo_total": Decimal("50")},
        ]


@pytest.fixture(autouse=True)
def base_contratos(monkeypatch):
    from src.web import dados_contratos

    base = BaseContratos()
    from src.services.contratos import previa_agenda

    pessoas = [base.cliente, base.cliente_bloqueado]
    frota = [base.moto, base.moto_livre]
    monkeypatch.setattr(dados_contratos, "contratos", SimpleNamespace(listar=lambda: base.contratos, previa_agenda=previa_agenda))
    monkeypatch.setattr(dados_contratos, "clientes", SimpleNamespace(
        listar=lambda: pessoas, obter=lambda id_: next((c for c in pessoas if c["id"] == id_), None)))
    monkeypatch.setattr(dados_contratos, "motos", SimpleNamespace(
        listar=lambda: frota, obter=lambda id_: next((m for m in frota if m["id"] == id_), None)))
    monkeypatch.setattr(dados_contratos, "cobrancas", SimpleNamespace(
        listar_por_contrato=lambda id_: base.cobrancas,
        historicos_pagamentos=lambda ids: {i: base.pagamentos.get(i, []) for i in ids}))
    monkeypatch.setattr(dados_contratos, "vistorias", SimpleNamespace(listar_por_contrato=lambda id_: base.vistorias))
    monkeypatch.setattr(dados_contratos, "manutencao", SimpleNamespace(listar_manutencoes=lambda id_: base.manutencoes))
    return base


class AcoesContratosFalsas:
    """Registra a criação em vez de falar com o banco; `falhar_com` faz a próxima gravação levantar."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.encerramentos: list[tuple] = []
        self.falhar_com: Exception | None = None

    def criar_contrato_com_vistoria(self, dados, vistoria):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.chamadas.append((dados, vistoria))
        return {"contrato_id": "00000000-0000-0000-0000-0000000000e1"}

    def encerrar_contrato_com_vistoria(self, contrato_id, data, vistoria, valor_danos, descricao_danos):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.encerramentos.append((contrato_id, data, vistoria, valor_danos, descricao_danos))
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

    from src.web.rotas import cobrancas_mensagem, cobrancas_pagamento

    base = BaseCobrancas()
    # "Hoje" é 07/10/2026 em todo o fluxo de Cobranças (lista, mensagem e pagamento): as rotas importam o próprio
    # `hoje_br`, então o relógio congelado precisa valer em cada módulo, e não só na camada de dados.
    for modulo in (dados_cobrancas, cobrancas_mensagem, cobrancas_pagamento):
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
        self.falhar_com: Exception | None = None

    def registrar_pagamento(self, cobranca_id, data, principal, extras, forma, observacoes, chave_operacao):
        if self.falhar_com is not None:
            raise self.falhar_com
        self.pagamentos.append((cobranca_id, data, principal, extras, forma, observacoes, chave_operacao))
        return {}


@pytest.fixture(autouse=True)
def acoes_cobrancas_falsas(monkeypatch):
    from src.web import acoes_cobrancas

    falsas = AcoesCobrancasFalsas()
    monkeypatch.setattr(acoes_cobrancas, "registrar_pagamento", falsas.registrar_pagamento)
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


class BaseVistorias:
    def __init__(self):
        self.cliente = {"id": "c1", "nome": "Maria <b>Silva</b>"}
        self.moto = {"id": "m1", "placa": "BRA2E19", "marca": "Honda", "modelo": "CG 160", "km_atual": 12000}
        self.contrato_sem_vistorias = "00000000-0000-0000-0000-0000000000d3"
        self.contratos = [
            {"id": CONTRATO_VISTORIAS, "cliente_id": "c1", "moto_id": "m1", "data_inicio": "2026-08-01", "data_encerramento": None, "status": "ativo"},
            {"id": "00000000-0000-0000-0000-0000000000d2", "cliente_id": "c1", "moto_id": "m1",
             "data_inicio": "2026-01-01", "data_encerramento": "2026-06-30", "status": "encerrado"},
            {"id": self.contrato_sem_vistorias, "cliente_id": "c1", "moto_id": "m1", "status": "ativo",
             "data_inicio": "2026-09-01", "data_encerramento": None},
        ]
        self.entrega = {"id": "v1", "contrato_id": CONTRATO_VISTORIAS, "tipo": "entrega", "data": "2026-08-01", "km": 10500,
                        "nivel_combustivel": "cheio", "avarias": None,
                        "checklist": {"farol_dianteiro": "ok", "freio_dianteiro": "ok", "Rack <i>extra</i>": "ok"},
                        "fotos": [{"storage_path": "v1/a.jpg", "legenda": "Lado <direito>"}, {"storage_path": "v1/quebrada.jpg"}]}
        self.devolucao = {"id": "v2", "contrato_id": CONTRATO_VISTORIAS, "tipo": "devolucao", "data": "2026-09-01", "km": 11000,
                          "nivel_combustivel": "1/2", "avarias": None,
                          "checklist": {"farol_dianteiro": "ok", "freio_dianteiro": "avaria", "Rack <i>extra</i>": "ausente"},
                          "fotos": []}
        self.antiga = {"id": "v3", "contrato_id": "00000000-0000-0000-0000-0000000000d2", "tipo": "entrega",
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

    def comparar(contrato_id):
        por_tipo = {v["tipo"]: v for v in base.registradas if v["contrato_id"] == contrato_id}
        return {"entrega": por_tipo.get("entrega"), "devolucao": por_tipo.get("devolucao"), "diferencas": None}

    monkeypatch.setattr(dados_vistorias, "vistorias", SimpleNamespace(
        listar=lambda: base.registradas, comparar_entrega_devolucao=comparar,
        listar_por_contrato=lambda id_: [v for v in base.registradas if v["contrato_id"] == id_],
        url_foto=lambda caminho: _url({"storage_path": caminho})))
    monkeypatch.setattr(dados_vistorias, "contratos", SimpleNamespace(listar=lambda: base.contratos))
    monkeypatch.setattr(dados_vistorias, "clientes", SimpleNamespace(
        listar=lambda: [base.cliente], obter=lambda id_: base.cliente if id_ == "c1" else None))
    monkeypatch.setattr(dados_vistorias, "motos", SimpleNamespace(
        listar=lambda: [base.moto], obter=lambda id_: base.moto if id_ == "m1" else None))
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
        url_comprovante=lambda caminho: base.url_assinada + caminho + "?token=x"))
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
            "alerta_documento_dias": 30, "alerta_cnh_dias": 30,
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

    monkeypatch.setattr(dados_portal, "portal_locatario", SimpleNamespace(dados_portal=lambda: base.dados))
    monkeypatch.setattr(acoes_portal, "portal_locatario", SimpleNamespace(registrar_troca_oleo=registrar))
    return base

