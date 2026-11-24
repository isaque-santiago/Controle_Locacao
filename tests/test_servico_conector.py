"""Serviço do conector do claude.ai (seção 24.7b): normaliza, chama a RPC e devolve um texto que o chat entende. Banco isolado por mocks."""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.domain.pendencias import chave_operacao_padrao
from src.services import conector as servico_conector
from src.services.autenticacao import CredenciaisInvalidas, TokensUsuario
from src.services.conector import MENSAGEM_FALHA, ServicoConector, texto_da_gravacao

REPO = "src.services.conector.repositorio"
COBRANCA = "11111111-2222-3333-4444-555555555555"
MOTO = "99999999-2222-3333-4444-555555555555"
HOJE = date(2026, 11, 24)


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


class AutenticacaoFalsa:
    def __init__(self, relogio, falhar=False):
        self.relogio, self.entradas, self.falhar = relogio, 0, falhar

    def entrar(self, email, senha):
        self.entradas += 1
        if self.falhar:
            raise CredenciaisInvalidas()
        return TokensUsuario(usuario_id="u", email=email, access_token=f"tok-{self.entradas}", refresh_token="r", expira_em=self.relogio() + 3600)


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def autenticacao(relogio):
    return AutenticacaoFalsa(relogio)


@pytest.fixture
def servico(autenticacao, relogio):
    usados = []

    @contextmanager
    def usar_cliente(cliente):
        usados.append(cliente)
        yield cliente

    banco = SimpleNamespace(criar_cliente_autenticado=lambda token: f"cliente({token})", usar_cliente=usar_cliente)
    with patch.object(servico_conector, "db", banco):
        s = ServicoConector("conector@exemplo.com", "senha", autenticacao, relogio, lambda: HOJE)
        s.clientes_usados = usados
        yield s


def _gravou(resumo="Pagamento de X: R$ 275,00"):
    return {"gravado": True, "repetida": False, "pendencia_id": "p", "registro_id": "r", "resumo": resumo}


class TestLogin:
    def test_entra_uma_vez_e_reaproveita_o_cliente(self, servico, autenticacao):
        with patch(f"{REPO}.veiculos", return_value=[]):
            servico.executar("buscar_veiculos", {"busca": "ABC"})
            servico.executar("buscar_veiculos", {"busca": "ABC"})
        assert autenticacao.entradas == 1 and servico.clientes_usados == ["cliente(tok-1)"] * 2

    def test_renova_o_login_antes_de_vencer(self, servico, autenticacao, relogio):
        with patch(f"{REPO}.veiculos", return_value=[]):
            servico.executar("buscar_veiculos", {"busca": "ABC"})
            relogio.agora += 3600 - 60  # faltam 60 s: dentro da margem de 120 s
            servico.executar("buscar_veiculos", {"busca": "ABC"})
        assert autenticacao.entradas == 2 and servico.clientes_usados[-1] == "cliente(tok-2)"

    def test_credencial_recusada_vira_mensagem_sem_detalhes(self, servico, autenticacao):
        autenticacao.falhar = True
        r = servico.executar("buscar_veiculos", {"busca": "ABC"})
        assert r["erro"] and "não conseguiu entrar no banco" in r["texto"] and "senha" not in r["texto"].lower()


class TestPagamento:
    def _args(self, **extra):
        return {"cobranca_id": COBRANCA, "valor": "275", "forma": "Pix", "trecho_origem": "Jhonatan pagou 275", **extra}

    def test_normaliza_e_monta_o_payload(self, servico):
        with patch(f"{REPO}.registrar_pagamento", return_value=_gravou()) as rpc:
            r = servico.executar("registrar_pagamento", self._args(data_pagamento="20/11/2026"))
        payload = rpc.call_args.args[0]
        assert payload["origem"] == "chat_financeiro" and payload["trecho_origem"] == "Jhonatan pagou 275"
        assert payload["dados"] == {"cobranca_id": COBRANCA, "valor": "275.00", "multa_juros": "0.00", "data_pagamento": "2026-11-20",
                                    "forma": "pix", "observacoes": None}
        assert payload["chave_operacao"] == chave_operacao_padrao("pagamento", "chat_financeiro", payload["dados"])
        assert r == {"texto": "Gravado: Pagamento de X: R$ 275,00.", "erro": False}

    def test_a_mesma_proposta_gera_a_mesma_chave(self, servico):
        with patch(f"{REPO}.registrar_pagamento", return_value=_gravou()) as rpc:
            servico.executar("registrar_pagamento", self._args())
            servico.executar("registrar_pagamento", self._args(observacoes=None))
        assert rpc.call_args_list[0].args[0]["chave_operacao"] == rpc.call_args_list[1].args[0]["chave_operacao"]

    def test_chave_do_chat_vale(self, servico):
        with patch(f"{REPO}.registrar_pagamento", return_value=_gravou()) as rpc:
            servico.executar("registrar_pagamento", self._args(chave_operacao="  minha-chave  "))
        assert rpc.call_args.args[0]["chave_operacao"] == "minha-chave"

    @pytest.mark.parametrize("args,trecho", [({"valor": "0"}, "valor"), ({"valor": "abc"}, "valor"), ({"valor": "20000.01"}, "limite"),
                                             ({"forma": "abatimento"}, "forma"), ({"cobranca_id": "123"}, "cobrança"),
                                             ({"data_pagamento": "2027-01-01"}, "futuro")])
    def test_argumento_invalido_nao_chama_o_banco(self, servico, args, trecho):
        with patch(f"{REPO}.registrar_pagamento") as rpc:
            r = servico.executar("registrar_pagamento", self._args(**args))
        assert r["erro"] and trecho in r["texto"] and not rpc.called

    def test_nao_gravou_vira_erro_com_o_motivo_e_manda_perguntar(self, servico):
        recusa = {"gravado": False, "motivo": "duvida", "mensagem": "Pagamento parcial: o saldo da cobrança é R$ 300,00.", "avisos": []}
        with patch(f"{REPO}.registrar_pagamento", return_value=recusa):
            r = servico.executar("registrar_pagamento", self._args())
        assert r["erro"] is True and r["texto"].startswith("NÃO GRAVADO (duvida): Pagamento parcial")
        assert "Pergunte ao usuário" in r["texto"]


