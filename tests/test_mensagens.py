"""Mensagens de confirmação (Etapa 7): dizem o que mudou e escolhem toast ou alerta."""

from decimal import Decimal

import pytest

from src.domain import mensagens
from src.domain.configuracoes import campos_alterados
from src.domain.mensagens import ALERTA, TOAST


def test_moeda_no_padrao_brasileiro():
    assert mensagens.moeda(Decimal("450")) == "R$ 450,00"
    assert mensagens.moeda("1234.5") == "R$ 1.234,50"


def test_pagamento_descreve_valor_encargos_e_situacao_da_cobranca():
    quitado = mensagens.pagamento_registrado(Decimal("450.00"), Decimal("0"), quitada=True)
    assert quitado == ("Pagamento de R$ 450,00 registrado. Cobrança quitada.", TOAST, False)
    parcial = mensagens.pagamento_registrado(Decimal("100"), Decimal("12.5"), quitada=False)
    assert "R$ 100,00" in parcial.texto and "R$ 12,50" in parcial.texto
    assert "continua em aberto" in parcial.texto


def test_cadastro_e_edicao_tem_textos_distintos_e_citam_o_registro():
    assert mensagens.moto_salva("ABC-1D23", nova=True).texto == "Moto ABC-1D23 cadastrada."
    assert mensagens.moto_salva("ABC-1D23", nova=False).texto == "Dados da moto ABC-1D23 atualizados."
    assert mensagens.cliente_salvo("Maria", novo=True).texto == "Cliente Maria cadastrado."
    assert mensagens.cliente_salvo("Maria", novo=False).texto == "Dados de Maria atualizados."


def test_nenhuma_mensagem_usa_o_texto_generico():
    avisos = [
        mensagens.moto_salva("ABC-1D23", True),
        mensagens.moto_status_alterado("ABC-1D23", True),
        mensagens.km_atualizado("ABC-1D23", 12345),
        mensagens.cliente_salvo("Maria", False),
        mensagens.contrato_encerrado("Maria", "ABC-1D23"),
        mensagens.manutencao_registrada("ABC-1D23", True, Decimal("300")),
        mensagens.manutencao_finalizada("ABC-1D23", False),
        mensagens.configuracoes_salvas([]),
    ]
    assert all("Alterações salvas" not in aviso.texto for aviso in avisos)


def test_quilometragem_e_custo_formatados():
    assert "12.345 km" in mensagens.km_atualizado("ABC-1D23", 12345).texto
    assert "R$ 300,00" in mensagens.manutencao_registrada("ABC-1D23", True, Decimal("300")).texto
    assert "R$" not in mensagens.manutencao_registrada("ABC-1D23", True, Decimal("0")).texto


def test_o_que_pede_proximo_passo_ou_atencao_fica_na_tela():
    criado = mensagens.contrato_criado("Maria", "ABC-1D23")
    assert criado.tom == ALERTA and not criado.atencao and "Vistorias" in criado.texto
    incompleta = mensagens.vistoria_registrada("entrega", "ABC-1D23", falhas_fotos=2)
    assert incompleta.tom == ALERTA and incompleta.atencao and "2 fotos não foram enviadas" in incompleta.texto
    assert mensagens.fotos_anexadas(3).texto == "3 fotos anexadas."
    assert mensagens.fotos_anexadas(1).texto == "1 foto anexada."
    assert mensagens.troca_oleo_registrada(True, None).atencao
    assert mensagens.troca_oleo_registrada(False).tom == TOAST


def test_documento_regularizado_avisa_do_proximo_cadastro():
    assert mensagens.documento_regularizado("IPVA 2026").tom == TOAST
    com_proximo = mensagens.documento_regularizado("IPVA 2026", cadastrar_proximo=True)
    assert com_proximo.tom == ALERTA and "vencimento" in com_proximo.texto


@pytest.mark.parametrize(
    "alterados,trecho",
    [([], "Nenhum valor foi alterado"), (["Multa de atraso", "Adicional por dia"], "Multa de atraso, Adicional por dia")],
)
def test_configuracoes_dizem_o_que_mudou(alterados, trecho):
    assert trecho in mensagens.configuracoes_salvas(alterados).texto


def test_campos_alterados_compara_numeros_e_ignora_ausentes():
    antes = {"multa_atraso_valor": "15.00", "encargo_diario_valor": "7.00", "alerta_cnh_dias": 30}
    depois = {"multa_atraso_valor": "20.00", "encargo_diario_valor": "7", "alerta_cnh_dias": 30}
    assert campos_alterados(antes, depois) == ["Multa de atraso (no vencimento)"]
    assert campos_alterados(antes, {}) == []


def test_encerramento_diz_quanto_devolver_da_caucao_e_o_que_foi_descontado():
    simples = mensagens.contrato_encerrado("Maria", "ABC-1D23")
    assert simples.texto == "Contrato de Maria encerrado. A moto ABC-1D23 está disponível."
    assert simples.tom == TOAST
    com_desconto = mensagens.contrato_encerrado(
        "Maria", "ABC-1D23", devolucao=Decimal("700"), desconto=Decimal("300"), excedente=Decimal("0")
    )
    assert "Devolver R$ 700,00 de caução ao cliente." in com_desconto.texto
    assert "Danos descontados da caução: R$ 300,00." in com_desconto.texto
    assert com_desconto.tom == TOAST


def test_encerramento_com_danos_acima_da_caucao_gera_alerta_com_a_cobranca():
    aviso = mensagens.contrato_encerrado(
        "Maria", "ABC-1D23", devolucao=Decimal("0"), desconto=Decimal("1000"), excedente=Decimal("300")
    )
    assert aviso.tom == ALERTA
    assert "cobrança de R$ 300,00" in aviso.texto
