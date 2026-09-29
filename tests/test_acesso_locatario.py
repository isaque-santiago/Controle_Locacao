"""Testes de src/domain/acesso_locatario.py (login por CPF e senhas do locatário)."""

import pytest

from src.domain.acesso_locatario import (
    eh_email_de_locatario,
    email_de_acesso,
    identificador_para_email,
    validar_nova_senha,
)

CPF = "52998224725"  # CPF válido de teste


class TestEmailDeAcesso:
    def test_cpf_com_ou_sem_pontuacao(self):
        assert email_de_acesso("529.982.247-25") == f"{CPF}@portal.example.com"
        assert email_de_acesso(CPF) == f"{CPF}@portal.example.com"

    @pytest.mark.parametrize("cpf", ["", "123", "11111111111", "52998224726"])
    def test_cpf_invalido(self, cpf):
        with pytest.raises(ValueError):
            email_de_acesso(cpf)


class TestIdentificadorParaEmail:
    def test_cpf_vira_email_interno(self):
        assert identificador_para_email(" 529.982.247-25 ") == f"{CPF}@portal.example.com"

    def test_email_do_dono_passa_direto(self):
        assert identificador_para_email(" dono@exemplo.com ") == "dono@exemplo.com"

    def test_texto_que_nao_e_cpf_valido_passa_direto(self):
        assert identificador_para_email("12345678900") == "12345678900"

    def test_email_so_com_digitos_nao_vira_cpf(self):
        assert identificador_para_email(f"{CPF}@outro.com") == f"{CPF}@outro.com"


def test_eh_email_de_locatario():
    assert eh_email_de_locatario(f"{CPF}@portal.example.com")
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
