"""Testes de src/domain/mensagens_banco.py (mensagens das RPCs com "veículo" no lugar de "moto")."""

import pytest

from src.domain.mensagens_banco import para_o_usuario


@pytest.mark.parametrize(
    "banco,esperado",
    [
        ("Moto não encontrada.", "Veículo não encontrado."),
        ("Moto ABC-1D23 não está disponível (status atual: alugada).", "Veículo ABC-1D23 não está disponível (status atual: alugada)."),
        ("Um contrato aceita até 3 motos.", "Um contrato aceita até 3 veículos."),
        ("Reative a moto antes de registrar manutenção.", "Reative o veículo antes de registrar manutenção."),
        ("A moto já está em outro contrato ativo.", "O veículo já está em outro contrato ativo."),
        ("A mesma moto foi informada mais de uma vez.", "O mesmo veículo foi informado mais de uma vez."),
        ("A moto principal do contrato não pode ser listada como vinculada.", "O veículo principal do contrato não pode ser listado como vinculado."),
    ],
)
def test_troca_moto_por_veiculo_com_o_genero_certo(banco, esperado):
    assert para_o_usuario(banco) == esperado


@pytest.mark.parametrize("texto", ["Cliente não encontrado.", "", "Qualquer outra regra do banco."])
def test_mensagem_desconhecida_volta_igual(texto):
    assert para_o_usuario(texto) == texto


def test_valores_nao_textuais():
    assert para_o_usuario(None) == ""
