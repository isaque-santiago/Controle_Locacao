"""Testes de src/domain/whatsapp_painel.py: filtros da lista de mensagens e alertas do Dashboard."""

from datetime import datetime, timedelta, timezone

from src.domain.whatsapp_painel import (
    alertas_whatsapp, assuntos, clientes_com_problema, contar_por_filtro, filtrar, filtro_valido, pode_cancelar, pode_reenviar,
)

AGORA = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)


def _msg(id, cliente="c1", status="enviada", horas_atras=1, erro=None, numero="5511988887777", nome=None, tipos=("atraso",)):
    return {"id": id, "cliente_id": cliente, "cliente": nome or f"Cliente {cliente}", "numero": numero, "status": status, "erro": erro,
            "criado_em": (AGORA - timedelta(hours=horas_atras)).isoformat(), "tipos": list(tipos)}


def _config(**extra):
    base = {"whatsapp_ativo": True, "whatsapp_modo_teste": False, "whatsapp_ultimo_estado": "open",
            "whatsapp_ultima_rodada_em": (AGORA - timedelta(minutes=10)).isoformat()}
    return {**base, **extra}


def test_filtros():
    todas = [_msg("1", status="falhou"), _msg("2", status="ignorada"), _msg("3", status="pendente"), _msg("4"), _msg("5", status="cancelada")]
    assert [m["id"] for m in filtrar(todas, "problemas")] == ["1", "2"]
    assert [m["id"] for m in filtrar(todas, "pendentes")] == ["3"]
    assert [m["id"] for m in filtrar(todas, "enviadas")] == ["4"]
    assert len(filtrar(todas, "todas")) == 5
    assert contar_por_filtro(todas) == {"problemas": 2, "pendentes": 1, "enviadas": 1, "todas": 5}
    assert filtro_valido("xyz") == "problemas" and filtro_valido("todas") == "todas"


def test_assuntos_em_portugues():
    assert assuntos(_msg("1", tipos=("atraso", "cnh_vencida", "outro"))) == ["Pagamento em atraso", "CNH vencida", "outro"]


def test_acoes_possiveis():
    assert pode_cancelar(_msg("1", status="pendente")) and pode_cancelar(_msg("1", status="falhou"))
    assert not pode_cancelar(_msg("1", status="enviada")) and not pode_cancelar(_msg("1", status="cancelada"))
    assert pode_reenviar(_msg("1", status="falhou"))
    assert not pode_reenviar(_msg("1", status="ignorada", numero=None)) and not pode_reenviar(_msg("1", status="falhou", numero=None))


def test_problema_some_quando_chega_mensagem_posterior_boa():
    msgs = [_msg("1", status="falhou", horas_atras=30), _msg("2", status="enviada", horas_atras=2)]
    assert clientes_com_problema(msgs, AGORA) == []
    msgs = [_msg("1", status="enviada", horas_atras=30), _msg("2", status="falhou", horas_atras=2)]
    assert [m["id"] for m in clientes_com_problema(msgs, AGORA)] == ["2"]


def test_problema_antigo_e_cancelada_nao_contam():
    assert clientes_com_problema([_msg("1", status="falhou", horas_atras=24 * 8)], AGORA) == []
    assert clientes_com_problema([_msg("1", status="falhou", horas_atras=5), _msg("2", status="cancelada", horas_atras=1)], AGORA)[0]["id"] == "1"


def test_um_problema_por_cliente_com_falha_primeiro():
    msgs = [_msg("1", cliente="a", status="ignorada", nome="Ana"), _msg("2", cliente="b", status="falhou", nome="Bia"),
            _msg("3", cliente="b", status="falhou", nome="Bia", horas_atras=3)]
    assert [m["id"] for m in clientes_com_problema(msgs, AGORA)] == ["2", "1"]


def test_sem_o_envio_ligado_nao_ha_alerta():
    assert alertas_whatsapp(_config(whatsapp_ativo=False), [_msg("1", status="falhou")], AGORA) == []
    assert alertas_whatsapp({}, [], AGORA) == []


