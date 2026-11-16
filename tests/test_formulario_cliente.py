"""Leitura e validação do formulário de cliente (src/domain/formulario_cliente.py), com os dados que o contrato usa."""

import pytest

from src.domain.formulario_cliente import ler_cliente
from src.domain.formulario_moto import ErroDeCampos

BASE = {"nome": " Alberto  Filho da Silva Costa ", "cpf": "529.982.247-25", "status": "ativo"}


def test_dados_do_contrato_sao_normalizados():
    dados = ler_cliente({
        **BASE, "nacionalidade": " Brasileiro ", "naturalidade": "Fortaleza/CE", "estado_civil": "União  estável",
        "profissao": "Autônomo", "data_nascimento": "1981-05-18", "rg": "96029195173", "rg_orgao": "SSPDS/CE",
        "cep": "63044090", "referencias": "Rute (esposa) (88) 9 2180-1972",
    })
    assert dados["nacionalidade"] == "Brasileiro" and dados["estado_civil"] == "União estável"
    assert dados["data_nascimento"] == "1981-05-18" and dados["cep"] == "63044-090"
    assert dados["rg"] == "96029195173" and dados["rg_orgao"] == "SSPDS/CE" and dados["referencias"].startswith("Rute")


def test_campos_novos_sao_opcionais():
    dados = ler_cliente(BASE)
    for campo in ("nacionalidade", "naturalidade", "estado_civil", "profissao", "data_nascimento", "rg", "rg_orgao", "cep", "referencias"):
        assert dados[campo] is None


def test_cep_com_pontuacao_e_aceito():
    assert ler_cliente({**BASE, "cep": "63.044-090"})["cep"] == "63044-090"


@pytest.mark.parametrize(
    "campo,valor",
    [("cep", "123"), ("data_nascimento", "31/02/1990"), ("data_nascimento", "1850-01-01"), ("data_nascimento", "2999-01-01")],
)
def test_valores_invalidos_apontam_o_campo(campo, valor):
    with pytest.raises(ErroDeCampos) as erro:
        ler_cliente({**BASE, campo: valor})
    assert campo in erro.value.erros
