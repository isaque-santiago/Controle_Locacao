"""Testes de src/domain/validadores.py (Fase 1)."""

from src.domain.validadores import validar_cpf, validar_placa, validar_telefone


class TestValidarCpf:
    def test_cpf_valido_sem_mascara(self):
        assert validar_cpf("52998224725") is True

    def test_cpf_valido_com_mascara(self):
        assert validar_cpf("529.982.247-25") is True

    def test_cpf_com_digito_verificador_errado(self):
        assert validar_cpf("52998224700") is False

    def test_cpf_com_todos_digitos_iguais(self):
        assert validar_cpf("11111111111") is False

    def test_cpf_com_tamanho_invalido(self):
        assert validar_cpf("1234567890") is False

    def test_cpf_vazio(self):
        assert validar_cpf("") is False

    def test_cpf_none(self):
        assert validar_cpf(None) is False


class TestValidarPlaca:
    def test_placa_formato_antigo_valida(self):
        assert validar_placa("ABC1234") is True

    def test_placa_formato_antigo_com_hifen(self):
        assert validar_placa("ABC-1234") is True

    def test_placa_formato_mercosul_valida(self):
        assert validar_placa("ABC1D23") is True

    def test_placa_minuscula_e_valida(self):
        assert validar_placa("abc1234") is True

    def test_placa_com_espacos_e_valida(self):
        assert validar_placa("  ABC1234  ") is True

    def test_placa_formato_invalido(self):
        assert validar_placa("ABCD123") is False

    def test_placa_curta(self):
        assert validar_placa("ABC123") is False

    def test_placa_vazia(self):
        assert validar_placa("") is False


class TestValidarTelefone:
    def test_celular_com_nove_digitos_valido(self):
        assert validar_telefone("11987654321") is True

    def test_celular_formatado_valido(self):
        assert validar_telefone("(11) 98765-4321") is True

    def test_fixo_valido(self):
        assert validar_telefone("1132654321") is True

    def test_celular_sem_nono_digito_invalido(self):
        assert validar_telefone("11887654321") is False

    def test_ddd_invalido(self):
        assert validar_telefone("0187654321") is False

    def test_tamanho_invalido(self):
        assert validar_telefone("123456789") is False

    def test_telefone_vazio(self):
        assert validar_telefone("") is False
