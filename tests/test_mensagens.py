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
    assert "12.345 km" in mensagens.km_atualizado("ABC-1D23", 12345, km_atual=12000).texto


def test_leitura_historica_menor_diz_que_o_km_atual_continua():
    texto = mensagens.km_atualizado("ABC-1D23", 300, km_atual=500).texto
    assert "300 km" in texto and "histórico" in texto and "O km atual continua 500 km" in texto
    igual = mensagens.km_atualizado("ABC-1D23", 500, km_atual=500).texto
    assert "500 km" in igual and "continua" not in igual
    assert "R$ 300,00" in mensagens.manutencao_registrada("ABC-1D23", True, Decimal("300")).texto
    assert "R$" not in mensagens.manutencao_registrada("ABC-1D23", True, Decimal("0")).texto


def test_contrato_criado_diz_o_que_aconteceu_com_as_fotos_da_entrega():
    sem_fotos = mensagens.contrato_criado("Maria", "ABC-1D23")
    assert "Vistorias" in sem_fotos.texto and "Adicionar fotos" in sem_fotos.texto and not sem_fotos.atencao
    assert "1 foto" not in sem_fotos.texto and "anexadas" not in sem_fotos.texto
    assert mensagens.contrato_criado("Maria", "ABC-1D23", enviadas=1).texto.endswith("Foto da vistoria de entrega anexada.")
    assert "3 fotos da vistoria de entrega anexadas" in mensagens.contrato_criado("Maria", "ABC-1D23", enviadas=3).texto
    parcial = mensagens.contrato_criado("Maria", "ABC-1D23", enviadas=1, falhas_fotos=2)
    assert parcial.atencao and "2 fotos não foram enviadas" in parcial.texto and "Adicionar fotos" in parcial.texto


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


def test_mensagens_do_whatsapp():
    from src.domain import mensagens as m

    assert m.whatsapp_cancelada().tom == "toast" and "cancelada" in m.whatsapp_cancelada().texto
    assert "próxima rodada" in m.whatsapp_reenviada().texto
    bloqueado = m.whatsapp_cliente_bloqueado("Maria")
    assert bloqueado.tom == "alerta" and bloqueado.atencao and "Maria" in bloqueado.texto
    assert m.whatsapp_cliente_liberado("Maria").tom == "toast"
    assert "desligado" in m.whatsapp_controles_salvos(False, True).texto
    teste = m.whatsapp_controles_salvos(True, True)
    assert "modo teste" in teste.texto and not teste.atencao
    real = m.whatsapp_controles_salvos(True, False)
    assert "vão para os clientes" in real.texto and real.atencao


def test_mensagens_do_comprovante_de_documento():
    from src.domain import mensagens as m

    enviado = m.comprovante_enviado("IPVA 2026")
    assert enviado.tom == "toast" and "IPVA 2026" in enviado.texto and "conferir" in enviado.texto
    recusado = m.comprovante_recusado("IPVA 2026")
    assert recusado.tom == "toast" and "motivo" in recusado.texto and "IPVA 2026" in recusado.texto
