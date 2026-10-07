"""Validação do assistente de novo contrato (src/domain/formulario_contrato.py)."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain import formulario_contrato as f
from src.domain.formulario_moto import ErroDeCampos
from src.domain.vistorias import CHECKLIST_PADRAO

BASE = {"data_inicio": "2026-10-07", "indeterminado": "on", "periodicidade": "semanal",
        "valor_periodo": "320,00", "caucao_valor": "500,00"}


def _erros(funcao, *args):
    with pytest.raises(ErroDeCampos) as erro:
        funcao(*args)
    return erro.value.erros


def test_condicoes_validas_com_prazo_indeterminado_ignoram_o_fim():
    dados = f.ler_condicoes({**BASE, "data_fim_prevista": "lixo"})
    assert dados == {"data_inicio": "2026-10-07", "data_fim_prevista": None, "periodicidade": "semanal",
                     "valor_periodo": "320.00", "caucao_valor": "500.00"}
    assert Decimal(dados["valor_periodo"]) == Decimal("320")


def test_condicoes_com_prazo_definido_exigem_fim_valido_e_posterior_ao_inicio():
    sem_marca = {k: v for k, v in BASE.items() if k != "indeterminado"}
    assert f.ler_condicoes({**sem_marca, "data_fim_prevista": "2026-12-31"})["data_fim_prevista"] == "2026-12-31"
    assert "data_fim_prevista" in _erros(f.ler_condicoes, sem_marca)
    assert "posterior ao início" in _erros(f.ler_condicoes, {**sem_marca, "data_fim_prevista": "2026-10-01"})["data_fim_prevista"]


def test_condicoes_um_erro_por_campo():
    erros = _erros(f.ler_condicoes, {"data_inicio": "", "indeterminado": "on", "periodicidade": "anual", "valor_periodo": "0", "caucao_valor": "-5"})
    assert set(erros) == {"data_inicio", "periodicidade", "valor_periodo", "caucao_valor"}


def test_valor_do_periodo_precisa_ser_positivo_mas_caucao_pode_ser_zero():
    assert "valor_periodo" in _erros(f.ler_condicoes, {**BASE, "valor_periodo": "0,00"})
    assert f.ler_condicoes({**BASE, "caucao_valor": "0,00"})["caucao_valor"] == "0.00"


def test_condicoes_iniciais_e_rascunho_de_texto():
    ini = f.condicoes_iniciais(date(2026, 10, 7), "280")
    assert ini["data_inicio"] == "2026-10-07" and ini["data_fim_prevista"] == "2026-11-06"
    assert ini["indeterminado"] is True and ini["valor_periodo"] == "280,00" and ini["caucao_valor"] == "0,00"
    assert f.condicoes_iniciais(date(2026, 10, 7), None)["valor_periodo"] == ""
    assert f.texto_das_condicoes({"valor_periodo": " 12,5 "})["valor_periodo"] == "12,5"
    assert f.texto_das_condicoes({})["indeterminado"] is False


def _vistoria(**extra):
    return {**f.vistoria_inicial(12000), **extra}


def test_vistoria_valida_junta_checklist_padrao_e_adicionais():
    dados = f.ler_vistoria(_vistoria(km="12.500", adicionais="manual do dono=ok\n\nlona=ausente", avarias=" arranhão "), 12000)
    assert dados["km"] == 12500 and dados["nivel_combustivel"] == "vazio" and dados["avarias"] == "arranhão"
    assert set(CHECKLIST_PADRAO) <= set(dados["checklist"]) and dados["checklist"]["lona"] == "ausente"
    assert dados["checklist"]["manual do dono"] == "ok" and dados["checklist"]["farol_dianteiro"] == "ok"


def test_vistoria_km_nao_pode_ser_menor_que_o_da_moto():
    assert "km" in _erros(f.ler_vistoria, _vistoria(km="11999"), 12000)
    assert f.ler_vistoria(_vistoria(km="12000"), 12000)["km"] == 12000
    assert "km" in _erros(f.ler_vistoria, _vistoria(km="abc"), 12000)


def test_vistoria_rejeita_combustivel_estado_e_adicional_invalidos():
    erros = _erros(f.ler_vistoria, _vistoria(nivel_combustivel="5/4", item_buzina="quebrada", adicionais="sem sinal"), 0)
    assert set(erros) == {"nivel_combustivel", "item_buzina", "adicionais"}
    assert "nome=estado" in erros["adicionais"]
    assert "adicionais" in _erros(f.ler_vistoria, _vistoria(adicionais="x=talvez"), 0)
