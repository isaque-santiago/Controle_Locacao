"""Testes de src/domain/pendencias.py (pendências de lançamento propostas pelo conector)."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.pendencias import (
    AVISOS_BLOQUEANTES,
    avisos_despesa,
    avisos_pagamento,
    chave_operacao_padrao,
    escolher_unico,
    normalizar_despesa,
    normalizar_pagamento,
    pode_aprovar,
    pontuar_busca,
    resumo,
)

HOJE = date(2026, 11, 24)
COBRANCA = "11111111-2222-3333-4444-555555555555"


class TestNormalizarPagamento:
    def test_proposta_completa(self):
        r = normalizar_pagamento({"cobranca_id": COBRANCA.upper(), "valor": "1.234,56", "data_pagamento": "20/11/2026", "forma": "PIX",
                                  "multa_juros": "10,5", "observacoes": "  pago  pelo\n app "}, HOJE)
        assert r == {"cobranca_id": COBRANCA, "valor": "1234.56", "multa_juros": "10.50", "data_pagamento": "2026-11-20",
                     "forma": "pix", "observacoes": "pago pelo app"}

    def test_padroes(self):
        r = normalizar_pagamento({"valor": 275}, HOJE)
        assert r["valor"] == "275.00" and r["data_pagamento"] == "2026-11-24" and r["forma"] == "pix"
        assert r["multa_juros"] == "0.00" and r["cobranca_id"] is None and r["observacoes"] is None

    def test_valor_numerico_com_decimais(self):
        assert normalizar_pagamento({"valor": 275.5}, HOJE)["valor"] == "275.50"

    @pytest.mark.parametrize("valor", [None, "", "0", "-5", "abc", True, "10,999", 20000.01, "20.000,01"])
    def test_valor_invalido(self, valor):
        with pytest.raises(ValueError):
            normalizar_pagamento({"valor": valor}, HOJE)

    def test_limite_e_borda(self):
        assert normalizar_pagamento({"valor": "20000"}, HOJE)["valor"] == "20000.00"

    @pytest.mark.parametrize("campos", [{"forma": "abatimento"}, {"forma": "boleto"}, {"cobranca_id": "123"}, {"data_pagamento": "2026-12-25"},
                                        {"data_pagamento": "ontem"}, {"observacoes": "x" * 501}, {"multa_juros": "-1"}])
    def test_recusa(self, campos):
        with pytest.raises(ValueError):
            normalizar_pagamento({"valor": "10", **campos}, HOJE)

    def test_tolera_um_dia_a_frente(self):
        assert normalizar_pagamento({"valor": "10", "data_pagamento": "25/11/2026"}, HOJE)["data_pagamento"] == "2026-11-25"

    def test_forma_sem_acento(self):
        assert normalizar_pagamento({"valor": "10", "forma": "Cartão"}, HOJE)["forma"] == "cartao"


class TestNormalizarDespesa:
    def test_proposta(self):
        r = normalizar_despesa({"valor": "95", "categoria": "Manutenção", "descricao": "Troca de pastilha", "descricao_veiculo": "Biz Yangry",
                                "repassar_locatario": 1, "data": "2026-11-20"}, HOJE)
        assert r == {"moto_id": None, "descricao_veiculo": "Biz Yangry", "valor": "95.00", "data": "2026-11-20",
                     "categoria": "manutencao", "repassar_locatario": True, "observacoes": "Troca de pastilha"}

    def test_categoria_com_espaco(self):
        assert normalizar_despesa({"valor": "1", "descricao": "x", "categoria": "seguro rastreador"}, HOJE)["categoria"] == "seguro_rastreador"

    def test_categoria_padrao_e_descricao_obrigatoria(self):
        assert normalizar_despesa({"valor": "1", "descricao": "x"}, HOJE)["categoria"] == "outros"
        with pytest.raises(ValueError, match="Descreva"):
            normalizar_despesa({"valor": "1"}, HOJE)

    @pytest.mark.parametrize("campos", [{"categoria": "lazer"}, {"valor": "50.000,01"}, {"moto_id": "x"}, {"descricao_veiculo": "v" * 121}])
    def test_recusa(self, campos):
        with pytest.raises(ValueError):
            normalizar_despesa({"valor": "1", "descricao": "x", **campos}, HOJE)


def test_chave_padrao_e_estavel_e_distingue_propostas():
    a = chave_operacao_padrao("pagamento", "chat_financeiro", {"valor": "1.00", "forma": "pix"})
    assert a == chave_operacao_padrao("pagamento", "chat_financeiro", {"forma": "pix", "valor": "1.00"})
    assert a != chave_operacao_padrao("pagamento", "chat_financeiro", {"valor": "2.00", "forma": "pix"})
    assert a != chave_operacao_padrao("pagamento", "chat_contratos", {"valor": "1.00", "forma": "pix"})
    assert a.startswith("auto-") and len(a) <= 120


class TestResumo:
    def test_pagamento(self):
        d = normalizar_pagamento({"valor": "275", "data_pagamento": "2026-11-24"}, HOJE)
        assert resumo("pagamento", d, "Jhonatan", "ABC1D23") == "Pagamento de Jhonatan (ABC1D23): R$ 275,00 em 24/11/2026 por Pix"
        assert resumo("pagamento", d) == "Pagamento: R$ 275,00 em 24/11/2026 por Pix"

    def test_despesa(self):
        d = normalizar_despesa({"valor": "95", "categoria": "seguro_rastreador", "descricao": "x", "data": "2026-11-20"}, HOJE)
        assert resumo("despesa", d, placa="QRS4T21") == "Despesa (QRS4T21): R$ 95,00 em 20/11/2026, seguro rastreador"
        assert resumo("despesa", d) == "Despesa: R$ 95,00 em 20/11/2026, seguro rastreador"


def _codigos(avisos):
    return [a["codigo"] for a in avisos]


class TestAvisosPagamento:
    def _dados(self, valor="275"):
        return normalizar_pagamento({"valor": valor, "data_pagamento": "2026-11-24"}, HOJE)

    def test_cobranca_nao_identificada_bloqueia(self):
        avisos = avisos_pagamento(self._dados(), None)
        assert _codigos(avisos) == ["cobranca_nao_identificada"] and not pode_aprovar(avisos)

    def test_valor_igual_ao_saldo_nao_tem_aviso(self):
        avisos = avisos_pagamento(self._dados(), {"status": "aberta", "saldo": "275.00"})
        assert avisos == [] and pode_aprovar(avisos)

    def test_pagamento_parcial_avisa_mas_deixa_aprovar(self):
        avisos = avisos_pagamento(self._dados("100"), {"status": "aberta", "saldo": "275.00"})
        assert _codigos(avisos) == ["valor_abaixo_do_saldo"] and "R$ 275,00" in avisos[0]["texto"] and pode_aprovar(avisos)

    def test_valor_acima_do_saldo_bloqueia(self):
        avisos = avisos_pagamento(self._dados("300"), {"status": "aberta", "saldo": Decimal("275")})
        assert _codigos(avisos) == ["valor_acima_do_saldo"] and not pode_aprovar(avisos)

    @pytest.mark.parametrize("status,codigo", [("paga", "cobranca_paga"), ("cancelada", "cobranca_cancelada")])
    def test_cobranca_fechada_bloqueia(self, status, codigo):
        avisos = avisos_pagamento(self._dados(), {"status": status, "saldo": "0"})
        assert _codigos(avisos) == [codigo] and not pode_aprovar(avisos)

    def test_duplicada_so_avisa(self):
        avisos = avisos_pagamento(self._dados(), {"status": "aberta", "saldo": "275"}, iguais=1)
        assert _codigos(avisos) == ["possivel_duplicada"] and pode_aprovar(avisos)

    def test_data_no_futuro(self):
        dados = normalizar_pagamento({"valor": "275", "data_pagamento": "25/11/2026"}, HOJE)
        assert "data_no_futuro" in _codigos(avisos_pagamento(dados, {"status": "aberta", "saldo": "275"}, hoje=HOJE))

    def test_bloqueantes_conhecidos(self):
        assert set(AVISOS_BLOQUEANTES) == {"cobranca_nao_identificada", "cobranca_paga", "cobranca_cancelada", "valor_acima_do_saldo", "veiculo_nao_identificado"}


class TestAvisosDespesa:
    def _dados(self, **extra):
        return normalizar_despesa({"valor": "95", "descricao": "x", **extra}, HOJE)

    def test_sem_veiculo_avisa(self):
        assert _codigos(avisos_despesa(self._dados(), None)) == ["sem_veiculo"]

    def test_com_descricao_do_veiculo_nao_avisa(self):
        assert avisos_despesa(self._dados(descricao_veiculo="Biz Yangry"), None) == []

    def test_veiculo_informado_mas_nao_encontrado(self):
        dados = self._dados(moto_id=COBRANCA)
        assert _codigos(avisos_despesa(dados, None)) == ["veiculo_nao_identificado"]
        assert not pode_aprovar(avisos_despesa(dados, None))  # não dá para gravar despesa de um veículo que não existe
        assert avisos_despesa(dados, {"placa": "ABC1D23"}) == []

    def test_duplicada(self):
        assert "possivel_duplicada" in _codigos(avisos_despesa(self._dados(descricao_veiculo="Biz"), None, iguais=2))
        assert pode_aprovar(avisos_despesa(self._dados(), None))


CLIENTES = [
    {"nome": "Jhonatan Silva Souza", "cpf": "529.982.247-25", "placas": ["ABC1D23"]},
    {"nome": "João Pedro Lima", "cpf": "11122233344", "placas": ["QRS4T21", "BRA2E19"]},
    {"nome": "Joana Prado", "cpf": "99988877766", "placas": []},
]


class TestIdentificar:
    def test_pontos_por_nome_cpf_e_placa(self):
        assert pontuar_busca("Jhonatan", CLIENTES[0]) == 10
        assert pontuar_busca("jhonatan silva", CLIENTES[0]) == 20
        assert pontuar_busca("CPF 247", CLIENTES[0]) == 0  # menos de 4 dígitos não vale como CPF parcial
        assert pontuar_busca("CPF 247-25", CLIENTES[0]) == 40  # 24725: 5 dígitos contidos no CPF
        assert pontuar_busca("***.982.247-**", CLIENTES[0]) == 40
        assert pontuar_busca("placa ABC-1D23", CLIENTES[0]) == 50
        assert pontuar_busca("abc1d23", CLIENTES[0]) == 50

    def test_nome_ignora_acento_e_maiusculas(self):
        assert pontuar_busca("JOÃO", CLIENTES[1]) == 10 and pontuar_busca("joao pedro", CLIENTES[1]) == 20

    def test_busca_vazia_ou_curta(self):
        assert pontuar_busca("", CLIENTES[0]) == 0 and pontuar_busca("a 12", CLIENTES[0]) == 0

    def test_escolhe_com_seguranca(self):
        escolhido, motivo = escolher_unico("Jhonatan silva placa ABC1D23", CLIENTES)
        assert escolhido["nome"] == "Jhonatan Silva Souza" and motivo == ""

    def test_nome_ambiguo_nao_escolhe(self):
        escolhido, motivo = escolher_unico("Jo", CLIENTES)
        assert escolhido is None and "Nenhum" in motivo
        assert escolher_unico("joa", CLIENTES)[0] is None  # João e Joana: 10 pontos cada, abaixo do mínimo
        gemeos = [{"nome": "Ana A", "cpf": "00012340000", "placas": []}, {"nome": "Bia B", "cpf": "99912349999", "placas": []}]
        escolhido, motivo = escolher_unico("cpf 1234", gemeos)  # os dois combinam com 40 pontos
        assert escolhido is None and "Mais de um" in motivo

    def test_um_nome_so_nao_basta_mas_nome_e_placa_sim(self):
        assert escolher_unico("Jhonatan", CLIENTES)[0] is None  # 10 pontos, abaixo do mínimo
        assert escolher_unico("Jhonatan ABC1D23", CLIENTES)[0]["cpf"].startswith("529")

    def test_sem_candidatos(self):
        assert escolher_unico("Jhonatan", [])[0] is None


# ---------------------------------------------------------------- escrita direta (etapa 3) --

from src.domain.pendencias import (  # noqa: E402
    TETO_DESPESA_DIRETA,
    TETO_PAGAMENTO_DIRETO,
    cpf_final,
    decidir_gravacao_direta,
    normalizar_cliente,
    normalizar_veiculo,
    proximo_cpf_provisorio,
)


class TestGravarDireto:
    def test_tetos_decididos_pelo_dono(self):
        assert TETO_PAGAMENTO_DIRETO == Decimal("10000.00") and TETO_DESPESA_DIRETA == Decimal("5000.00")

    def test_limpo_e_abaixo_do_teto_grava(self):
        d = normalizar_pagamento({"valor": "275"}, HOJE)
        assert decidir_gravacao_direta("pagamento", d, [])["gravar"] is True

    def test_valor_igual_ao_teto_ainda_grava_e_acima_nao(self):
        assert decidir_gravacao_direta("pagamento", normalizar_pagamento({"valor": "10000"}, HOJE), [])["gravar"]
        r = decidir_gravacao_direta("pagamento", normalizar_pagamento({"valor": "10000.01"}, HOJE), [])
        assert r["gravar"] is False and r["motivo"] == "acima_do_teto" and "R$ 10.000,00" in r["mensagem"]

    def test_despesa_tem_teto_proprio(self):
        d = normalizar_despesa({"valor": "5000.01", "descricao": "x", "descricao_veiculo": "Biz"}, HOJE)
        r = decidir_gravacao_direta("despesa", d, [])
        assert r["gravar"] is False and r["motivo"] == "acima_do_teto" and "R$ 5.000,00" in r["mensagem"]
        assert decidir_gravacao_direta("despesa", normalizar_despesa({"valor": "5000", "descricao": "x", "descricao_veiculo": "Biz"}, HOJE), [])["gravar"]

    def test_qualquer_aviso_vira_duvida_com_o_motivo_no_texto(self):
        d = normalizar_pagamento({"valor": "100"}, HOJE)
        avisos = avisos_pagamento(d, {"status": "aberta", "saldo": "275"})
        r = decidir_gravacao_direta("pagamento", d, avisos)
        assert r["gravar"] is False and r["motivo"] == "duvida" and "Pagamento parcial" in r["mensagem"]

    def test_varios_avisos_aparecem_juntos(self):
        d = normalizar_pagamento({"valor": "100"}, HOJE)
        avisos = avisos_pagamento(d, {"status": "aberta", "saldo": "275"}, iguais=1)
        assert "parcial" in decidir_gravacao_direta("pagamento", d, avisos)["mensagem"] and "igual" in decidir_gravacao_direta("pagamento", d, avisos)["mensagem"]


class TestCpfProvisorio:
    def test_primeiro_e_proximos(self):
        assert proximo_cpf_provisorio([]) == "00000000001"
        assert proximo_cpf_provisorio(["00000000001", "00000000002", "52998224725"]) == "00000000003"

    def test_pula_numero_usado_com_ou_sem_mascara(self):
        assert proximo_cpf_provisorio(["000.000.000-01"]) == "00000000002"

    def test_passa_de_nove(self):
        usados = [str(n).zfill(11) for n in range(1, 11)]
        assert proximo_cpf_provisorio(usados) == "00000000011"

    def test_nunca_devolve_cpf_valido(self):
        from src.domain.validadores import validar_cpf
        assert not any(validar_cpf(proximo_cpf_provisorio([str(n).zfill(11) for n in range(1, k)])) for k in range(2, 40))

    def test_cpf_final(self):
        assert cpf_final("529.982.247-25") == "4725" and cpf_final("") == ""


class TestNormalizarCliente:
    def test_cliente_completo(self):
        r = normalizar_cliente({"nome": "  Maria   da Silva ", "cpf": "529.982.247-25", "telefone": "11912345678", "whatsapp": "(11) 91234-5678",
                                "email": "maria@exemplo.com", "endereco": "Rua A, 10", "observacoes": "indicada"})
        assert r["nome"] == "Maria da Silva" and r["cpf"] == "52998224725" and r["cpf_provisorio"] is False
        assert r["telefone"] == "(11) 91234-5678" and r["email"] == "maria@exemplo.com" and r["confirmar_homonimo"] is False

    @pytest.mark.parametrize("entrada", [{"nome": "Maria"}, {"nome": ""}, {"nome": "Maria Silva"}, {"nome": "Maria Silva", "cpf": "11111111111"},
                                         {"nome": "Maria Silva", "cpf": "52998224726"}, {"nome": "Maria Silva", "cpf": "52998224725", "telefone": "123"},
                                         {"nome": "Maria Silva", "cpf": "52998224725", "email": "sem-arroba"},
                                         {"nome": "Maria Silva", "cpf": "52998224725", "observacoes": "x" * 501},
                                         {"nome": "M" * 161 + " Silva", "cpf": "52998224725"}])
    def test_recusa(self, entrada):
        with pytest.raises(ValueError):
            normalizar_cliente(entrada)

    def test_provisorio_nao_leva_cpf(self):
        r = normalizar_cliente({"nome": "Wagner Souza", "cpf_provisorio": True})
        assert r["cpf"] is None and r["cpf_provisorio"] is True
        with pytest.raises(ValueError, match="não se informa CPF"):
            normalizar_cliente({"nome": "Wagner Souza", "cpf_provisorio": True, "cpf": "52998224725"})

    def test_confirmar_homonimo(self):
        assert normalizar_cliente({"nome": "Maria Silva", "cpf": "52998224725", "confirmar_homonimo": True})["confirmar_homonimo"] is True


class TestNormalizarVeiculo:
    def test_veiculo(self):
        r = normalizar_veiculo({"placa": "abc-1d23", "marca": " Honda ", "modelo": "CG 160", "tipo": "Moto", "km_atual": "12.500", "ano_modelo": 2024})
        assert r["placa"] == "ABC1D23" and r["marca"] == "Honda" and r["tipo"] == "moto" and r["km_atual"] == 12500
        assert r["ano_modelo"] == 2024 and r["ano_fabricacao"] is None

    def test_padroes(self):
        r = normalizar_veiculo({"placa": "ABC1234", "marca": "Fiat", "modelo": "Uno", "tipo": "carro"})
        assert r["km_atual"] == 0 and r["tipo"] == "carro" and r["cor"] is None

    @pytest.mark.parametrize("campos", [{"placa": "123"}, {"marca": ""}, {"modelo": ""}, {"tipo": "barco"}, {"km_atual": "-1"}, {"km_atual": "abc"},
                                        {"ano_modelo": 1900}, {"ano_fabricacao": "xx"}, {"km_atual": 3_000_000}])
    def test_recusa(self, campos):
        with pytest.raises(ValueError):
            normalizar_veiculo({"placa": "ABC1D23", "marca": "Honda", "modelo": "CG", **campos})
