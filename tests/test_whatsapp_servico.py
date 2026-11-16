"""Testes de src/services/whatsapp.py com repositório e Evolution falsos: enfileira, respeita a janela e o modo teste."""

from datetime import date, datetime

import pytest

from src.domain.janela_envio import FUSO
from src.domain.textos_whatsapp import OpcoesTexto
from src.services import whatsapp
from src.services.evolution import ErroEnvio, EvolutionConfiguracaoInvalida, EvolutionIndisponivel

OP = OpcoesTexto(empresa="LA Motos", contato="o Alisson")
QUINTA_11H40 = datetime(2026, 11, 12, 11, 40, tzinfo=FUSO)  # dentro do disparo das 11:30
QUINTA_20H = datetime(2026, 11, 12, 20, 0, tzinfo=FUSO)
DOMINGO_10H = datetime(2026, 11, 15, 10, 0, tzinfo=FUSO)


GRUPO = "120363025246125486@g.us"


def _bruto(ativo=True, modo_teste=False, numero_teste=None, grupo=GRUPO):
    return {
        "config": {"ativo": ativo, "modo_teste": modo_teste, "numero_teste": numero_teste, "max_repeticoes": 10,
                   "dias_inadimplencia": 15, "multa_atraso": "15.00", "encargo_diario": "7.00"},
        "cobrancas": [{"id": "cob-1", "cliente_id": "cli-1", "tipo": "locacao", "vencimento": "2026-11-10", "saldo": "450.00",
                       "periodicidade": "semanal", "situacao": "atrasada", "placa": "ABC1D23"}],
        "pagamentos": [], "cnhs": [], "documentos": [], "oleo": [], "portal": [],
        "clientes": [{"id": "cli-1", "nome": "Maria Souza", "whatsapp": "(11) 98888-7777", "whatsapp_grupo_id": grupo}],
        "historico": [],
    }


class RepoFalso:
    def __init__(self, bruto, pendentes=()):
        self.bruto, self.pendentes = bruto, list(pendentes)
        self.dias_lidos, self.enfileirado, self.resultados, self.rodadas = [], [], [], []
        self.falha_ao_registrar_rodada = False
        self.grupos_gravados = []

    def gravar_grupos(self, grupos):
        self.grupos_gravados.append(grupos)
        return len(grupos)

    def dados(self, dia):
        self.dias_lidos.append(dia)
        return self.bruto

    def enfileirar(self, mensagens):
        self.enfileirado.append(mensagens)
        return {"enfileiradas": len(mensagens), "sem_numero": 0, "duplicadas": 0, "bloqueadas": 0}

    def reservar(self, limite):
        return self.pendentes[:limite]

    def registrar_rodada(self, estado, resumo=None):
        if self.falha_ao_registrar_rodada:
            raise RuntimeError("banco fora do ar")
        self.rodadas.append((estado, resumo))

    def registrar_resultado(self, mensagem_id, resultado, erro=None, evolution_id=None):
        self.resultados.append((mensagem_id, resultado, erro, evolution_id))
        return {}


class EvolutionFalsa:
    def __init__(self, estado="open", tem_whatsapp=True, falhas=None):
        self._estado, self._tem, self._falhas = estado, tem_whatsapp, falhas or {}
        self.enviados = []
        self.verificados = []
        self.grupos = [{"id": GRUPO, "nome": "Maria Souza - ABC1D23", "participantes": 5}]
        self.erro_nos_grupos = None

    def listar_grupos(self):
        if self.erro_nos_grupos:
            raise self.erro_nos_grupos
        return self.grupos

    def estado(self):
        if isinstance(self._estado, Exception):
            raise self._estado
        return self._estado

    def numero_tem_whatsapp(self, numero):
        self.verificados.append(numero)
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


def _executar(evolution, agora=QUINTA_11H40, pausas=None):
    pausas = pausas if pausas is not None else []
    return whatsapp.executar(evolution, OP, agora, dormir=pausas.append, sorteio=lambda a, b: 30)


# ------------------------------------------------------------------- grupo --


def test_so_cobrancas_e_recibos_sao_enfileirados(instalar):
    bruto = _bruto()
    bruto["cnhs"] = [{"cliente_id": "cli-1", "cnh_validade": "2026-11-20", "situacao": "proxima"}]
    bruto["portal"] = [{"tipo": "portal_acesso", "cliente_id": "cli-1", "referencia_id": "u1", "ocorrido_em": "2026-11-12"}]
    repo = instalar(RepoFalso(bruto))
    _executar(EvolutionFalsa())
    tipos = {i["tipo"] for m in repo.enfileirado[0] for i in m["itens"]}
    assert tipos == {"atraso"}  # CNH e portal ficam fora (decisão do dono, 17/11/2026)


