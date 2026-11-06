"""Testes de src/services/whatsapp.py com repositório e Evolution falsos: enfileira, respeita a janela e o modo teste."""

from datetime import date, datetime

import pytest

from src.domain.janela_envio import FUSO
from src.domain.textos_whatsapp import OpcoesTexto
from src.services import whatsapp
from src.services.evolution import ErroEnvio, EvolutionConfiguracaoInvalida, EvolutionIndisponivel

OP = OpcoesTexto(empresa="LA Motos", contato="o Alisson")
QUINTA_10H = datetime(2026, 11, 12, 10, 0, tzinfo=FUSO)
QUINTA_20H = datetime(2026, 11, 12, 20, 0, tzinfo=FUSO)
DOMINGO_10H = datetime(2026, 11, 15, 10, 0, tzinfo=FUSO)


def _bruto(ativo=True, modo_teste=False, numero_teste=None, whatsapp="(11) 98888-7777"):
    return {
        "config": {"ativo": ativo, "modo_teste": modo_teste, "numero_teste": numero_teste, "max_repeticoes": 10,
                   "dias_inadimplencia": 15, "multa_atraso": "15.00", "encargo_diario": "7.00"},
        "cobrancas": [{"id": "cob-1", "cliente_id": "cli-1", "tipo": "locacao", "vencimento": "2026-11-10", "saldo": "450.00",
                       "periodicidade": "semanal", "situacao": "atrasada", "placa": "ABC1D23"}],
        "pagamentos": [], "cnhs": [], "documentos": [], "oleo": [], "portal": [],
        "clientes": [{"id": "cli-1", "nome": "Maria Souza", "whatsapp": whatsapp}],
        "historico": [],
    }


class RepoFalso:
    def __init__(self, bruto, pendentes=()):
        self.bruto, self.pendentes = bruto, list(pendentes)
        self.dias_lidos, self.enfileirado, self.resultados = [], [], []

    def dados(self, dia):
        self.dias_lidos.append(dia)
        return self.bruto

    def enfileirar(self, mensagens):
        self.enfileirado.append(mensagens)
        return {"enfileiradas": len(mensagens), "sem_numero": 0, "duplicadas": 0, "bloqueadas": 0}

    def reservar(self, limite):
        return self.pendentes[:limite]

    def registrar_resultado(self, mensagem_id, resultado, erro=None, evolution_id=None):
        self.resultados.append((mensagem_id, resultado, erro, evolution_id))
        return {}


class EvolutionFalsa:
    def __init__(self, estado="open", tem_whatsapp=True, falhas=None):
        self._estado, self._tem, self._falhas = estado, tem_whatsapp, falhas or {}
        self.enviados = []

    def estado(self):
        if isinstance(self._estado, Exception):
            raise self._estado
        return self._estado

    def numero_tem_whatsapp(self, numero):
        return self._tem

    def enviar_texto(self, numero, texto):
        if numero in self._falhas:
            raise self._falhas[numero]
        self.enviados.append((numero, texto))
        return f"EVO-{len(self.enviados)}"


def _pendente(id, numero="5511988887777"):
    return {"id": id, "cliente_id": "cli-1", "numero": numero, "texto": "Olá, Maria!", "tentativas": 0}


@pytest.fixture
def instalar(monkeypatch):
    def _instalar(repo):
        monkeypatch.setattr(whatsapp, "repo", repo)
        return repo
    return _instalar


def _executar(evolution, agora=QUINTA_10H, pausas=None):
    pausas = pausas if pausas is not None else []
    return whatsapp.executar(evolution, OP, agora, dormir=pausas.append, sorteio=lambda a, b: 30)


# ---------------------------------------------------------------- desligado --


