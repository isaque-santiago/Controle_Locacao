"""Testes de src/domain/pedido_senha.py: leitura do CPF do pedido e alerta do Dashboard."""

import pytest

from src.domain.formulario_moto import ErroDeCampos
from src.domain.painel import TOM_ATENCAO, ItemAlerta
from src.domain.pedido_senha import alertas_de_pedidos, ler_cpf

CPF = "529.982.247-25"  # válido


@pytest.mark.parametrize("texto", [CPF, "52998224725", "  529 982 247 25  ", "cpf: 529.982.247-25"])
def test_cpf_vira_so_digitos(texto):
    assert ler_cpf({"cpf": texto}) == "52998224725"


@pytest.mark.parametrize("entrada", [{}, {"cpf": ""}, {"cpf": "   "}, {"cpf": "abc"}])
def test_cpf_ausente_e_recusado(entrada):
    with pytest.raises(ErroDeCampos) as erro:
        ler_cpf(entrada)
    assert "informe o CPF" in erro.value.erros["cpf"]


@pytest.mark.parametrize("texto", ["123", "11111111111", "52998224726", "529982247255"])
def test_cpf_invalido_e_recusado(texto):
    with pytest.raises(ErroDeCampos) as erro:
        ler_cpf({"cpf": texto})
    assert "CPF válido" in erro.value.erros["cpf"]


def test_sem_pedidos_nao_ha_alerta():
    assert alertas_de_pedidos([]) == []


def test_alerta_cita_o_primeiro_cliente_e_conta_os_demais():
    um = alertas_de_pedidos([{"cliente": "Maria Souza"}])
    assert um == [ItemAlerta(1, "Nova senha do portal pedida", "Maria Souza", TOM_ATENCAO, "clientes")]
    varios = alertas_de_pedidos([{"cliente": "Maria Souza"}, {"cliente": "João"}, {"cliente": "Ana"}])
    assert varios[0].quantidade == 3 and varios[0].descricao == "Maria Souza e mais 2" and varios[0].area == "clientes"
    assert alertas_de_pedidos([{}])[0].descricao == "Locatário"
