"""Testes de src/domain/contrato_modelo.py (dados fictícios)."""

from decimal import Decimal

import pytest

from src.domain.contrato_modelo import TERMOS, montar

CONTRATO = {
    "data_inicio": "2026-03-05",
    "data_fim_prevista": "2026-09-05",
    "periodicidade": "semanal",
    "valor_periodo": Decimal("250.00"),
    "caucao_valor": Decimal("400.00"),
    "km_inicial": 12500,
}
CLIENTE = {
    "nome": "Fulano de Tal",
    "cpf": "52998224725",
    "telefone": "(85) 90000-0001",
    "whatsapp": "(85) 90000-0001",
    "email": "fulano@exemplo.com",
    "endereco": "Rua das Flores, 100, Centro, Cidade - CE",
}
MOTO = {
    "marca": "Honda",
    "modelo": "CG 160 Start",
    "placa": "ABC1D23",
    "renavam": "01234567890",
    "chassi": "9C2KC0000ER000001",
    "cor": "Preta",
    "ano_fabricacao": 2023,
    "ano_modelo": 2024,
}
LOCADOR = {
    "nome": "Empresa Exemplo Ltda",
    "cnpj": "00.000.000/0001-00",
    "cidade": "Cidade",
    "foro": "Cidade-CE",
}


def _texto(blocos):
    return "\n".join(b.texto for b in blocos)


def test_estrutura_tem_dez_clausulas_e_assinaturas():
    blocos = montar(CONTRATO, CLIENTE, MOTO, LOCADOR)
    clausulas = [b.texto for b in blocos if b.tipo == "clausula"]
    assert len(clausulas) == 10
    assert clausulas[0].startswith("CLÁUSULA 1ª - DO OBJETO")
    assert clausulas[-1].startswith("CLÁUSULA 10ª")
    assert blocos[0].tipo == "preambulo"
    assert [b.tipo for b in blocos[-3:]] == ["fecho", "assinatura", "assinatura"]


def test_dados_do_veiculo_e_do_locatario_entram_no_texto():
    texto = _texto(montar(CONTRATO, CLIENTE, MOTO, LOCADOR))
    assert "FULANO DE TAL" in texto
    assert "529.982.247-25" in texto
    assert "ABC1D23" in texto
    assert "HONDA" in texto and "CG 160 START" in texto
    assert "Ano: 2023/2024" in texto
    assert "Quilometragem: 12.500." in texto
    assert "Empresa Exemplo Ltda" in texto


def test_valor_e_caucao_aparecem_por_extenso():
    texto = _texto(montar(CONTRATO, CLIENTE, MOTO, LOCADOR))
    assert "R$ 250,00 (duzentos e cinquenta reais) por semana" in texto
    assert "R$ 400,00 (quatrocentos reais)" in texto
    assert "primeiro vencimento em 05/03/2026" in texto


def test_sem_caucao_o_contrato_diz_que_nao_ha():
    contrato = {**CONTRATO, "caucao_valor": Decimal("0")}
    texto = _texto(montar(contrato, CLIENTE, MOTO, LOCADOR))
    assert "não haverá QUANTIA CAUÇÃO" in texto


def test_vigencia_com_e_sem_termino_previsto():
    com_fim = _texto(montar(CONTRATO, CLIENTE, MOTO, LOCADOR))
    assert "se inicia em 05/03/2026, com término previsto para 05/09/2026" in com_fim
    sem_fim = _texto(montar({**CONTRATO, "data_fim_prevista": None}, CLIENTE, MOTO, LOCADOR))
    assert "se inicia em 05/03/2026, com prazo mínimo" in sem_fim


def test_fecho_usa_cidade_e_data_por_extenso():
    fecho = next(b for b in montar(CONTRATO, CLIENTE, MOTO, LOCADOR) if b.tipo == "fecho")
    assert fecho.texto == "Cidade, 05 DE MARÇO DE 2026."


def test_dados_ausentes_viram_linha_para_preencher():
    texto = _texto(montar(CONTRATO, {"nome": "Sem Dados", "cpf": ""}, MOTO, {}))
    assert "..............................." in texto
    assert "_______________" in texto  # cidade do fecho


def test_penalidades_vem_do_dicionario_de_termos():
    texto = _texto(montar(CONTRATO, CLIENTE, MOTO, LOCADOR))
    assert "R$ 500,00 (quinhentos reais)" in texto
    assert "R$ 15,00 (quinze reais)" in texto
    assert "R$ 7,00 (sete reais)" in texto
    assert "R$ 10.000,00 (dez mil reais)" in texto
    assert "1.000 km rodados" in texto


def test_termos_alterados_refletem_no_contrato(monkeypatch):
    monkeypatch.setitem(TERMOS, "multa_terceiro_conduzir", Decimal("800.00"))
    assert "R$ 800,00 (oitocentos reais)" in _texto(montar(CONTRATO, CLIENTE, MOTO, LOCADOR))


def test_foro_padrao_quando_o_locador_nao_informa():
    texto = _texto(montar(CONTRATO, CLIENTE, MOTO, {}))
    assert f"Comarca de {TERMOS['foro_padrao']}" in texto


def test_marcacoes_de_formatacao_do_cadastro_sao_neutralizadas():
    cliente = {**CLIENTE, "nome": "Fulano **Negrito** __X__ --Y--"}
    texto = _texto(montar(CONTRATO, cliente, MOTO, LOCADOR))
    assert "FULANO *NEGRITO* _X_ -Y-" in texto


@pytest.mark.parametrize("cliente", [CLIENTE, {"nome": "José da Conceição", "cpf": "1"}])
def test_texto_inteiro_cabe_em_latin1(cliente):
    # A fonte padrão do PDF é Latin-1: qualquer caractere fora dela quebraria a geração.
    _texto(montar(CONTRATO, cliente, MOTO, LOCADOR)).encode("latin-1")


def test_todo_item_tem_numero_e_texto():
    for bloco in montar(CONTRATO, CLIENTE, MOTO, LOCADOR):
        if bloco.tipo in ("item", "subitem"):
            assert bloco.numero.endswith(".") and bloco.texto