def test_envio_desligado_nao_enfileira_nem_envia(instalar):
    repo = instalar(RepoFalso(_bruto(ativo=False), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    assert _executar(evolution) == {"ativo": False}
    assert repo.enfileirado == [] and repo.resultados == [] and evolution.enviados == []


# ---------------------------------------------------------------- enfileirar --


def test_enfileira_a_mensagem_devida_com_o_numero_normalizado(instalar):
    repo = instalar(RepoFalso(_bruto()))
    resumo = _executar(EvolutionFalsa())
    assert resumo["fila"]["enfileiradas"] == 1
    mensagem = repo.enfileirado[0][0]
    assert mensagem["cliente_id"] == "cli-1" and mensagem["numero"] == "5511988887777"
    assert mensagem["itens"][0]["tipo"] == "atraso" and mensagem["itens"][0]["data_referencia"] == "2026-11-12"
    assert "Olá, Maria!" in mensagem["texto"] and "R$" in mensagem["texto"]


def test_sem_nada_devido_nao_chama_a_fila(instalar):
    bruto = _bruto()
    bruto["cobrancas"] = []
    repo = instalar(RepoFalso(bruto))
    assert _executar(EvolutionFalsa())["fila"]["enfileiradas"] == 0
    assert repo.enfileirado == []


def test_cliente_sem_whatsapp_vai_sem_numero(instalar):
    repo = instalar(RepoFalso(_bruto(whatsapp=None)))
    _executar(EvolutionFalsa())
    assert repo.enfileirado[0][0]["numero"] is None


def test_domingo_enfileira_para_segunda_as_8h_e_nao_envia(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution, agora=DOMINGO_10H)
    assert repo.dias_lidos == [date(2026, 11, 16)]
    assert repo.enfileirado[0][0]["enviar_apos"] == "2026-11-16T08:00:00-03:00"
    assert resumo["envio"] == {"parou_por": "fora_da_janela"} and evolution.enviados == []


def test_fora_do_horario_enfileira_mas_nao_envia(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution, agora=QUINTA_20H)
    assert repo.enfileirado[0][0]["enviar_apos"] == "2026-11-13T08:00:00-03:00"
    assert resumo["envio"]["parou_por"] == "fora_da_janela" and evolution.enviados == []


# -------------------------------------------------------------------- envio --


def test_envia_registra_e_pausa_entre_mensagens(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1"), _pendente("m2"), _pendente("m3")]))
    evolution, pausas = EvolutionFalsa(), []
    resumo = _executar(evolution, pausas=pausas)
    assert resumo["envio"] == {"enviadas": 3, "ignoradas": 0, "falhas": 0, "parou_por": None}
    assert [e[0] for e in evolution.enviados] == ["5511988887777"] * 3
    assert repo.resultados == [("m1", "enviada", None, "EVO-1"), ("m2", "enviada", None, "EVO-2"), ("m3", "enviada", None, "EVO-3")]
    assert pausas == [30, 30]  # entre as mensagens, não antes da primeira


def test_numero_sem_whatsapp_fica_ignorado(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa(tem_whatsapp=False)
    resumo = _executar(evolution)
    assert resumo["envio"]["ignoradas"] == 1 and evolution.enviados == []
    assert repo.resultados == [("m1", "ignorada", "O número não tem WhatsApp.", None)]


def test_instancia_desconectada_nao_envia_nem_registra_falha(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    resumo = _executar(EvolutionFalsa(estado="close"))
    assert resumo["envio"]["parou_por"] == "instancia_desconectada" and repo.resultados == []


def test_evolution_fora_do_ar_na_conferencia_nao_derruba_a_rodada(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    resumo = _executar(EvolutionFalsa(estado=EvolutionIndisponivel("fora")))
    assert resumo["envio"]["parou_por"] == "evolution_indisponivel" and repo.resultados == []


def test_erro_so_daquela_mensagem_registra_falha_e_segue(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1", "5511900000001"), _pendente("m2")]))
    evolution = EvolutionFalsa(falhas={"5511900000001": ErroEnvio("A Evolution recusou o pedido (400).")})
    resumo = _executar(evolution)
    assert resumo["envio"]["falhas"] == 1 and resumo["envio"]["enviadas"] == 1
    assert repo.resultados[0][:2] == ("m1", "falhou") and repo.resultados[1][:2] == ("m2", "enviada")


def test_evolution_cai_no_meio_registra_falha_e_para(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1", "5511900000001"), _pendente("m2")]))
    evolution = EvolutionFalsa(falhas={"5511900000001": EvolutionIndisponivel("Sem resposta da Evolution (ConnectTimeout).")})
    resumo = _executar(evolution)
    assert resumo["envio"]["parou_por"] == "evolution_indisponivel" and resumo["envio"]["enviadas"] == 0
    assert [r[:2] for r in repo.resultados] == [("m1", "falhou")]  # m2 fica reservada e volta depois


def test_chave_recusada_interrompe_com_erro(instalar):
    instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    with pytest.raises(EvolutionConfiguracaoInvalida):
        _executar(EvolutionFalsa(falhas={"5511988887777": EvolutionConfiguracaoInvalida("chave")}))


def test_o_erro_registrado_nao_leva_o_numero_inteiro(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa(falhas={"5511988887777": ErroEnvio("recusou 5511988887777")})
    _executar(evolution)
    assert "5511988887777" not in repo.resultados[0][2]


# -------------------------------------------------------------- modo teste --


def test_modo_teste_manda_so_para_o_numero_de_teste_com_aviso(instalar):
    repo = instalar(RepoFalso(_bruto(modo_teste=True, numero_teste="5511977776666"), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution)
    numero, texto = evolution.enviados[0]
    assert numero == "5511977776666" and texto.startswith("[TESTE] Esta mensagem iria para 55119****7777.")
    assert texto.endswith("Olá, Maria!")
    assert repo.resultados == [("m1", "enviada", None, "teste:m1")]
    assert resumo["modo_teste"] is True


def test_modo_teste_sem_numero_de_teste_nao_envia(instalar):
    repo = instalar(RepoFalso(_bruto(modo_teste=True, numero_teste=None), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution)
    assert resumo["envio"]["parou_por"] == "modo_teste_sem_numero" and evolution.enviados == [] and repo.resultados == []
    assert repo.enfileirado  # ainda enfileira: o histórico de teste acompanha a cadência real


def test_aceita_fabrica_de_evolution_e_so_cria_quando_ha_o_que_enviar(instalar):
    instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    criou = []

    def fabrica():
        criou.append(True)
        return EvolutionFalsa()

    resumo = _executar(fabrica)
    assert criou == [True] and resumo["envio"]["enviadas"] == 1
    instalar(RepoFalso(_bruto(modo_teste=True, numero_teste=None), [_pendente("m1")]))
    criou.clear()
    _executar(fabrica)
    assert criou == []  # modo teste sem número: nem chega a precisar da Evolution