def test_tudo_em_ordem_nao_alerta():
    assert alertas_whatsapp(_config(), [_msg("1")], AGORA) == []


def test_modo_teste_avisa_que_clientes_nao_recebem():
    itens = alertas_whatsapp(_config(whatsapp_modo_teste=True), [], AGORA)
    assert [(i.titulo, i.area) for i in itens] == [("WhatsApp em modo teste", "configuracoes")]


def test_instancia_desconectada_e_evolution_fora_do_ar():
    desconectada = alertas_whatsapp(_config(whatsapp_ultimo_estado="close"), [], AGORA)
    assert [(i.titulo, i.tom, i.area) for i in desconectada] == [("WhatsApp desconectado", "perigo", "mensagens")]
    fora = alertas_whatsapp(_config(whatsapp_ultimo_estado="indisponivel"), [], AGORA)
    assert fora[0].titulo == "Evolution fora do ar"


def test_rodada_parada_ou_que_nunca_rodou():
    parada = alertas_whatsapp(_config(whatsapp_ultima_rodada_em=(AGORA - timedelta(minutes=95)).isoformat()), [], AGORA)
    assert parada[0].titulo == "Envio automático parado" and "mais de 1h30" in parada[0].descricao
    nunca = alertas_whatsapp(_config(whatsapp_ultima_rodada_em=None), [], AGORA)
    assert nunca[0].titulo == "Envio automático parado" and "ainda não rodou" in nunca[0].descricao
    assert alertas_whatsapp(_config(whatsapp_ultima_rodada_em=(AGORA - timedelta(minutes=89)).isoformat()), [], AGORA) == []


def test_rodada_parada_nao_repete_o_alerta_de_instancia():
    itens = alertas_whatsapp(_config(whatsapp_ultimo_estado="close", whatsapp_ultima_rodada_em=None), [], AGORA)
    assert [i.titulo for i in itens] == ["Envio automático parado"]  # o estado antigo não vale mais


def test_mensagens_sem_entrega_contam_clientes_e_citam_o_motivo():
    msgs = [_msg("1", cliente="a", status="falhou", nome="Ana Souza", erro="A Evolution recusou o pedido (400)."),
            _msg("2", cliente="b", status="ignorada", nome="Bia", erro="Cliente sem WhatsApp cadastrado.")]
    item = alertas_whatsapp(_config(), msgs, AGORA)[0]
    assert item.quantidade == 2 and item.titulo == "Mensagens sem entrega" and item.tom == "perigo" and item.area == "mensagens"
    assert item.descricao == "Ana Souza: A Evolution recusou o pedido (400). e mais 1"


def test_so_ignorada_e_atencao_nao_perigo():
    item = alertas_whatsapp(_config(), [_msg("1", status="ignorada", erro="Número de WhatsApp inválido.")], AGORA)[0]
    assert item.tom == "atencao"


def test_data_com_z_e_aceita():
    msg = _msg("1", status="falhou")
    msg["criado_em"] = (AGORA - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert len(clientes_com_problema([msg], AGORA)) == 1


def test_achatar_mensagem_do_banco():
    from src.domain.whatsapp_painel import achatar

    bruto = {"id": "m1", "cliente_id": "c1", "status": "enviada", "clientes": {"nome": "Maria"},
             "mensagens_whatsapp_itens": [{"tipo": "atraso"}, {"tipo": "cnh_proxima"}]}
    assert achatar(bruto) == {"id": "m1", "cliente_id": "c1", "status": "enviada", "cliente": "Maria", "tipos": ["atraso", "cnh_proxima"]}
    assert achatar({"id": "m2", "clientes": None, "mensagens_whatsapp_itens": None}) == {"id": "m2", "cliente": None, "tipos": []}


def test_estado_da_instancia_em_portugues():
    from src.domain.whatsapp_painel import estado_da_instancia

    assert estado_da_instancia(None) == "ainda sem rodada" and estado_da_instancia("open") == "conectada"
    assert "QR code" in estado_da_instancia("close") and estado_da_instancia("indisponivel") == "Evolution fora do ar"
    assert estado_da_instancia("outro") == "outro"
