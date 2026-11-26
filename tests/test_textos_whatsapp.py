"""Testes de src/domain/textos_whatsapp.py: textos, ordem, agrupamento por cliente e payload da fila."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.domain.avisos_whatsapp import TIPOS
from src.domain.avisos_whatsapp import Aviso
from src.domain.janela_envio import FUSO
from src.domain.textos_whatsapp import ORDEM, OpcoesTexto, montar_mensagem, montar_payload, texto_bloco

DIA = date(2026, 11, 13)
OP = OpcoesTexto(empresa="LA Locadora", link_portal="https://portal.exemplo.com.br")


def _aviso(tipo, ref="ref-1", cliente="cli-1", **dados):
    return Aviso(tipo, cliente, ref, DIA, dados)


def _atraso(dias=3, saldo="450.00", encargos="36.00", total="486.00", **extra):
    return _aviso("atraso", ref="cob-1", vencimento=date(2026, 11, 10), placa="ABC1D23", saldo=Decimal(saldo),
                  tipo_cobranca="locacao", dias_atraso=dias, encargos=Decimal(encargos), total=Decimal(total), **extra)


def test_ordem_cobre_todos_os_tipos():
    assert sorted(ORDEM) == sorted(TIPOS)


# ------------------------------------------------- cobranças e recibos --

GRUPO_OP = OpcoesTexto(empresa="LA Locadora")


def _cobranca(tipo, ref="cob-1", vencimento=date(2026, 11, 13), saldo="350.00", encargos=None, total=None, **extra):
    dados = dict(vencimento=vencimento, placa="ABC1D23", saldo=Decimal(saldo), tipo_cobranca="locacao")
    if encargos is not None:
        dados.update(encargos=Decimal(encargos), total=Decimal(total or saldo) if total else Decimal(saldo) + Decimal(encargos))
    return _aviso(tipo, ref=ref, **{**dados, **extra})


def _recibo(restante="0", ref="pag-1"):
    return _aviso("recibo_pagamento", ref=ref, valor=Decimal("200"), placa="ABC1D23", vencimento=date(2026, 11, 10),
                  saldo_restante=Decimal(restante))


def _texto(*avisos, op=GRUPO_OP, nome="MARIA SOUZA"):
    return montar_mensagem(nome, list(avisos), op)[0]


def test_vespera():
    aviso = _cobranca("lembrete_vespera", vencimento=date(2026, 11, 14), dias_ate_vencer=1)
    assert _texto(aviso) == (
        "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n"
        "Passando pra lembrar que amanhã (14/11/2026) vence a parcela do veículo ABC-1D23.\n\n"
        "💰 *Valor: R$ 350,00*\n\n"
        "Depois de pagar, é só mandar o comprovante aqui no grupo. 😊")


def test_vespera_de_vencimento_na_segunda_diz_o_dia_da_semana():
    aviso = _cobranca("lembrete_vespera", vencimento=date(2026, 11, 16), dias_ate_vencer=2)
    texto = _texto(aviso)
    assert "que segunda-feira (16/11/2026) vence a parcela" in texto and "amanhã" not in texto
    assert "Se já pagou" not in texto


def test_vence_hoje():
    assert _texto(_cobranca("lembrete_vencimento", dias_ate_vencer=0)) == (
        "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n"
        "Passando pra lembrar que a parcela do veículo ABC-1D23 vence hoje (13/11/2026).\n\n"
        "💰 *Valor: R$ 350,00*\n\n"
        "Depois de pagar, é só mandar o comprovante aqui no grupo.\nSe já pagou, pode desconsiderar. 🙏")


def test_atraso_mostra_a_conta_e_o_total():
    aviso = _cobranca("atraso", vencimento=date(2026, 11, 10), encargos="36.00", dias_atraso=3)
    assert _texto(aviso) == (
        "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n"
        "A parcela do veículo ABC-1D23 que venceu em 10/11/2026 está em aberto há 3 dias.\n\n"
        "💰 Parcela: R$ 350,00\n➕ Multa e adicional: R$ 36,00\n✅ *Total hoje: R$ 386,00*\n\n"
        "O valor aumenta a cada dia. Depois de pagar, é só mandar o comprovante aqui no grupo.\n"
        "Se já pagou, pode desconsiderar. 🙏")


def test_atraso_de_um_dia_no_singular_e_sem_encargos_nao_fala_em_aumento():
    texto = _texto(_cobranca("atraso", encargos="0.00", dias_atraso=1))
    assert "há 1 dia." in texto and "*Valor: R$ 350,00*" in texto
    assert "Total hoje" not in texto and "Multa" not in texto and "aumenta" not in texto


def test_inadimplencia_e_seria_e_sem_ameaca():
    aviso = _cobranca("inadimplencia", vencimento=date(2026, 10, 29), encargos="120.00", dias_atraso=15)
    texto = _texto(aviso)
    assert texto.startswith("Olá, Maria. Aqui é da LA Locadora.\n\n⚠️ A parcela do veículo ABC-1D23 que venceu em 29/10/2026")
    assert "há 15 dias, e o contrato passa a constar como inadimplente." in texto
    assert "✅ *Total hoje: R$ 470,00*" in texto
    assert "Precisamos regularizar isso *hoje*. Responda aqui no grupo pra gente resolver." in texto
    assert "bloque" not in texto and "👋" not in texto


def test_atraso_e_inadimplencia_da_mesma_cobranca_aparecem_uma_vez_e_os_dois_sao_marcados():
    base = dict(vencimento=date(2026, 10, 29), encargos="120.00", dias_atraso=15)
    texto, entram, sobram = montar_mensagem("Maria", [_cobranca("atraso", **base), _cobranca("inadimplencia", **base)], GRUPO_OP)
    assert texto.count("29/10/2026") == 1 and texto.count("R$ 470,00") == 1 and "Seguem" not in texto
    assert sorted(a.tipo for a in entram) == ["atraso", "inadimplencia"] and sobram == []


def test_varias_parcelas_uma_linha_cada_com_o_total():
    avisos = [_cobranca("lembrete_vencimento", ref="b", dias_ate_vencer=0),
              _cobranca("atraso", ref="a", vencimento=date(2026, 11, 6), encargos="64.00", dias_atraso=7)]
    assert _texto(*avisos) == (
        "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n"
        "Seguem 2 parcelas do veículo ABC-1D23:\n\n"
        "• *06/11/2026* (7 dias de atraso): R$ 350,00 + R$ 64,00 de multa e adicional\n"
        "• *13/11/2026* (vence hoje): R$ 350,00\n\n"
        "✅ *Total destas parcelas: R$ 764,00*\n\n"
        "O valor aumenta a cada dia de atraso. Depois de pagar, é só mandar o comprovante aqui no grupo.\n"
        "Se já pagou, pode desconsiderar. 🙏")


def test_cobrancas_de_tipos_e_veiculos_diferentes_dizem_qual_e_qual():
    avisos = [_cobranca("lembrete_vencimento", ref="a", dias_ate_vencer=0),
              _cobranca("lembrete_vencimento", ref="b", dias_ate_vencer=0, tipo_cobranca="caucao", placa="XYZ9A88", saldo="100.00")]
    texto = _texto(*avisos)
    assert "Seguem 2 cobranças:" in texto and "*Total destas cobranças: R$ 450,00*" in texto
    assert "· Parcela · ABC-1D23 (vence hoje)" in texto and "· Caução · XYZ-9A88 (vence hoje)" in texto


def test_varias_com_inadimplencia_usa_o_tom_serio_sem_repetir_a_divida():
    antiga = dict(vencimento=date(2026, 10, 29), encargos="120.00", dias_atraso=15)
    avisos = [_cobranca("atraso", ref="a", **antiga), _cobranca("inadimplencia", ref="a", **antiga),
              _cobranca("lembrete_vencimento", ref="b", dias_ate_vencer=0)]
    texto = _texto(*avisos)
    assert texto.startswith("Olá, Maria.") and "⚠️ Seguem 2 parcelas" in texto and "15 dias de atraso, inadimplente" in texto
    assert texto.count("29/10/2026") == 1 and "*Total destas parcelas: R$ 820,00*" in texto
    assert "Precisamos regularizar isso *hoje*" in texto


def test_todas_as_cobrancas_entram_mesmo_acima_do_teto_para_o_total_bater():
    avisos = [_cobranca("lembrete_vencimento", ref=f"c{i}", dias_ate_vencer=0, saldo="10.00") for i in range(7)]
    texto, entram, sobram = montar_mensagem("Maria", avisos, OpcoesTexto(maximo_assuntos=5))
    assert len(entram) == 7 and sobram == [] and texto.count("• ") == 7 and "R$ 70,00" in texto


def test_pix_so_aparece_quando_informado_e_logo_abaixo_do_valor():
    aviso = _cobranca("atraso", encargos="36.00", dias_atraso=3)
    assert "Pix" not in _texto(aviso)
    assert "*Total hoje: R$ 386,00*\n🔑 Pix: chave-exemplo\n\n" in _texto(aviso, op=OpcoesTexto(pix="chave-exemplo"))


def test_recibo_quitado():
    assert _texto(_recibo()) == (
        "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n"
        "Recebemos R$ 200,00 da parcela de 10/11/2026 (ABC-1D23). Está tudo certo. Obrigado! 🙏")


def test_recibo_parcial_vem_antes_da_cobranca():
    texto = _texto(_cobranca("lembrete_vencimento", dias_ate_vencer=0), _recibo(restante="150"))
    assert "Ainda faltam R$ 150,00. Obrigado! 🙏" in texto
    assert texto.index("Recebemos") < texto.index("Passando pra lembrar")


def test_cobranca_nao_pede_para_falar_com_a_empresa():
    texto = _texto(_cobranca("atraso", encargos="36.00", dias_atraso=3), op=OP)
    assert "Dúvidas?" not in texto and "Fale com" not in texto


# ------------------------------------------------------- outros avisos --


PORTAL = "https://portal.exemplo.com.br/portal"
COM_PORTAL = OpcoesTexto(empresa="LA Locadora", link_portal=PORTAL, comprovante_no_portal=True)


def _documento(tipo="documento_vencido", tipo_documento="ipva", vencimento=date(2026, 11, 5), dias=-8, descricao=None, ref="doc-1"):
    return _aviso(tipo, ref=ref, placa="ABC1D23", tipo_documento=tipo_documento, descricao=descricao, vencimento=vencimento, dias=dias)


@pytest.mark.parametrize("tipo, nome, instrucao", [
    ("ipva", "O IPVA", "Providencie o pagamento da guia"),
    ("licenciamento", "O licenciamento", "Providencie o pagamento da guia"),
    ("seguro", "O seguro", "Providencie a renovação do seguro"),
    ("vistoria_detran", "A vistoria do Detran", "Agende e faça a vistoria"),
])
def test_documento_cita_o_tipo_o_prazo_e_o_que_fazer(tipo, nome, instrucao):
    assert texto_bloco(_documento(tipo_documento=tipo), COM_PORTAL) == (
        f"⚠️ {nome} do veículo ABC-1D23 venceu em 05/11/2026 (há 8 dias).\n"
        f"{instrucao} e envie o comprovante pelo portal: {PORTAL}\n"
        "Se esse custo não for seu, é só avisar aqui no grupo.")


def test_documento_perto_de_vencer_sem_portal_pede_o_comprovante_no_grupo():
    texto = texto_bloco(_documento("documento_proximo", vencimento=date(2026, 11, 20), dias=7))
    assert texto.startswith("📄 O IPVA do veículo ABC-1D23 vence em 20/11/2026 (daqui a 7 dias).")
    assert "envie o comprovante aqui no grupo." in texto and "portal" not in texto


def test_documento_que_vence_hoje():
    assert "(hoje)" in texto_bloco(_documento("documento_proximo", vencimento=DIA, dias=0))


def test_documento_outro_usa_a_descricao():
    texto = texto_bloco(_documento(tipo_documento="outro", descricao="Taxa do rastreador", dias=-1))
    assert "O documento (Taxa do rastreador) do veículo ABC-1D23 venceu" in texto and "há 1 dia)" in texto
    assert "Providencie a regularização" in texto


def test_oleo_proxima_e_vencida_levam_o_link_do_portal():
    proxima = texto_bloco(_aviso("oleo_proxima", ref="m1", placa="ABC1D23", km_restantes=300, dias_restantes=None), COM_PORTAL)
    vencida = texto_bloco(_aviso("oleo_vencida", ref="m1", placa="ABC1D23", km_restantes=-50, dias_restantes=-4), COM_PORTAL)
    assert proxima == ("🛢️ O veículo ABC-1D23 está perto da troca de óleo (faltam 300 km).\n"
                       f"Quando trocar, registre pelo portal com a foto do painel e a da nota fiscal: {PORTAL}")
    assert vencida == ("⚠️ A troca de óleo do veículo ABC-1D23 está atrasada (passou 50 km e 4 dias). "
                       "Trocas fora do intervalo podem gerar multa.\n"
                       f"Faça a troca e registre pelo portal com a foto do painel e a da nota fiscal: {PORTAL}")


def test_oleo_sem_link_termina_a_frase():
    texto = texto_bloco(_aviso("oleo_proxima", ref="m1", placa="ABC1D23", km_restantes=300, dias_restantes=5))
    assert "(faltam 300 km ou 5 dias)" in texto and texto.endswith("a da nota fiscal.")


def test_cnh_proxima_e_vencida():
    prox = texto_bloco(_aviso("cnh_proxima", ref="c", validade=date(2026, 11, 30), dias=17))
    venc = texto_bloco(_aviso("cnh_vencida", ref="c", validade=date(2026, 11, 1), dias=-12))
    assert prox == "🪪 Sua CNH vence em 30/11/2026 (daqui a 17 dias).\nDepois de renovar, manda a nova aqui no grupo."
    assert venc == ("⚠️ Sua CNH venceu em 01/11/2026 (há 12 dias). Não é permitido conduzir com a CNH vencida.\n"
                    "Assim que renovar, manda a nova aqui no grupo.")


def test_portal_nunca_leva_senha():
    acesso = texto_bloco(_aviso("portal_acesso", ref="e1"), COM_PORTAL)
    troca = texto_bloco(_aviso("portal_senha_alterada", ref="e2"), COM_PORTAL)
    assert acesso == ("🔐 Seu acesso ao portal foi criado!\n"
                      f"Entre em {PORTAL} com seu e-mail de acesso e a senha que a empresa te passou.")
    assert troca == "🔐 A senha do seu acesso ao portal foi alterada.\nSe não foi você, avise aqui no grupo agora."


# ------------------------------------------------------------- mensagem --


def _cnh(ref="c"):
    return _aviso("cnh_proxima", ref=ref, validade=date(2026, 11, 30), dias=17)


def test_aviso_sozinho_tem_saudacao_leve_e_o_paragrafo():
    texto, entram, sobram = montar_mensagem("maria da silva", [_cnh()], OP)
    assert texto == "Oi, Maria! 👋 Aqui é da LA Locadora.\n\n" + texto_bloco(_cnh(), OP)
    assert len(entram) == 1 and sobram == []


def test_cobranca_vem_antes_dos_outros_avisos_com_uma_saudacao_so():
    texto, entram, _ = montar_mensagem("Maria", [_cnh(), _atraso()], OP)
    assert texto.index("venceu em 10/11/2026") < texto.index("🪪 Sua CNH")
    assert texto.count("Oi, Maria!") == 1 and "Seguem" not in texto and "*1." not in texto
    assert [a.tipo for a in entram] == ["atraso", "cnh_proxima"]


def test_passando_do_teto_o_resto_dos_outros_avisos_fica_de_fora():
    avisos = [_atraso()] + [_cnh(f"c{i}") for i in range(6)]
    texto, entram, sobram = montar_mensagem("Maria", avisos, OpcoesTexto(maximo_assuntos=5))
    assert len(entram) == 5 and len(sobram) == 2
    assert entram[0].tipo == "atraso"
    assert texto.endswith("Tem mais 2 avisos, que vão em outra mensagem.")
    um = montar_mensagem("Maria", avisos[:6], OpcoesTexto(maximo_assuntos=5))[0]
    assert um.endswith("Tem mais 1 aviso, que vai em outra mensagem.")


def test_sem_empresa_a_saudacao_fica_so_com_o_nome():
    assert montar_mensagem("Maria", [_cnh()])[0].startswith("Oi, Maria! 👋\n\n🪪")


def test_mensagem_sem_avisos_e_erro():
    with pytest.raises(ValueError):
        montar_mensagem("Maria", [])


# -------------------------------------------------------------- payload --


MOMENTO = datetime(2026, 11, 13, 9, 0, tzinfo=FUSO)


def test_payload_uma_mensagem_por_cliente_com_o_grupo_como_destino():
    clientes = {"cli-1": {"nome": "Maria Souza", "whatsapp": "(11) 98888-7777", "grupo": "120363025246125486@g.us"},
                "cli-2": {"nome": "João Lima", "whatsapp": "(11) 98888-7777", "grupo": None}}
    avisos = [_atraso(), _aviso("cnh_proxima", ref="c", validade=date(2026, 11, 30), dias=17),
              _aviso("portal_acesso", ref="e1", cliente="cli-2")]
    payload = montar_payload(clientes, avisos, MOMENTO, OP)
    assert len(payload) == 2
    um, dois = payload
    assert um["cliente_id"] == "cli-1" and um["numero"] == "120363025246125486@g.us"
    assert um["enviar_apos"] == "2026-11-13T09:00:00-03:00"
    assert [(i["tipo"], i["referencia_id"], i["data_referencia"]) for i in um["itens"]] == [
        ("atraso", "cob-1", "2026-11-13"), ("cnh_proxima", "c", "2026-11-13")]
    assert dois["numero"] is None  # sem grupo (mesmo com número individual): a RPC grava como ignorada


def test_payload_so_leva_os_itens_que_entraram_na_mensagem():
    clientes = {"cli-1": {"nome": "Maria", "grupo": "120363025246125486@g.us"}}
    avisos = [_aviso("cnh_proxima", ref=f"c{i}", validade=date(2026, 11, 30), dias=17) for i in range(7)]
    payload = montar_payload(clientes, avisos, MOMENTO, OpcoesTexto(maximo_assuntos=5))
    assert len(payload[0]["itens"]) == 5


def test_payload_cliente_desconhecido_e_erro():
    with pytest.raises(ValueError):
        montar_payload({}, [_atraso()], MOMENTO, OP)
