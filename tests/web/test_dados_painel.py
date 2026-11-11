"""`dados_painel.carregar` de verdade: cada aba lê só o que mostra e junta tudo no dicionário da tela."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.domain.painel import ItemAlerta
from src.web import dados_painel

HOJE = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def dados_painel_falsos():
    """Aqui o que se testa é o `carregar` de verdade: este teste desliga o `carregar` fictício do conftest."""


def _instalar(monkeypatch, config=None, alertas_zap=None, hoje=None, dinheiro=None, frota=None, motos=None, ordens=None, comprovantes=None):
    chamadas = {"gerar": 0, "hoje": 0, "dinheiro": [], "frota": 0, "alertas_zap": []}
    config = config or {"alerta_manutencao_km": 300, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30}

    def gerar():
        chamadas["gerar"] += 1

    def painel_hoje(h):
        chamadas["hoje"] += 1
        return hoje if hoje is not None else {
            "mes_texto": "2026-11", "cobranca": {"linhas": []}, "atencao_financeira": [
                ItemAlerta(1, "Parcela de dívida atrasada", "R$ 1.000,00 em atraso", "perigo", "dividas")]}

    def painel_dinheiro(mes, h):
        chamadas["dinheiro"].append(mes)
        return dinheiro if dinheiro is not None else {"mes_texto": "2026-10", "mes_anterior": "2026-09", "mes_seguinte": "2026-11"}

    def painel_frota(h):
        chamadas["frota"] += 1
        return frota if frota is not None else {"veiculos": [], "manutencao_mes": Decimal("10.00")}

    monkeypatch.setattr(dados_painel, "cobrancas", SimpleNamespace(gerar_cobrancas_pendentes=gerar))
    monkeypatch.setattr(dados_painel, "financeiro_servico", SimpleNamespace(
        painel_hoje_seguro=painel_hoje, painel_dinheiro_seguro=painel_dinheiro, painel_frota_seguro=painel_frota))
    monkeypatch.setattr(dados_painel, "motos", SimpleNamespace(listar=lambda: motos if motos is not None else [
        {"id": "m1", "status": "alugada"}, {"id": "m2", "status": "disponivel"}, {"id": "m3", "status": "manutencao"}]))
    monkeypatch.setattr(dados_painel, "manutencao", SimpleNamespace(listar_manutencoes=lambda: ordens or []))
    monkeypatch.setattr(dados_painel, "alertas", SimpleNamespace(listar_manutencao=lambda: [], listar_documentos=lambda: [], listar_cnh=lambda: []))
    monkeypatch.setattr(dados_painel, "configuracoes", SimpleNamespace(obter=lambda: config))
    monkeypatch.setattr(dados_painel, "documentos", SimpleNamespace(alertas_de_comprovantes=lambda: comprovantes or []))
    monkeypatch.setattr(dados_painel, "whatsapp_painel", SimpleNamespace(
        alertas=lambda c: chamadas["alertas_zap"].append(c) or (alertas_zap or [])))
    return chamadas


def test_so_a_aba_pedida_e_lida_e_hoje_e_o_padrao(monkeypatch):
    chamadas = _instalar(monkeypatch)
    d = dados_painel.carregar(HOJE)
    assert d["aba"] == "hoje" and "hoje" in d and "dinheiro" not in d and "frota" not in d
    assert chamadas["gerar"] == 1 and chamadas["hoje"] == 1 and chamadas["dinheiro"] == [] and chamadas["frota"] == 0

    chamadas = _instalar(monkeypatch)
    d = dados_painel.carregar(HOJE, aba="dinheiro", mes="2026-08")
    assert d["aba"] == "dinheiro" and "dinheiro" in d and "hoje" not in d and chamadas["dinheiro"] == ["2026-08"] and chamadas["hoje"] == 0

    chamadas = _instalar(monkeypatch)
    d = dados_painel.carregar(HOJE, aba="frota")
    assert d["aba"] == "frota" and "frota" in d and chamadas["frota"] == 1 and chamadas["hoje"] == 0


def test_aba_desconhecida_vale_hoje(monkeypatch):
    _instalar(monkeypatch)
    assert dados_painel.carregar(HOJE, aba="relatorios")["aba"] == "hoje"


def test_cabecalho_comum_com_data_abas_e_modos(monkeypatch):
    _instalar(monkeypatch)
    d = dados_painel.carregar(HOJE, compacto=True, ocultar=True, aba="frota")
    assert d["data_extenso"].startswith("terça-feira, 10 de novembro de 2026") and d["compacto"] is True and d["ocultar"] is True
    assert [(a["chave"], a["rotulo"], a["ativa"]) for a in d["abas"]] == [("hoje", "Hoje", False), ("dinheiro", "Dinheiro", False), ("frota", "Frota", True)]
    assert d["abas"][0]["href"] == "/?compacto=1&ocultar=1" and d["abas"][1]["href"] == "/?aba=dinheiro&compacto=1&ocultar=1"
    assert d["links"]["compacto"] == "?aba=frota&ocultar=1" and d["links"]["ocultar"] == "?aba=frota&compacto=1"


def test_a_navegacao_de_mes_so_existe_na_aba_dinheiro(monkeypatch):
    _instalar(monkeypatch)
    d = dados_painel.carregar(HOJE, aba="dinheiro", compacto=True)
    assert d["links"]["anterior"] == "?aba=dinheiro&mes=2026-09&compacto=1" and d["links"]["seguinte"] == "?aba=dinheiro&mes=2026-11&compacto=1"
    assert d["links"]["compacto"] == "?aba=dinheiro&mes=2026-10"
    for aba in ("hoje", "frota"):
        links = dados_painel.carregar(HOJE, aba=aba)["links"]
        assert links["anterior"] is None and links["seguinte"] is None and "mes=" not in links["compacto"]


def test_atencao_junta_manutencao_documentos_cnh_whatsapp_e_o_dinheiro_com_o_perigo_na_frente(monkeypatch):
    zap = ItemAlerta(2, "Mensagens sem entrega", "Maria: inválido.", "atencao", "mensagens")
    chamadas = _instalar(monkeypatch, alertas_zap=[zap], hoje={
        "mes_texto": "2026-11", "cobranca": {"linhas": []},
        "atencao_financeira": [ItemAlerta(None, "Despesa a repassar ao locatário", "R$ 40,00", "atencao", None),
                               ItemAlerta(1, "Parcela de dívida atrasada", "R$ 1.000,00 em atraso", "perigo", "dividas")]})
    d = dados_painel.carregar(HOJE)
    assert [a.titulo for a in d["hoje"]["atencao"]] == ["Parcela de dívida atrasada", "Mensagens sem entrega", "Despesa a repassar ao locatário"]
    assert chamadas["alertas_zap"] == [{"alerta_manutencao_km": 300, "alerta_manutencao_dias": 15, "alerta_documento_dias": 30}]


def test_hoje_indisponivel_ainda_traz_os_alertas_operacionais(monkeypatch):
    zap = ItemAlerta(1, "WhatsApp em modo teste", "só teste", "atencao", "configuracoes")
    _instalar(monkeypatch, alertas_zap=[zap], hoje={"mes_texto": "2026-11", "indisponivel": True})
    d = dados_painel.carregar(HOJE)
    assert d["hoje"]["indisponivel"] is True and d["hoje"]["atencao"] == [zap]


def test_frota_monta_ocupacao_rosca_legenda_e_manutencao(monkeypatch):
    ordens = [{"status": "concluida", "data_entrada": "2026-11-03", "custo_total": "100"},
              {"status": "aberta", "data_entrada": "2026-11-08", "custo_total": "290"}]
    _instalar(monkeypatch, ordens=ordens)
    f = dados_painel.carregar(HOJE, aba="frota")["frota"]
    assert f["total"] == 3 and f["ativas"] == 3 and f["ocupacao"] == 33 and f["contagem"]["manutencao"] == 1
    assert f["ordens_concluidas"] == 1 and f["manutencao_aberta"] == {"quantidade": 1, "total": Decimal("290")}
    assert f["rosca"] and f["legenda"] and "3 motos" in f["descricao_medidor"]
    assert f["manutencao_mes"] == Decimal("10.00") and f["veiculos"] == []


def test_comprovante_a_conferir_entra_na_lista_de_atencao_da_aba_hoje(monkeypatch):
    item = ItemAlerta(1, "Comprovante a conferir", "Maria · IPVA 2026 · ABC1D23", "atencao", "documentos")
    _instalar(monkeypatch, comprovantes=[item])
    titulos = [i.titulo for i in dados_painel.carregar(HOJE)["hoje"]["atencao"]]
    assert "Comprovante a conferir" in titulos
    _instalar(monkeypatch)
    assert "Comprovante a conferir" not in [i.titulo for i in dados_painel.carregar(HOJE)["hoje"]["atencao"]]