class TestDemaisFerramentas:
    def test_despesa(self, servico):
        with patch(f"{REPO}.registrar_despesa", return_value=_gravou("Despesa: R$ 95,00")) as rpc:
            r = servico.executar("registrar_despesa", {"valor": 95, "descricao": "Pastilha", "categoria": "Manutenção", "moto_id": MOTO})
        p = rpc.call_args.args[0]
        assert p["origem"] == "chat_financeiro" and p["dados"]["categoria"] == "manutencao" and p["dados"]["observacoes"] == "Pastilha"
        assert p["dados"]["data"] == "2026-11-24" and p["dados"]["moto_id"] == MOTO and r["erro"] is False

    def test_cliente_com_cpf_e_com_cpf_provisorio(self, servico):
        with patch(f"{REPO}.cadastrar_cliente", return_value=_gravou("Cliente cadastrado")) as rpc:
            servico.executar("cadastrar_cliente", {"nome": "Maria da Silva", "cpf": "529.982.247-25", "telefone": "11912345678"})
            servico.executar("cadastrar_cliente", {"nome": "Wagner Souza", "cpf_provisorio": True})
        primeiro, segundo = (c.args[0] for c in rpc.call_args_list)
        assert primeiro["origem"] == "chat_contratos" and primeiro["dados"]["cpf"] == "52998224725" and primeiro["dados"]["telefone"] == "(11) 91234-5678"
        assert segundo["dados"]["cpf"] is None and segundo["dados"]["cpf_provisorio"] is True

    def test_cliente_invalido_nao_chama_o_banco(self, servico):
        with patch(f"{REPO}.cadastrar_cliente") as rpc:
            r = servico.executar("cadastrar_cliente", {"nome": "Maria", "cpf": "529.982.247-25"})
        assert r["erro"] and "nome completo" in r["texto"] and not rpc.called

    def test_veiculo(self, servico):
        with patch(f"{REPO}.cadastrar_veiculo", return_value=_gravou("Veículo cadastrado")) as rpc:
            servico.executar("cadastrar_veiculo", {"placa": "abc-1d23", "marca": "Honda", "modelo": "CG 160", "km_atual": "12.500"})
        d = rpc.call_args.args[0]["dados"]
        assert d["placa"] == "ABC1D23" and d["km_atual"] == 12500 and d["tipo"] == "moto"

    def test_cobrancas_abertas_em_texto_e_aviso_de_mais_de_um_cliente(self, servico):
        linhas = [
            {"cobranca_id": "c1", "cliente_nome": "Jhonatan Silva", "cpf_final": "0061", "placa": "PEN1A11", "vencimento": "2026-11-24",
             "valor": 275, "saldo": 275.0},
            {"cobranca_id": "c2", "cliente_nome": "Jhonatan Moreira", "cpf_final": "4439", "placa": "OIQ5024", "vencimento": "2026-11-17",
             "valor": 343.75, "saldo": 216.25},
        ]
        with patch(f"{REPO}.cobrancas_abertas", return_value=linhas) as rpc:
            r = servico.executar("consultar_cobrancas_abertas", {"busca": "Jhonatan"})
        assert rpc.call_args.args == ("Jhonatan",) and r["erro"] is False
        assert "cobranca_id=c1" in r["texto"] and "CPF final 0061" in r["texto"] and "saldo R$ 216,25" in r["texto"] and "vencimento 24/11/2026" in r["texto"]
        assert "mais de um cliente" in r["texto"]
        com_um = servico_conector.texto_das_cobrancas(linhas[:1])
        assert "mais de um cliente" not in com_um["texto"]

    def test_listas_vazias(self, servico):
        with patch(f"{REPO}.cobrancas_abertas", return_value=[]), patch(f"{REPO}.veiculos", return_value=[]), patch(f"{REPO}.ultimos_lancamentos", return_value=[]):
            assert "Nenhuma cobrança" in servico.executar("consultar_cobrancas_abertas", {"busca": "x"})["texto"]
            assert "Nenhum veículo" in servico.executar("buscar_veiculos", {"busca": "x"})["texto"]
            assert "ainda não gravou" in servico.executar("listar_ultimos_lancamentos", {})["texto"]

    def test_ultimos_lancamentos(self, servico):
        linhas = [{"resumo": "Pagamento X", "status": "desfeita", "decisao_automatica": True, "criado_em": "2026-11-24T15:30:00+00:00"},
                  {"resumo": "Cliente Y", "status": "aprovada", "decisao_automatica": True, "criado_em": "2026-11-24T12:00:00+00:00"}]
        with patch(f"{REPO}.ultimos_lancamentos", return_value=linhas) as rpc:
            r = servico.executar("listar_ultimos_lancamentos", {"limite": 5})
        assert rpc.call_args.args == (5,)
        assert "Pagamento X | desfeito pelo dono | automático" in r["texto"] and "Cliente Y | gravado" in r["texto"]


