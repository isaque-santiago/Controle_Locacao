"""Testes de src/domain/vistorias.py (Fase 5)."""

from src.domain.vistorias import CHECKLIST_PADRAO, checklist_inicial, comparar_checklists


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
