"""Testes das variáveis de ambiente do envio de WhatsApp em src/config.py."""

import pytest

from src import config


def _ambiente(monkeypatch, valores):
    monkeypatch.setattr(config, "_ler", lambda nome: valores.get(nome))


def test_evolution_completa(monkeypatch):
    _ambiente(monkeypatch, {"EVOLUTION_URL": "https://evo.exemplo.com/", "EVOLUTION_APIKEY": " k ", "EVOLUTION_INSTANCIA": "locacao"})
    assert config.get_evolution() == {"url": "https://evo.exemplo.com", "apikey": "k", "instancia": "locacao", "versao": 2}


def test_evolution_versao_1(monkeypatch):
    _ambiente(monkeypatch, {"EVOLUTION_URL": "https://e", "EVOLUTION_APIKEY": "k", "EVOLUTION_INSTANCIA": "i", "EVOLUTION_VERSAO": "1"})
    assert config.get_evolution()["versao"] == 1


def test_evolution_incompleta_diz_o_que_falta(monkeypatch):
    _ambiente(monkeypatch, {"EVOLUTION_URL": "https://e"})
    with pytest.raises(RuntimeError, match="EVOLUTION_APIKEY, EVOLUTION_INSTANCIA"):
        config.get_evolution()


def test_evolution_versao_invalida(monkeypatch):
    _ambiente(monkeypatch, {"EVOLUTION_URL": "https://e", "EVOLUTION_APIKEY": "k", "EVOLUTION_INSTANCIA": "i", "EVOLUTION_VERSAO": "3"})
    with pytest.raises(RuntimeError, match="1 ou 2"):
        config.get_evolution()


def test_usuario_de_servico(monkeypatch):
    _ambiente(monkeypatch, {"SERVICO_MENSAGENS_EMAIL": "robo@exemplo.com", "SERVICO_MENSAGENS_SENHA": "s"})
    assert config.get_servico_mensagens() == ("robo@exemplo.com", "s")
    _ambiente(monkeypatch, {"SERVICO_MENSAGENS_EMAIL": "robo@exemplo.com"})
    with pytest.raises(RuntimeError):
        config.get_servico_mensagens()


def test_textos_usam_la_locadora_quando_nao_ha_empresa_e_nunca_a_razao_social(monkeypatch):
    _ambiente(monkeypatch, {"LOCADOR_NOME": "Razão Social do Contrato Ltda", "WHATSAPP_CONTATO": "variável antiga, ignorada"})
    textos = config.get_textos_whatsapp()
    assert textos == {"empresa": "LA Locadora", "pix": None, "link_portal": None,
                      "comprovante_no_portal": False}
    _ambiente(monkeypatch, {"WHATSAPP_EMPRESA": "LA Locadora", "LOCADOR_NOME": "Outro", "WHATSAPP_PIX": "chave", "PORTAL_URL": "https://p"})
    textos = config.get_textos_whatsapp()
    assert textos["empresa"] == "LA Locadora" and textos["pix"] == "chave" and textos["link_portal"] == "https://p"
    assert textos["comprovante_no_portal"] is True  # com o link do portal, o aviso de documento convida a enviar o comprovante por lá
