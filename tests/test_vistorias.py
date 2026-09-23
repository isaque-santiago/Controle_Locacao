"""Testes de src/domain/vistorias.py (Fase 5)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.domain.vistorias import (
    CHECKLIST_PADRAO,
    checklist_inicial,
    comparar_checklists,
    contar_avarias,
    filtrar_por_tipo,
    instante_da_vistoria,
    itens_ordenados,
    km_rodados,
    resumo_avarias,
    rotulo_item,
    tipos_faltantes,
)


class TestChecklistInicial:
    def test_contem_todos_os_itens_padrao_marcados_ok(self):
        checklist = checklist_inicial()
        assert set(checklist) == set(CHECKLIST_PADRAO)
        assert all(valor == "ok" for valor in checklist.values())


class TestCompararChecklists:
    def test_sem_diferencas_retorna_vazio(self):
        checklist = checklist_inicial()
        assert comparar_checklists(checklist, dict(checklist)) == {}

    def test_item_avariado_na_devolucao(self):
        entrega = checklist_inicial()
        devolucao = dict(entrega, freio_dianteiro="avaria")
        diferencas = comparar_checklists(entrega, devolucao)
        assert diferencas == {
            "freio_dianteiro": {"entrega": "ok", "devolucao": "avaria"}
        }

    def test_varios_itens_diferentes(self):
        entrega = checklist_inicial()
        devolucao = dict(entrega, pneu_dianteiro="gasto", retrovisores="quebrado")
        diferencas = comparar_checklists(entrega, devolucao)
        assert set(diferencas) == {"pneu_dianteiro", "retrovisores"}

    def test_item_presente_so_na_devolucao(self):
        entrega = {"farol_dianteiro": "ok"}
        devolucao = {"farol_dianteiro": "ok", "extra": "avaria"}
        diferencas = comparar_checklists(entrega, devolucao)
        assert diferencas == {"extra": {"entrega": None, "devolucao": "avaria"}}

    def test_checklists_vazios_ou_nulos(self):
        assert comparar_checklists({}, {}) == {}
        assert comparar_checklists(None, None) == {}


class TestRotuloEOrdem:
    def test_rotulo_troca_underline_e_capitaliza(self):
        assert rotulo_item("freio_dianteiro") == "Freio dianteiro"
        assert rotulo_item("Kit ferramentas") == "Kit ferramentas"

    def test_rotulos_padrao_com_acento(self):
        assert rotulo_item("documentos_do_veiculo") == "Documentos do veículo"
        assert rotulo_item("pisca_alerta") == "Pisca-alerta"
        assert all(rotulo_item(c)[0].isupper() for c in CHECKLIST_PADRAO)

    def test_padrao_primeiro_na_ordem_do_padrao_e_extras_depois(self):
        checklist = {"zebra": "ok", "buzina": "ok", "farol_dianteiro": "avaria", "alfa": "ausente"}
        assert [c for c, _ in itens_ordenados(checklist)] == [
            "farol_dianteiro",
            "buzina",
            "alfa",
            "zebra",
        ]

    def test_ordem_com_checklist_nulo(self):
        assert itens_ordenados(None) == []


class TestAvarias:
    def test_conta_itens_marcados_como_avaria(self):
        vistoria = {"checklist": {"buzina": "avaria", "banco": "avaria", "capacete": "ok"}}
        assert contar_avarias(vistoria) == 2

    def test_so_descricao_conta_como_uma(self):
        assert contar_avarias({"checklist": {"buzina": "ok"}, "avarias": "Risco no tanque"}) == 1

    def test_sem_avarias(self):
        assert contar_avarias({"checklist": {"buzina": "ok"}, "avarias": "  "}) == 0
        assert contar_avarias(None) == 0

    def test_resumo_prefere_a_descricao_digitada(self):
        vistoria = {"avarias": " Retrovisor trincado ", "checklist": {"retrovisores": "avaria"}}
        assert resumo_avarias(vistoria) == "Retrovisor trincado"

    def test_resumo_usa_os_itens_na_falta_de_descricao(self):
        vistoria = {"avarias": None, "checklist": {"retrovisores": "avaria", "buzina": "avaria"}}
        assert resumo_avarias(vistoria) == "Retrovisores, Buzina"

    def test_resumo_none_sem_avaria(self):
        assert resumo_avarias({"avarias": "", "checklist": {"buzina": "ok"}}) is None


class TestKmRodados:
    def test_diferenca_entre_devolucao_e_entrega(self):
        assert km_rodados({"km": 38500}, {"km": 41020}) == 2520

    def test_none_enquanto_falta_uma_vistoria(self):
        assert km_rodados({"km": 1}, None) is None
        assert km_rodados(None, {"km": 1}) is None


class TestFiltroETipos:
    REGISTROS = [{"tipo": "entrega"}, {"tipo": "devolucao"}, {"tipo": "entrega"}]

    def test_todas_devolve_tudo(self):
        assert filtrar_por_tipo(self.REGISTROS, "todas") == self.REGISTROS

    def test_filtra_pelo_tipo(self):
        assert len(filtrar_por_tipo(self.REGISTROS, "entrega")) == 2
        assert len(filtrar_por_tipo(self.REGISTROS, "devolucao")) == 1

    def test_tipos_faltantes(self):
        assert tipos_faltantes([]) == ["entrega", "devolucao"]
        assert tipos_faltantes([{"tipo": "entrega"}]) == ["devolucao"]
        assert tipos_faltantes([{"tipo": "entrega"}, {"tipo": "devolucao"}]) == []


class TestInstanteDaVistoria:
    FUSO = ZoneInfo("America/Sao_Paulo")

    def test_hoje_usa_o_momento_atual(self):
        agora = datetime(2026, 9, 23, 15, 30, tzinfo=self.FUSO)
        assert instante_da_vistoria(date(2026, 9, 23), agora) == agora

    def test_dia_passado_vira_meio_dia_local(self):
        agora = datetime(2026, 9, 23, 15, 30, tzinfo=self.FUSO)
        instante = instante_da_vistoria(date(2026, 9, 20), agora)
        assert instante == datetime(2026, 9, 20, 12, 0, tzinfo=self.FUSO)
        assert instante.astimezone(self.FUSO).date() == date(2026, 9, 20)

    def test_agora_em_utc_perto_da_meia_noite_compara_no_fuso_local(self):
        # 01:00 UTC de 24/09 ainda é 22:00 de 23/09 em São Paulo.
        agora = datetime(2026, 9, 24, 1, 0, tzinfo=ZoneInfo("UTC"))
        instante = instante_da_vistoria(date(2026, 9, 23), agora)
        assert instante == agora
