"""Modelo do contrato de locação com promessa de compra e venda (src/domain/contrato_promessa.py)."""

import re
from decimal import Decimal

import pytest

from src.domain.contrato_promessa import TERMOS, montar

CONTRATO = {
    "data_inicio": "2026-11-16", "periodicidade": "semanal", "valor_periodo": Decimal("300.00"), "numero_parcelas": 130,
    "valor_total": Decimal("39000.00"), "valor_entrada": Decimal("0"), "caucao_valor": Decimal("500.00"),
    "primeira_cobranca": "2026-11-16", "parcelas_pagas_inicial": 0, "km_inicial": 0, "tipo_contrato": "promessa_compra",
}
CLIENTE = {
    "nome": "Alberto Filho da Silva Costa", "cpf": "88766870330", "nacionalidade": "Brasileiro", "naturalidade": "Fortaleza/CE",
    "estado_civil": "União estável", "profissao": "Autônomo", "data_nascimento": "1981-05-18", "rg": "96029195173",
    "rg_orgao": "SSPDS/CE", "cnh_numero": "07196425361", "cnh_categoria": "AB", "cnh_validade": "2033-06-28",
    "email": "alberto@exemplo.com", "telefone": "(88) 9 8884-3795", "whatsapp": "(88) 9 8884-3795",
    "referencias": "Rute (esposa) (88) 9 2180-1972", "endereco": "Rua Manoel Tavares Lopes, nº 1110, Juazeiro do Norte/CE", "cep": "63044-090",
}
MOTO = {
    "marca": "Honda", "modelo": "CG 150 Fan ESDI", "ano_fabricacao": 2013, "ano_modelo": 2014, "placa": "OSA4G16",
    "renavam": "00593642090", "chassi": "9C2KC1680ER484355", "motor": "KC16E8E484355", "cor": "Vermelha",
    "combustivel": "Álcool / Gasolina", "tipo": "moto",
}
LOCADOR = {
    "representante_nome": "Alisson Erllen dos Santos Silva", "representante_qualificacao": "brasileiro, solteiro, empresário",
    "representante_rg": "2004034025786", "representante_cpf": "06791962348", "endereco": "Rua Rocildo Alves de Lima, nº 99, Crato/CE",
    "telefones": "(88) 9 9806-4387", "email": "alisson@exemplo.com", "cidade": "Crato/CE", "foro": "Crato/CE",
}


def _blocos(contrato=None, cliente=None, moto=None, locador=None):
    return montar({**CONTRATO, **(contrato or {})}, {**CLIENTE, **(cliente or {})},
                  MOTO if moto is None else moto, {**LOCADOR, **(locador or {})})


def _quadros(blocos):
    return [dict(b.linhas) for b in blocos if b.tipo == "quadro"]


def _texto(blocos):
    return "\n".join(b.texto for b in blocos)


def _preco(blocos):
    return next(q for q in _quadros(blocos) if "Valor total do contrato" in q)


class TestEstrutura:
    def test_titulo_e_treze_clausulas_em_ordem(self):
        blocos = _blocos()
        assert blocos[0].tipo == "titulo" and "PROMESSA DE COMPRA E VENDA" in blocos[0].texto and blocos[0].texto.startswith("CONTRATO DE LOCAÇÃO")
        clausulas = [b.texto for b in blocos if b.tipo == "clausula"]
        assert len(clausulas) == 13
        assert [int(re.match(r"CLÁUSULA (\d+)ª", c).group(1)) for c in clausulas] == list(range(1, 14))
        assert clausulas[0] == "CLÁUSULA 1ª - DO OBJETO DO CONTRATO" and "PREÇO" in clausulas[7]

    def test_numeracao_dos_itens_sem_repeticao_e_seguindo_a_clausula(self):
        numeros = [b.numero for b in _blocos() if b.tipo in ("item", "subitem")]
        assert len(numeros) == len(set(numeros))
        atual = 0
        for b in _blocos():
            if b.tipo == "clausula":
                atual = int(re.match(r"CLÁUSULA (\d+)", b.texto).group(1))
            elif b.tipo in ("item", "subitem"):
                assert b.numero.startswith(f"{atual}."), (atual, b.numero)

    def test_tudo_cabe_em_latin1_e_negritos_fecham(self):
        for b in _blocos():
            textos = [b.texto, b.numero] + [c for linha in b.linhas for c in linha]
            for texto in textos:
                texto.encode("latin-1")
                assert texto.count("**") % 2 == 0, texto

    def test_termina_com_resumo_fecho_e_duas_assinaturas(self):
        blocos = _blocos()
        assert [b.tipo for b in blocos[-4:]] == ["resumo", "fecho", "assinatura", "assinatura"]
        assert blocos[-3].texto == "Crato/CE, 16 de novembro de 2026."
        assert blocos[-2].texto == "ALISSON ERLLEN DOS SANTOS SILVA" and "CPF 067.919.623-48" in blocos[-2].numero
        assert blocos[-1].texto == "ALBERTO FILHO DA SILVA COSTA" and "CPF 887.668.703-30" in blocos[-1].numero


