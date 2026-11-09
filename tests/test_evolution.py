"""Testes de src/services/evolution.py com transporte falso: nenhum teste chama a Evolution de verdade."""

import json

import httpx
import pytest

from src.services.evolution import (
    ClienteEvolution, ErroEnvio, EvolutionConfiguracaoInvalida, EvolutionIndisponivel, mascarar_numero,
)


def _cliente(manipulador, versao=2):
    return ClienteEvolution("https://evo.exemplo.com", "chave-secreta", "locacao", versao,
                            transporte=httpx.MockTransport(manipulador))


def test_estado_conectado():
    def tratar(req):
        assert req.method == "GET" and req.url.path == "/instance/connectionState/locacao"
        assert req.headers["apikey"] == "chave-secreta"
        return httpx.Response(200, json={"instance": {"instanceName": "locacao", "state": "open"}})
    assert _cliente(tratar).estado() == "open"


def test_estado_desconectado():
    assert _cliente(lambda req: httpx.Response(200, json={"instance": {"state": "close"}})).estado() == "close"


def test_numero_com_e_sem_whatsapp():
    def tratar(req):
        assert req.url.path == "/chat/whatsappNumbers/locacao"
        assert json.loads(req.content) == {"numbers": ["5511988887777"]}
        existe = json.loads(req.content)["numbers"][0].endswith("7777")
        return httpx.Response(200, json=[{"exists": existe, "number": "5511988887777"}])
    cliente = _cliente(tratar)
    assert cliente.numero_tem_whatsapp("5511988887777") is True
    assert _cliente(lambda req: httpx.Response(200, json=[{"exists": False}])).numero_tem_whatsapp("5511988880000") is False
    assert _cliente(lambda req: httpx.Response(200, json=[])).numero_tem_whatsapp("5511988880000") is False


def test_envio_na_versao_2_devolve_o_id():
    capturado = {}

    def tratar(req):
        capturado["path"] = req.url.path
        capturado["corpo"] = json.loads(req.content)
        return httpx.Response(201, json={"key": {"remoteJid": "x@s.whatsapp.net", "fromMe": True, "id": "EVO-123"}})

    assert _cliente(tratar).enviar_texto("5511988887777", "Olá!") == "EVO-123"
    assert capturado["path"] == "/message/sendText/locacao"
    assert capturado["corpo"]["number"] == "5511988887777" and capturado["corpo"]["text"] == "Olá!"


def test_envio_na_versao_1_usa_text_message():
    capturado = {}

    def tratar(req):
        capturado["corpo"] = json.loads(req.content)
        return httpx.Response(201, json={"key": {"id": "EVO-1"}})

    _cliente(tratar, versao=1).enviar_texto("5511988887777", "Olá!")
    assert capturado["corpo"]["textMessage"] == {"text": "Olá!"} and "text" not in capturado["corpo"]


def test_resposta_sem_id_devolve_vazio():
    assert _cliente(lambda req: httpx.Response(201, json={"status": "PENDING"})).enviar_texto("5511988887777", "x") == ""


@pytest.mark.parametrize("status", [408, 429])
def test_pedido_para_ir_mais_devagar_e_indisponibilidade_e_nao_erro_da_mensagem(status):
    """Limite de requisições (429) ou tempo esgotado (408): a mensagem não é culpada, volta para a fila e a rodada para."""
    with pytest.raises(EvolutionIndisponivel, match="tentar depois"):
        _cliente(lambda req: httpx.Response(status, json={"message": "Too Many Requests"})).enviar_texto("5511988887777", "x")
    with pytest.raises(EvolutionIndisponivel):
        _cliente(lambda req: httpx.Response(status)).numero_tem_whatsapp("5511988887777")


@pytest.mark.parametrize("status", [500, 502, 503])
def test_erro_de_servidor_e_indisponibilidade(status):
    with pytest.raises(EvolutionIndisponivel):
        _cliente(lambda req: httpx.Response(status, text="falha")).enviar_texto("5511988887777", "x")


def test_falha_de_rede_e_indisponibilidade_sem_vazar_dados():
    def tratar(req):
        raise httpx.ConnectTimeout("estourou", request=req)
    with pytest.raises(EvolutionIndisponivel) as erro:
        _cliente(tratar).enviar_texto("5511988887777", "texto secreto")
    assert "texto secreto" not in str(erro.value) and "5511988887777" not in str(erro.value)


@pytest.mark.parametrize("status", [401, 403])
def test_chave_recusada_para_tudo(status):
    with pytest.raises(EvolutionConfiguracaoInvalida):
        _cliente(lambda req: httpx.Response(status, json={"message": "Unauthorized"})).estado()


def test_instancia_inexistente_para_tudo():
    with pytest.raises(EvolutionConfiguracaoInvalida):
        _cliente(lambda req: httpx.Response(404, json={"message": "not found"})).estado()


def test_pedido_recusado_e_erro_so_daquela_mensagem():
    with pytest.raises(ErroEnvio):
        _cliente(lambda req: httpx.Response(400, json={"message": "bad"})).enviar_texto("5511988887777", "x")


def test_resposta_que_nao_e_json_e_indisponibilidade():
    with pytest.raises(EvolutionIndisponivel):
        _cliente(lambda req: httpx.Response(200, text="<html>")).estado()


def test_mascara_do_numero():
    assert mascarar_numero("falhou para 5511988887777 agora") == "falhou para 55119****7777 agora"