class TestErros:
    def test_erro_de_regra_do_banco_vai_para_o_chat(self, servico):
        erro = APIError({"message": "O valor precisa ser um número positivo.", "code": "P0001"})
        with patch(f"{REPO}.registrar_pagamento", side_effect=erro):
            r = servico.executar("registrar_pagamento", {"cobranca_id": COBRANCA, "valor": "10"})
        assert r == {"texto": "O valor precisa ser um número positivo.", "erro": True}

    @pytest.mark.parametrize("erro", [APIError({"message": "permission denied for table clientes", "code": "42501"}),
                                      RuntimeError("segredo-interno-123"), ConnectionError("db.interno:5432")])
    def test_falha_inesperada_nao_vaza_detalhe(self, servico, erro):
        with patch(f"{REPO}.registrar_pagamento", side_effect=erro):
            r = servico.executar("registrar_pagamento", {"cobranca_id": COBRANCA, "valor": "10"})
        assert r == {"texto": MENSAGEM_FALHA, "erro": True}

    def test_ferramenta_desconhecida(self, servico):
        assert servico.executar("apagar_tudo", {})["erro"] is True


def test_texto_da_gravacao_repetida_e_desfeita():
    assert texto_da_gravacao({"gravado": True, "repetida": True, "resumo": "X"})["texto"] == "Já estava gravado: X."
    r = texto_da_gravacao({"gravado": False, "repetida": True, "status": "desfeita", "mensagem": "Foi desfeito pelo dono."})
    assert r["erro"] and "NÃO GRAVADO (desfeita)" in r["texto"]


class TestRepositorio:
    def test_gravacoes_descartam_o_cache_mesmo_com_erro(self):
        from src.repositories import conector as repo

        cliente = MagicMock()
        cliente.rpc.return_value.execute.return_value.data = {"gravado": True}
        limpou = []
        with patch.object(repo, "get_client", return_value=cliente), patch("src.repositories.consultas.limpar_cache", lambda: limpou.append(1)):
            repo.registrar_pagamento({"a": 1})
            cliente.rpc.side_effect = RuntimeError("falhou")
            with pytest.raises(RuntimeError):
                repo.cadastrar_cliente({"a": 1})
        assert limpou == [1, 1]
        cliente.rpc.assert_called_with("rpc_conector_cadastrar_cliente", {"payload": {"a": 1}})

    def test_consultas_nao_descartam_o_cache(self):
        from src.repositories import conector as repo

        cliente = MagicMock()
        cliente.rpc.return_value.execute.return_value.data = None
        limpou = []
        with patch.object(repo, "get_client", return_value=cliente), patch("src.repositories.consultas.limpar_cache", lambda: limpou.append(1)):
            assert repo.cobrancas_abertas("x") == [] and repo.veiculos("x") == [] and repo.ultimos_lancamentos() == []
        assert limpou == []
        cliente.rpc.assert_any_call("rpc_conector_cobrancas_abertas", {"p_busca": "x", "p_limite": 20})


def test_servico_do_ambiente_sem_usuario_de_servico_fica_desligado(monkeypatch):
    for v in ("SERVICO_CONECTOR_EMAIL", "SERVICO_CONECTOR_SENHA"):
        monkeypatch.delenv(v, raising=False)
    with patch("src.config._segredo_do_arquivo", return_value=None):
        assert servico_conector.servico_do_ambiente() is None
    monkeypatch.setenv("SERVICO_CONECTOR_EMAIL", "c@exemplo.com")
    monkeypatch.setenv("SERVICO_CONECTOR_SENHA", "s")
    assert isinstance(servico_conector.servico_do_ambiente(), ServicoConector)