class TestPartes:
    def test_locador_pessoa_fisica(self):
        texto = _texto(_blocos())
        assert "**LOCADOR / PROMITENTE VENDEDOR: ALISSON ERLLEN DOS SANTOS SILVA**, brasileiro, solteiro, empresário" in texto
        assert "RG nº 2004034025786, inscrito no CPF nº 067.919.623-48" in texto and "residente e domiciliado em Rua Rocildo" in texto
        assert "proprietário do veículo descrito na Cláusula 1ª, doravante denominado LOCADOR" in texto

    def test_locador_pessoa_juridica(self):
        texto = _texto(_blocos(locador={"nome": "Erllen Variedades", "cnpj": "24.995.183/0001-90", "endereco": "Rua Bom Jesus, 956"}))
        assert "**LOCADOR / PROMITENTE VENDEDOR: ERLLEN VARIEDADES**, pessoa jurídica inscrita no CNPJ nº 24.995.183/0001-90" in texto
        assert "representada por **ALISSON ERLLEN DOS SANTOS SILVA**" in texto

    def test_quadro_do_locatario_com_os_dados_do_cadastro(self):
        q = _quadros(_blocos())[0]
        assert q["Nome completo"] == "Alberto Filho da Silva Costa" and q["Estado civil"] == "União estável"
        assert q["Data de nascimento"] == "18/05/1981" and q["RG / Órgão emissor"] == "96029195173 SSPDS/CE"
        assert q["CPF"] == "887.668.703-30" and q["CNH"] == "07196425361 - Categoria AB (validade 28/06/2033)"
        assert q["Telefone / WhatsApp"] == "(88) 9 8884-3795 · Referências: Rute (esposa) (88) 9 2180-1972"
        assert q["CEP"] == "63044-090" and q["Endereço"].startswith("Rua Manoel")

    def test_dado_que_falta_sai_em_branco_para_preencher_a_mao(self):
        vazio = {c: None for c in ("nacionalidade", "naturalidade", "estado_civil", "profissao", "data_nascimento", "rg", "rg_orgao",
                                   "cnh_numero", "cep", "referencias", "email", "endereco")}
        q = _quadros(_blocos(cliente=vazio))[0]
        for rotulo in ("Nacionalidade", "Profissão", "Data de nascimento", "RG / Órgão emissor", "CNH", "CEP"):
            assert set(q[rotulo]) == {"_"}, rotulo


class TestVeiculo:
    def test_quadro_do_veiculo(self):
        q = _quadros(_blocos())[1]
        assert q["Tipo"] == "Motocicleta" and q["Marca / Modelo"] == "Honda CG 150 Fan ESDI"
        assert q["Ano fabricação / modelo"] == "2013 / 2014" and q["Placa"] == "OSA4G16" and q["Motor"] == "KC16E8E484355"
        assert q["Cor / Combustível"] == "Vermelha / Álcool / Gasolina"
        assert q["Quilometragem na entrega"].endswith("_ km")  # km da entrega: a mão

    def test_carro_e_km_conhecido(self):
        q = _quadros(_blocos(contrato={"km_inicial": 12500}, moto={**MOTO, "tipo": "carro"}))[1]
        assert q["Tipo"] == "Automóvel" and q["Quilometragem na entrega"] == "12.500 km"

    def test_varias_motos_ganham_um_quadro_cada(self):
        blocos = _blocos(moto=[MOTO, {**MOTO, "placa": "BRA2E19"}])
        assert [b.texto for b in blocos if b.tipo == "legenda"][:2] == ["Veículo 1 de 2", "Veículo 2 de 2"]
        assert [q["Placa"] for q in _quadros(blocos)[1:3]] == ["OSA4G16", "BRA2E19"]
        assert "dos veículos abaixo descritos" in _texto(blocos)


