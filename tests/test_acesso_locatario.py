"""Testes de src/domain/acesso_locatario.py (e-mail e senha padrão do locatário)."""

import pytest

from src.domain.acesso_locatario import (
    eh_email_de_locatario,
    email_padrao,
    identificador_para_email,
    senha_padrao,
    usuario_base,
    validar_nova_senha,
)

CPF = "52998224725"  # CPF válido de teste


class TestUsuarioBase:
    @pytest.mark.parametrize(
        "nome,esperado",
        [
            ("João da Silva", "joao.silva"),
            ("  MARIA   de Souza Lima ", "maria.lima"),
            ("Ângela D'Ávila", "angela.davila"),
            ("Madonna", "madonna"),
        ],
    )
    def test_primeiro_nome_e_ultimo_sobrenome(self, nome, esperado):
        assert usuario_base(nome) == esperado

    @pytest.mark.parametrize("nome", ["", "   ", None, "---"])
    def test_nome_vazio(self, nome):
        with pytest.raises(ValueError):
            usuario_base(nome)


class TestEmailPadrao:
    def test_sem_conflito(self):
        assert email_padrao("João da Silva") == "joao.silva@locadora.com"

    def test_homonimos_ganham_sufixo(self):
        ocupados = {"joao.silva@locadora.com"}
        assert email_padrao("João Silva", ocupados) == "joao.silva2@locadora.com"
        ocupados |= {"joao.silva2@locadora.com"}
        assert email_padrao("João Silva", ocupados) == "joao.silva3@locadora.com"

    def test_ocupados_sem_diferenciar_maiusculas(self):
        assert email_padrao("João Silva", {"JOAO.SILVA@LOCADORA.COM"}) == "joao.silva2@locadora.com"


class TestSenhaPadrao:
    def test_primeiro_nome_e_ultimos_seis_digitos(self):
        assert senha_padrao("João da Silva", "529.982.247-25") == "joao224725"
        assert senha_padrao("Ângela Souza", CPF) == "angela224725"

    @pytest.mark.parametrize("cpf", ["", "123", "11111111111", "52998224726"])
    def test_cpf_invalido(self, cpf):
        with pytest.raises(ValueError):
            senha_padrao("João", cpf)

    def test_atende_o_tamanho_minimo(self):
        assert len(senha_padrao("Jo", CPF)) >= 8


class TestIdentificadorParaEmail:
    def test_so_nome_sobrenome_vira_email(self):
        assert identificador_para_email(" Joao.Silva2 ") == "joao.silva2@locadora.com"

    def test_email_completo_passa_direto(self):
        assert identificador_para_email(" dono@exemplo.com ") == "dono@exemplo.com"
        assert identificador_para_email("joao.silva@locadora.com") == "joao.silva@locadora.com"

    def test_vazio(self):
        assert identificador_para_email("  ") == ""


def test_eh_email_de_locatario():
    assert eh_email_de_locatario("joao.silva@locadora.com")
    assert eh_email_de_locatario("JOAO.SILVA@LOCADORA.COM")
    assert not eh_email_de_locatario("dono@exemplo.com")
    assert not eh_email_de_locatario(None)


class TestValidarNovaSenha:
    def test_aceita_senha_valida(self):
        assert validar_nova_senha("moto2026x", "moto2026x", CPF) == "moto2026x"

    @pytest.mark.parametrize(
        "nova,confirmacao",
        [
            ("moto2026x", "moto2026y"),  # não conferem
            ("curta1", "curta1"),  # menos de 8
            ("12345678", "12345678"),  # só números
            (f"a{CPF}", f"a{CPF}"),  # contém o CPF
        ],
    )
    def test_recusa(self, nova, confirmacao):
        with pytest.raises(ValueError):
            validar_nova_senha(nova, confirmacao, CPF)
