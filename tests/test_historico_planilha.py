"""Planilha de conferência do histórico dos chats: regras puras, montagem do xlsx e leitura (com o banco isolado por mocks)."""

from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook

from src.domain.historico_planilha import COLUNAS, DECISOES, linha_da_planilha, marcas, ordenar, resumo_por_fonte
from src.services import historico_chat as servico

HOJE = date(2026, 11, 25)


def _linha(id_, situacao, fonte="chat_financeiro", tipo="pagamento", data="2026-10-12", **extra):
    return {"id": id_, "fonte": fonte, "tipo": tipo, "data": data, "resumo": f"Registro {id_}", "situacao": situacao, "detalhe": None, "trecho": f"trecho {id_}",
            "lote": "lote-1", "entregue_em": "2026-11-25T10:00:00+00:00", "inferido": None, "faltando": None, "data_estimada": False, **extra}


def _lote(fonte="chat_financeiro", ini="2026-10-01", fim="2026-10-31", rotulo="lote-1", recebidos=10):
    return {"fonte": fonte, "rotulo": rotulo, "periodo_inicio": ini, "periodo_fim": fim, "registros_recebidos": recebidos, "registros_novos": recebidos,
            "entregue_em": "2026-11-25T10:00:00+00:00"}


class TestRegrasPuras:
    def test_ordem_chat_depois_situacao_depois_data(self):
        linhas = [_linha("a", "ja_existe"), _linha("b", "nova", data="2026-10-20"), _linha("c", "diverge"), _linha("d", "nova", data="2026-10-02"),
                  _linha("e", "sem_comparacao"), _linha("f", "diverge", fonte="chat_contratos")]
        assert [x["id"] for x in ordenar(linhas)] == ["f", "c", "d", "b", "e", "a"]  # contratos < financeiro (ordem alfabética do código) e, dentro, a situação

    def test_registro_sem_data_vai_para_o_fim_da_situacao(self):
        assert [x["id"] for x in ordenar([_linha("a", "nova", data=None), _linha("b", "nova", data="2026-10-02")])] == ["b", "a"]

    def test_marcas(self):
        assert marcas({"data_estimada": True, "inferido": "true", "faltando": "valor"}) == "data estimada; inferido; falta: valor"
        assert marcas({"inferido": "a placa"}) == "inferido: a placa" and marcas({}) == ""

    def test_linha_na_ordem_das_colunas_com_decisao_vazia(self):
        v = linha_da_planilha(_linha("x", "diverge", detalhe="No sistema há R$ 275,00."))
        assert len(v) == len(COLUNAS) and v[0] == "x" and v[1] == "Acompanhamento Financeiro" and v[2] == "Pagamento" and v[4] == "Diverge"
        assert v[6] == "No sistema há R$ 275,00." and v[7] == "trecho x" and v[-2] is None and v[-1] is None

    def test_resumo_por_fonte_com_buracos_e_contagens(self):
        lotes = [_lote(ini="2026-08-01", fim="2026-08-31", recebidos=5), _lote(ini="2026-10-01", fim="2026-10-31", rotulo="b", recebidos=7),
                 _lote(fonte="chat_contratos", ini="2026-09-01", fim="2026-09-30", rotulo="c", recebidos=2)]
        linhas = [_linha("1", "nova"), _linha("2", "nova"), _linha("3", "diverge", tipo="despesa"), _linha("4", "nova", fonte="chat_contratos", tipo="contrato")]
        r = {b["fonte"]: b for b in resumo_por_fonte(lotes, linhas)}
        assert r["chat_financeiro"]["registros"] == 12 and r["chat_financeiro"]["buracos"] == [(date(2026, 9, 1), date(2026, 9, 30))]
        assert r["chat_financeiro"]["por_tipo"] == {"pagamento": {"nova": 2}, "despesa": {"diverge": 1}} and r["chat_contratos"]["buracos"] == []


class TestPlanilha:
    def _abrir(self, **kw):
        conferencia = {"total": 3, "linhas": [_linha("a", "ja_existe"), _linha("b", "diverge", detalhe="No sistema há R$ 100,00.", inferido="true"),
                                              _linha("c", "nova", fonte="chat_contratos", tipo="contrato", data=None)]}
        return load_workbook(BytesIO(servico.montar_planilha(conferencia, [_lote(), _lote("chat_contratos", rotulo="c")], HOJE)))

    def test_tres_abas(self):
        assert self._abrir().sheetnames == ["Resumo", "Conferência", "Lotes"]

    def test_aba_de_conferencia(self):
        ws = self._abrir()["Conferência"]
        assert [c.value for c in ws[1]] == list(COLUNAS)
        assert ws.freeze_panes == "A2" and ws.auto_filter.ref.startswith("A1:L")
        ids = [ws.cell(i, 1).value for i in range(2, ws.max_row + 1)]
        assert ids == ["c", "b", "a"]  # contratos primeiro; no financeiro, o que diverge antes do que já existe
        divergente = next(i for i in range(2, ws.max_row + 1) if ws.cell(i, 1).value == "b")
        assert ws.cell(divergente, 5).value == "Diverge" and ws.cell(divergente, 7).value == "No sistema há R$ 100,00." and ws.cell(divergente, 9).value == "inferido"
        assert ws.cell(divergente, 5).fill.fgColor.rgb.endswith("FFF2CC") and ws.cell(divergente, 11).value is None

    def test_coluna_de_decisao_so_aceita_as_opcoes(self):
        ws = self._abrir()["Conferência"]
        (validacao,) = ws.data_validations.dataValidation
        assert validacao.type == "list" and validacao.allow_blank and validacao.showErrorMessage
        for decisao in DECISOES:
            assert decisao in validacao.formula1
        assert str(validacao.sqref).startswith("K2:K")

    def test_aba_de_resumo_traz_periodos_buracos_e_contagens(self):
        textos = [str(c.value) for linha in self._abrir()["Resumo"].iter_rows() for c in linha if c.value is not None]
        junto = " | ".join(textos)
        assert "gerado em 25/11/2026" in junto and "dados pessoais" in junto and "Acompanhamento Financeiro" in junto and "Contratos Locadora" in junto
        assert "01/10/2026 a 31/10/2026" in junto and "nenhum entre o primeiro e o último dia entregues" in junto

    def test_planilha_vazia_nao_quebra(self):
        wb = load_workbook(BytesIO(servico.montar_planilha({"total": 0, "linhas": []}, [], HOJE)))
        assert wb["Conferência"].max_row == 1 and wb.sheetnames == ["Resumo", "Conferência", "Lotes"]

    def test_le_o_repositorio_e_filtra_os_lotes_pela_fonte(self):
        with patch.object(servico.repositorio, "conferencia", return_value={"total": 1, "linhas": [_linha("a", "nova")]}) as conf, \
             patch.object(servico.repositorio, "lotes", return_value=[_lote(), _lote("chat_contratos", rotulo="c")]):
            wb = load_workbook(BytesIO(servico.planilha_de_conferencia("chat_financeiro")))
        assert conf.call_args.args == ("chat_financeiro",)
        assert wb["Lotes"].max_row == 2 and wb["Lotes"].cell(2, 1).value == "chat_financeiro"
