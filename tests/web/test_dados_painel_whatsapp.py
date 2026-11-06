"""O Dashboard junta aos alertas de manutenção, documentos e CNH os alertas do envio de WhatsApp."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.domain.painel import ItemAlerta
from src.web import dados_painel


@pytest.fixture(autouse=True)
def dados_painel_falsos():
    """Aqui o que se testa é o `carregar` de verdade: este teste desliga o `carregar` fictício do conftest."""


def _instalar(monkeypatch, config, alertas_zap):
    resumo = {"frota": [], "cobrancas": [], "recebido": Decimal(0), "previsto": Decimal(0), "atrasado": Decimal(0),
              "devedores": [], "manutencao": Decimal(0), "recebido_anterior": Decimal(0), "manutencao_anterior": Decimal(0)}
    financeiro = {"mes_texto": "2026-11", "mes_anterior": "2026-10", "mes_seguinte": None}
    monkeypatch.setattr(dados_painel, "cobrancas", SimpleNamespace(gerar_cobrancas_pendentes=lambda: None))
    monkeypatch.setattr(dados_painel, "dashboard", SimpleNamespace(resumo=lambda: resumo))
    monkeypatch.setattr(dados_painel, "clientes", SimpleNamespace(listar=lambda: []))
    monkeypatch.setattr(dados_painel, "manutencao", SimpleNamespace(listar_manutencoes=lambda: []))
    monkeypatch.setattr(dados_painel, "financeiro_servico", SimpleNamespace(painel_seguro=lambda mes, hoje: financeiro))
    monkeypatch.setattr(dados_painel, "alertas", SimpleNamespace(listar_manutencao=lambda: [], listar_documentos=lambda: [], listar_cnh=lambda: []))
    monkeypatch.setattr(dados_painel, "configuracoes", SimpleNamespace(obter=lambda: config))
    recebidos = []
    monkeypatch.setattr(dados_painel, "whatsapp_painel", SimpleNamespace(alertas=lambda c: recebidos.append(c) or alertas_zap))
    return recebidos


def test_alertas_do_whatsapp_entram_no_cartao_precisa_de_atencao(monkeypatch):
    item = ItemAlerta(2, "Mensagens sem entrega", "Maria: Número de WhatsApp inválido. e mais 1", "atencao", "mensagens")
    config = {"alerta_manutencao_km": 300, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30, "whatsapp_ativo": True}
    recebidos = _instalar(monkeypatch, config, [item])
    dados = dados_painel.carregar(date(2026, 11, 6))
    assert dados["alertas"] == [item]
    assert recebidos == [config]  # recebe a mesma configuração já lida (uma só leitura)


def test_sem_alertas_do_whatsapp_nada_muda(monkeypatch):
    _instalar(monkeypatch, {"alerta_manutencao_km": 300, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30}, [])
    assert dados_painel.carregar(date(2026, 11, 6))["alertas"] == []
