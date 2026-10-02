"""Classificação de falhas (Etapa 7): o que a pessoa vê depende do que aconteceu."""

import httpx
import pytest
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthSessionMissingError

from src.domain import erros


def _api(codigo, mensagem="falha", status=None):
    erro = APIError({"message": mensagem, "code": codigo, "hint": None, "details": None})
    if status is not None:
        erro.status = status
    return erro


def test_value_error_e_validacao_com_a_mensagem_original():
    falha = erros.classificar_erro(ValueError("Placa: use ABC1234 ou ABC1D23."))
    assert falha == erros.Falha(erros.VALIDACAO, "Placa: use ABC1234 ou ABC1D23.", False)


def test_raise_exception_das_rpcs_mostra_o_texto_escrito_para_o_usuario():
    falha = erros.classificar_erro(_api("P0001", "Contrato não encontrado ou já encerrado."))
    assert falha.categoria == erros.VALIDACAO
    assert falha.mensagem == "Contrato não encontrado ou já encerrado."
    assert not falha.recuperavel


@pytest.mark.parametrize(
    "erro",
    [
        _api("PGRST301", "JWT expired"),
        _api("PGRST302"),
        _api("XX000", "JWT expired"),
        _api("", "falha", status=401),
        AuthSessionMissingError(),
    ],
)
def test_sessao_expirada(erro):
    falha = erros.classificar_erro(erro)
    assert falha.categoria == erros.SESSAO_EXPIRADA
    assert "Entre novamente" in falha.mensagem
    assert not falha.recuperavel


@pytest.mark.parametrize("erro", [_api("42501"), _api("", "negado", status=403)])
def test_sem_permissao(erro):
    falha = erros.classificar_erro(erro)
    assert falha.categoria == erros.SEM_PERMISSAO
    assert not falha.recuperavel


@pytest.mark.parametrize(
    "erro",
    [
        httpx.ConnectError("sem rede"),
        httpx.ReadTimeout("lento"),
        ConnectionResetError(),
        TimeoutError(),
        _api("", "bad gateway", status=502),
        _api("", "muitas requisições", status=429),
    ],
)
def test_indisponibilidade_do_servico_permite_tentar_de_novo(erro):
    falha = erros.classificar_erro(erro)
    assert falha.categoria == erros.INDISPONIVEL
    assert falha.recuperavel
    assert "tente novamente" in falha.mensagem


@pytest.mark.parametrize(
    "codigo,categoria",
    [
        ("23505", erros.CONFLITO),
        ("23503", erros.CONFLITO),
        ("23514", erros.VALIDACAO),
        ("PGRST202", erros.CONFIGURACAO),
    ],
)
def test_erros_conhecidos_do_banco(codigo, categoria):
    falha = erros.classificar_erro(_api(codigo))
    assert falha.categoria == categoria
    assert not falha.recuperavel


def test_erro_do_banco_sem_classificacao_nao_oferece_repetir():
    falha = erros.classificar_erro(_api("XX999"))
    assert falha.categoria == erros.DESCONHECIDO
    assert not falha.recuperavel


def test_excecao_sem_codigo_orienta_verificar_servico_e_permite_repetir():
    falha = erros.classificar_erro(RuntimeError("segredo ausente"))
    assert falha.categoria == erros.DESCONHECIDO
    assert falha.recuperavel
    assert "Supabase" in falha.mensagem


def test_repeticao_de_envio_so_vale_para_a_chave_de_operacao():
    assert erros.eh_repeticao_de_envio(
        _api("23505", 'duplicate key value violates unique constraint "uq_pagamentos_chave_operacao"')
    )
    assert not erros.eh_repeticao_de_envio(_api("23505", 'unique constraint "motos_placa_key"'))
    assert not erros.eh_repeticao_de_envio(_api("23514", "uq_pagamentos_chave_operacao"))
    assert not erros.eh_repeticao_de_envio(ValueError("chave_operacao"))