def test_envio_ao_grupo_nao_confere_se_o_numero_tem_whatsapp(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1", numero=GRUPO)]))
    evolution = EvolutionFalsa(tem_whatsapp=False)  # se conferisse, a mensagem ficaria ignorada
    resumo = _executar(evolution)
    assert evolution.enviados[0][0] == GRUPO and evolution.verificados == []
    assert repo.resultados == [("m1", "enviada", None, "EVO-1")] and resumo["envio"]["enviadas"] == 1


def test_modo_teste_com_pendente_de_grupo_avisa_sem_mostrar_o_id(instalar):
    repo = instalar(RepoFalso(_bruto(modo_teste=True, numero_teste="5511977776666"), [_pendente("m1", numero=GRUPO)]))
    evolution = EvolutionFalsa()
    _executar(evolution)
    numero, texto = evolution.enviados[0]
    assert numero == "5511977776666" and texto.startswith("[TESTE] Esta mensagem iria para o grupo do cliente.")
    assert GRUPO not in texto and evolution.verificados == ["5511977776666"]  # o número de teste é individual: confere


def test_a_rodada_atualiza_a_lista_de_grupos_com_a_instancia_conectada(instalar):
    repo = instalar(RepoFalso(_bruto()))
    resumo = _executar(EvolutionFalsa())
    assert resumo["grupos"] == 1 and repo.grupos_gravados == [[{"id": GRUPO, "nome": "Maria Souza - ABC1D23", "participantes": 5}]]


def test_instancia_desconectada_nao_atualiza_os_grupos(instalar):
    repo = instalar(RepoFalso(_bruto()))
    resumo = _executar(EvolutionFalsa(estado="close"))
    assert "grupos" not in resumo and repo.grupos_gravados == []


def test_falha_ao_listar_grupos_nao_derruba_a_rodada(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1", numero=GRUPO)]))
    evolution = EvolutionFalsa()
    evolution.erro_nos_grupos = RuntimeError("fora do ar")
    resumo = _executar(evolution)
    assert resumo["grupos"] is None and resumo["envio"]["enviadas"] == 1 and repo.rodadas


# ---------------------------------------------------------------- desligado --


def test_envio_desligado_nao_enfileira_nem_envia(instalar):
    repo = instalar(RepoFalso(_bruto(ativo=False), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    assert _executar(evolution) == {"ativo": False}
    assert repo.enfileirado == [] and repo.resultados == [] and evolution.enviados == []


# ---------------------------------------------------------------- enfileirar --


def test_enfileira_a_mensagem_devida_para_o_grupo_do_cliente(instalar):
    repo = instalar(RepoFalso(_bruto()))
    resumo = _executar(EvolutionFalsa())
    assert resumo["fila"]["enfileiradas"] == 1
    mensagem = repo.enfileirado[0][0]
    assert mensagem["cliente_id"] == "cli-1" and mensagem["numero"] == GRUPO
    assert mensagem["itens"][0]["tipo"] == "atraso" and mensagem["itens"][0]["data_referencia"] == "2026-11-12"
    assert "Olá, Maria!" in mensagem["texto"] and "R$" in mensagem["texto"]


def test_sem_nada_devido_nao_chama_a_fila(instalar):
    bruto = _bruto()
    bruto["cobrancas"] = []
    repo = instalar(RepoFalso(bruto))
    assert _executar(EvolutionFalsa())["fila"]["enfileiradas"] == 0
    assert repo.enfileirado == []


def test_cliente_sem_grupo_vai_sem_destino_mesmo_com_numero_individual(instalar):
    repo = instalar(RepoFalso(_bruto(grupo=None)))
    _executar(EvolutionFalsa())
    assert repo.enfileirado[0][0]["numero"] is None


def test_domingo_enfileira_para_segunda_as_7h30_e_nao_envia(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution, agora=DOMINGO_10H)
    assert repo.dias_lidos == [date(2026, 11, 16)]
    assert repo.enfileirado[0][0]["enviar_apos"] == "2026-11-16T07:30:00-03:00"
    assert resumo["envio"] == {"parou_por": "fora_da_janela"} and evolution.enviados == []


def test_fora_do_horario_enfileira_mas_nao_envia(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    evolution = EvolutionFalsa()
    resumo = _executar(evolution, agora=QUINTA_20H)
    assert repo.enfileirado[0][0]["enviar_apos"] == "2026-11-13T07:30:00-03:00"
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


def test_aceita_fabrica_de_evolution_e_so_a_cria_com_o_envio_ligado(instalar):
    criou = []

    def fabrica():
        criou.append(True)
        return EvolutionFalsa()

    instalar(RepoFalso(_bruto(ativo=False)))
    _executar(fabrica)
    assert criou == []  # desligado: nem precisa da Evolution
    instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    resumo = _executar(fabrica)
    assert criou == [True] and resumo["envio"]["enviadas"] == 1


def test_grava_o_estado_da_instancia_a_cada_rodada_mesmo_fora_da_janela(instalar):
    repo = instalar(RepoFalso(_bruto()))
    _executar(EvolutionFalsa(estado="open"), agora=DOMINGO_10H)
    assert [r[0] for r in repo.rodadas] == ["open"]
    assert repo.rodadas[0][1]["envio"] == {"parou_por": "fora_da_janela"}


def test_grava_instancia_desconectada_e_indisponivel(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    _executar(EvolutionFalsa(estado="close"))
    _executar(EvolutionFalsa(estado=EvolutionIndisponivel("fora")))
    assert [r[0] for r in repo.rodadas] == ["close", "indisponivel"]


def test_falha_ao_gravar_o_estado_nao_derruba_a_rodada(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1")]))
    repo.falha_ao_registrar_rodada = True
    resumo = _executar(EvolutionFalsa())
    assert resumo["envio"]["enviadas"] == 1


# ----------------------------------------------------- reserva e orçamento de tempo --


def test_lote_pequeno_cabe_na_reserva_mesmo_no_pior_caso():
    """O pior caso de uma rodada (todas as pausas no máximo e as duas chamadas de cada mensagem estourando o tempo) tem de
    caber na reserva do banco, senão a rodada seguinte poderia pegar as mesmas mensagens."""
    pior = (whatsapp.LOTE - 1) * whatsapp.PAUSA_MAXIMA + whatsapp.LOTE * whatsapp.PIOR_CASO_POR_MENSAGEM
    assert pior <= whatsapp.RESERVA_SEGUNDOS - whatsapp.MARGEM_SEGUNDOS


def test_reserva_do_codigo_e_a_mesma_do_banco():
    import re
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20261106120000_whatsapp_base.sql").read_text(encoding="utf-8")
    minutos = int(re.search(r"reservada_ate = now\(\) \+ interval '(\d+) minutes'", sql).group(1))
    assert minutos * 60 == whatsapp.RESERVA_SEGUNDOS


def test_reserva_so_o_tamanho_do_lote(instalar):
    pedidos = []

    class Repo(RepoFalso):
        def reservar(self, limite):
            pedidos.append(limite)
            return super().reservar(limite)

    instalar(Repo(_bruto(), []))
    _executar(EvolutionFalsa())
    assert pedidos == [whatsapp.LOTE] and whatsapp.LOTE <= 5


def test_para_de_enviar_quando_o_tempo_da_reserva_acabaria(instalar):
    """Evolution lenta: com o relógio andando mais que o previsto, a rodada para antes de estourar a reserva."""
    repo = instalar(RepoFalso(_bruto(), [_pendente(f"m{i}") for i in range(5)]))
    evolution = EvolutionFalsa()
    relogio_atual = [0.0]

    def dormir(segundos):
        relogio_atual[0] += segundos + 200  # cada pausa "demora" 200 s a mais (simula tudo lento)

    resumo = whatsapp.enviar_pendentes(
        evolution, {"modo_teste": False, "numero_teste": None}, "open",
        dormir=dormir, sorteio=lambda a, b: 30, relogio=lambda: relogio_atual[0])
    assert resumo["parou_por"] == "tempo_esgotado"
    assert 1 <= resumo["enviadas"] < 5 and len(evolution.enviados) == resumo["enviadas"]
    assert len(repo.resultados) == resumo["enviadas"]  # as não enviadas nem foram registradas: voltam à fila sozinhas


def test_sem_lentidao_o_orcamento_nao_interfere(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente(f"m{i}") for i in range(5)]))
    resumo = whatsapp.enviar_pendentes(EvolutionFalsa(), {"modo_teste": False, "numero_teste": None}, "open",
                                       dormir=lambda s: None, sorteio=lambda a, b: 30, relogio=lambda: 0.0)
    assert resumo["enviadas"] == 5 and resumo["parou_por"] is None and len(repo.resultados) == 5


def test_limite_de_requisicoes_para_a_rodada_e_devolve_a_mensagem_a_fila(instalar):
    repo = instalar(RepoFalso(_bruto(), [_pendente("m1", "5511900000001"), _pendente("m2")]))
    evolution = EvolutionFalsa(falhas={"5511900000001": EvolutionIndisponivel("A Evolution pediu para tentar depois (429).")})
    resumo = _executar(evolution)
    assert resumo["envio"]["parou_por"] == "evolution_indisponivel" and resumo["envio"]["enviadas"] == 0
    assert [r[:2] for r in repo.resultados] == [("m1", "falhou")]  # volta para a fila com espera; m2 nem foi tentada
