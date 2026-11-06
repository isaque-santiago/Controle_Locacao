"""Testes de src/domain/textos_whatsapp.py: textos, ordem, agrupamento por cliente e payload da fila."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.domain.avisos_whatsapp import TIPOS
from src.domain.avisos_whatsapp import Aviso
from src.domain.janela_envio import FUSO
from src.domain.textos_whatsapp import ORDEM, OpcoesTexto, montar_mensagem, montar_payload, texto_bloco

DIA = date(2026, 11, 13)
OP = OpcoesTexto(empresa="LA Motos", contato="o Alisson, no (11) 99999-0000", link_portal="https://portal.exemplo.com.br")


def _aviso(tipo, ref="ref-1", cliente="cli-1", **dados):
    return Aviso(tipo, cliente, ref, DIA, dados)


def _atraso(dias=3, saldo="450.00", encargos="36.00", total="486.00", **extra):
    return _aviso("atraso", ref="cob-1", vencimento=date(2026, 11, 10), placa="ABC1D23", saldo=Decimal(saldo),
                  tipo_cobranca="locacao", dias_atraso=dias, encargos=Decimal(encargos), total=Decimal(total), **extra)


def test_ordem_cobre_todos_os_tipos():
    assert sorted(ORDEM) == sorted(TIPOS)


def test_atraso_mostra_valor_encargos_e_total():
    titulo, linhas = texto_bloco(_atraso(), OP)
    texto = "\n".join(linhas)
    assert titulo == "Pagamento em atraso"
    assert "ABC-1D23" in texto and "10/11/2026" in texto and "há 3 dias" in texto
    assert "Valor: R$ 450,00" in texto
    assert "Multa e adicional por atraso: R$ 36,00" in texto
    assert "*Total hoje: R$ 486,00*" in texto


def test_atraso_de_um_dia_no_singular_e_sem_encargos_nao_mostra_total():
    _, linhas = texto_bloco(_atraso(dias=1, encargos="0.00", total="450.00"), OP)
    texto = "\n".join(linhas)
    assert "há 1 dia." in texto and "Total hoje" not in texto and "Multa" not in texto


def test_pix_so_aparece_quando_informado():
    sem = "\n".join(texto_bloco(_atraso(), OP)[1])
    com = "\n".join(texto_bloco(_atraso(), OpcoesTexto(pix="chave-pix-exemplo"))[1])
    assert "Pix" not in sem
    assert "Pix para pagar: chave-pix-exemplo" in com


def test_lembretes_dizem_quando_vence():
    base = dict(vencimento=date(2026, 11, 13), placa="ABC1D23", saldo=Decimal("450"), tipo_cobranca="locacao")
    hoje = "\n".join(texto_bloco(_aviso("lembrete_vencimento", dias_ate_vencer=0, **base), OP)[1])
    amanha = "\n".join(texto_bloco(_aviso("lembrete_vespera", dias_ate_vencer=1, **base), OP)[1])
    segunda = "\n".join(texto_bloco(_aviso("lembrete_vespera", dias_ate_vencer=2, **dict(base, vencimento=date(2026, 11, 16))), OP)[1])
    assert "vence hoje" in hoje
    assert "vence amanhã (13/11/2026)" in amanha
    assert "vence segunda-feira (16/11/2026)" in segunda
    assert "R$ 450,00" in hoje


def test_recibo_quitado_e_parcial():
    base = dict(valor=Decimal("200"), placa="ABC1D23", vencimento=date(2026, 11, 10))
    quitado = "\n".join(texto_bloco(_aviso("recibo_pagamento", saldo_restante=Decimal("0"), **base), OP)[1])
    parcial = "\n".join(texto_bloco(_aviso("recibo_pagamento", saldo_restante=Decimal("250"), **base), OP)[1])
    assert "Recebemos R$ 200,00" in quitado and "Obrigado" in quitado
    assert "Ainda falta R$ 250,00" in parcial


def test_inadimplencia_chama_o_dono():
    _, linhas = texto_bloco(_aviso("inadimplencia", vencimento=date(2026, 10, 25), placa="ABC1D23", saldo=Decimal("450"),
                                   tipo_cobranca="locacao", dias_atraso=19, encargos=Decimal("148"), total=Decimal("598")), OP)
    texto = "\n".join(linhas)
    assert "inadimplente" in texto and "há 19 dias" in texto and "o Alisson" in texto


@pytest.mark.parametrize("tipo, esperado", [
    ("ipva", "IPVA"), ("licenciamento", "Licenciamento"), ("seguro", "Seguro"), ("vistoria_detran", "Vistoria do Detran"),
])
def test_documento_cita_o_tipo_o_prazo_e_o_comprovante(tipo, esperado):
    aviso = _aviso("documento_vencido", ref="doc-1", placa="ABC1D23", tipo_documento=tipo, descricao=None,
                   vencimento=date(2026, 11, 5), dias=-8)
    _, linhas = texto_bloco(aviso, OP)
    texto = "\n".join(linhas)
    assert esperado in texto and "venceu em 05/11/2026 (há 8 dias)" in texto
    assert "Se o custo for do proprietário, combine com o Alisson" in texto
    assert "envie o comprovante para o Alisson" in texto
    assert "portal" not in texto  # o envio pelo portal ainda não existe


def test_documento_cita_o_portal_so_quando_habilitado():
    aviso = _aviso("documento_proximo", ref="doc-1", placa="ABC1D23", tipo_documento="ipva", descricao=None,
                   vencimento=date(2026, 11, 20), dias=7)
    texto = "\n".join(texto_bloco(aviso, OpcoesTexto(contato="o Alisson", link_portal="https://p.exemplo", comprovante_no_portal=True))[1])
    assert "vence em 20/11/2026 (7 dias)" in texto
    assert "pelo portal (https://p.exemplo) ou para o Alisson" in texto


def test_documento_outro_usa_a_descricao():
    aviso = _aviso("documento_vencido", ref="doc-1", placa="ABC1D23", tipo_documento="outro", descricao="Taxa do rastreador",
                   vencimento=date(2026, 11, 5), dias=-1)
    assert "Taxa do rastreador da moto ABC-1D23 venceu" in "\n".join(texto_bloco(aviso, OP)[1])


def test_oleo_proxima_e_vencida_levam_o_link_do_portal():
    proxima = "\n".join(texto_bloco(_aviso("oleo_proxima", ref="m1", placa="ABC1D23", km_restantes=300, dias_restantes=None), OP)[1])
    vencida = "\n".join(texto_bloco(_aviso("oleo_vencida", ref="m1", placa="ABC1D23", km_restantes=-50, dias_restantes=-4), OP)[1])
    assert "faltam 300 km" in proxima and "https://portal.exemplo.com.br" in proxima
    assert "passou do prazo (passou 50 km e 4 dias)" in vencida and "multa" in vencida


def test_cnh_proxima_e_vencida():
    prox = "\n".join(texto_bloco(_aviso("cnh_proxima", ref="c", validade=date(2026, 11, 30), dias=17), OP)[1])
    venc = "\n".join(texto_bloco(_aviso("cnh_vencida", ref="c", validade=date(2026, 11, 1), dias=-12), OP)[1])
    assert "vence em 30/11/2026 (17 dias)" in prox
    assert "venceu em 01/11/2026 (há 12 dias)" in venc and "Não é permitido conduzir" in venc


def test_portal_nunca_leva_senha():
    acesso = "\n".join(texto_bloco(_aviso("portal_acesso", ref="e1"), OP)[1])
    troca = "\n".join(texto_bloco(_aviso("portal_senha_alterada", ref="e2"), OP)[1])
    assert "https://portal.exemplo.com.br" in acesso and "senha informada pela empresa" in acesso
    assert "foi alterada" in troca and "avise o Alisson" in troca


# ------------------------------------------------------------- mensagem --


def test_mensagem_de_um_assunto():
    texto, entram, sobram = montar_mensagem("maria da silva", [_atraso()], OP)
    assert texto.startswith("Olá, Maria! Aqui é da LA Motos. Segue um aviso:")
    assert "*Pagamento em atraso*" in texto and "1." not in texto.split("\n\n")[1].split("\n")[0]
    assert texto.endswith("Dúvidas? Fale com o Alisson, no (11) 99999-0000.")
    assert len(entram) == 1 and sobram == []


def test_dois_assuntos_no_mesmo_dia_vao_numerados_e_o_mais_urgente_vem_primeiro():
    cnh = _aviso("cnh_proxima", ref="c", validade=date(2026, 11, 30), dias=17)
    texto, entram, _ = montar_mensagem("Maria", [cnh, _atraso()], OP)
    assert "Seguem 2 avisos:" in texto
    assert texto.index("*1. Pagamento em atraso*") < texto.index("*2. CNH perto de vencer*")
    assert [a.tipo for a in entram] == ["atraso", "cnh_proxima"]


def test_passando_do_teto_os_mais_urgentes_entram_e_o_resto_fica_de_fora():
    avisos = [_atraso()] + [_aviso("cnh_proxima", ref=f"c{i}", validade=date(2026, 11, 30), dias=17) for i in range(6)]
    texto, entram, sobram = montar_mensagem("Maria", avisos, OpcoesTexto(contato="o Alisson", maximo_assuntos=5))
    assert len(entram) == 5 and len(sobram) == 2
    assert entram[0].tipo == "atraso"
    assert "Há mais 2 assuntos pendente(s). Fale com o Alisson para ver tudo." in texto
    assert "Dúvidas?" not in texto


def test_sem_empresa_nem_contato_usa_padroes():
    texto, _, _ = montar_mensagem("Maria", [_atraso()])
    assert texto.startswith("Olá, Maria! Segue um aviso:")
    assert "Fale com a empresa." in texto


def test_mensagem_sem_avisos_e_erro():
    with pytest.raises(ValueError):
        montar_mensagem("Maria", [])


# -------------------------------------------------------------- payload --


MOMENTO = datetime(2026, 11, 13, 9, 0, tzinfo=FUSO)


def test_payload_uma_mensagem_por_cliente_com_numero_normalizado():
    clientes = {"cli-1": {"nome": "Maria Souza", "whatsapp": "(11) 98888-7777"},
                "cli-2": {"nome": "João Lima", "whatsapp": None}}
    avisos = [_atraso(), _aviso("cnh_proxima", ref="c", validade=date(2026, 11, 30), dias=17),
              _aviso("portal_acesso", ref="e1", cliente="cli-2")]
    payload = montar_payload(clientes, avisos, MOMENTO, OP)
    assert len(payload) == 2
    um, dois = payload
    assert um["cliente_id"] == "cli-1" and um["numero"] == "5511988887777"
    assert um["enviar_apos"] == "2026-11-13T09:00:00-03:00"
    assert [(i["tipo"], i["referencia_id"], i["data_referencia"]) for i in um["itens"]] == [
        ("atraso", "cob-1", "2026-11-13"), ("cnh_proxima", "c", "2026-11-13")]
    assert dois["numero"] is None  # sem WhatsApp: a RPC grava como ignorada


def test_payload_so_leva_os_itens_que_entraram_na_mensagem():
    clientes = {"cli-1": {"nome": "Maria", "whatsapp": "11988887777"}}
    avisos = [_aviso("cnh_proxima", ref=f"c{i}", validade=date(2026, 11, 30), dias=17) for i in range(7)]
    payload = montar_payload(clientes, avisos, MOMENTO, OpcoesTexto(maximo_assuntos=5))
    assert len(payload[0]["itens"]) == 5


def test_payload_cliente_desconhecido_e_erro():
    with pytest.raises(ValueError):
        montar_payload({}, [_atraso()], MOMENTO, OP)