class TestPreco:
    def test_igual_ao_contrato_de_exemplo(self):
        q = _preco(_blocos())
        assert q["Entrada"] == "Sem entrada"
        assert q["Parcelas"] == "130 (cento e trinta) parcelas semanais de R$ 300,00 (trezentos reais) cada"
        assert q["Vencimento das parcelas"].startswith("Toda segunda-feira. A 1ª parcela (R$ 300,00) é paga no ato da assinatura, restando 129 (cento e vinte e nove) parcelas")
        assert q["1ª e última parcela"] == "1ª em 16/11/2026 (paga na assinatura) · 130ª em 07/05/2029"
        assert q["Valor total do contrato"] == "R$ 39.000,00 (trinta e nove mil reais)"
        assert q["Caução"].startswith("R$ 500,00 (quinhentos reais), paga na retirada do veículo; não abate parcelas")

    def test_sem_caucao_e_com_entrada(self):
        q = _preco(_blocos(contrato={"caucao_valor": 0, "valor_entrada": Decimal("1000.00")}))
        assert q["Caução"] == "Sem caução" and q["Entrada"] == "R$ 1.000,00 (mil reais)"

    @pytest.mark.parametrize(
        "periodicidade,primeira,esperado",
        [("semanal", "2026-11-14", "Todo sábado"), ("semanal", "2026-11-15", "Todo domingo"), ("mensal", "2026-11-10", "Todo dia 10"),
         ("quinzenal", "2026-11-10", "A cada 15 dias, a partir de 10/11/2026"), ("diario", "2026-11-10", "Todos os dias")],
    )
    def test_vencimento_por_periodicidade(self, periodicidade, primeira, esperado):
        q = _preco(_blocos(contrato={"periodicidade": periodicidade, "primeira_cobranca": primeira, "data_inicio": "2026-11-01"}))
        assert q["Vencimento das parcelas"].startswith(esperado)

    def test_parcelas_ja_pagas_e_primeira_cobranca_depois_da_assinatura(self):
        q = _preco(_blocos(contrato={"parcelas_pagas_inicial": 10, "primeira_cobranca": "2026-12-07", "data_inicio": "2026-11-16"}))
        assert "paga na assinatura" not in q["1ª e última parcela"] and q["1ª e última parcela"].startswith("1ª em 07/12/2026")
        assert "120ª em" in q["1ª e última parcela"]

    def test_sem_valor_total_soma_entrada_e_parcelas(self):
        q = _preco(_blocos(contrato={"valor_total": None, "numero_parcelas": 10, "valor_entrada": Decimal("500.00")}))
        assert q["Valor total do contrato"].startswith("R$ 3.500,00")


class TestValoresFixos:
    def test_valores_do_contrato_de_exemplo_aparecem_no_texto(self):
        texto = _texto(_blocos())
        for trecho in ("R$ 500,00 (quinhentos reais)", "R$ 20,00 (vinte reais) por dia", "R$ 10.000,00 (dez mil reais)",
                       "R$ 200,00 (duzentos reais)", "R$ 30,00 (trinta reais) por dia", "R$ 150,00 (cento e cinquenta reais)",
                       "Grande Cariri", "DETRAN-CE", "R$ 10,00 (dez reais) por ocorrência", "30 (trinta) dias corridos",
                       "R$ 15,00 (quinze reais) a título de multa", "R$ 7,00 (sete reais) por dia de atraso",
                       "15 (quinze) dias", "R$ 100,00 (cem reais)", "R$ 50,00 (cinquenta reais) por dia", "Comarca de Crato/CE"):
            assert trecho in texto, trecho

    def test_alterar_termos_muda_texto_e_resumo(self, monkeypatch):
        monkeypatch.setitem(TERMOS, "multa_vistoria_por_dia", Decimal("35.00"))
        blocos = _blocos()
        assert "R$ 35,00 (trinta e cinco reais) por dia de atraso" in _texto(blocos)
        resumo = next(b for b in blocos if b.tipo == "resumo")
        assert ("Não apresentar o veículo para vistoria mensal", "R$ 35,00 por dia", "3.3") in resumo.linhas

    def test_resumo_de_multas_aponta_para_itens_que_existem(self):
        blocos = _blocos()
        itens = {b.numero.rstrip(".") for b in blocos if b.tipo in ("item", "subitem")}
        resumo = next(b for b in blocos if b.tipo == "resumo")
        assert len(resumo.linhas) == 12
        for _, _, clausula in resumo.linhas:
            assert clausula in itens

    def test_foro_e_cidade_do_locador_prevalecem(self):
        blocos = _blocos(locador={"foro": "Fortaleza/CE", "cidade": "Fortaleza/CE"})
        assert "Comarca de Fortaleza/CE" in _texto(blocos) and blocos[-3].texto.startswith("Fortaleza/CE,")
