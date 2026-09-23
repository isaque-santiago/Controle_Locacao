from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from src.domain.relatorios import consolidar
from src.domain.valores import decimal_br
from src.services.relatorios import exportar_csv, exportar_excel
from src.services import configuracoes
from src.repositories import consultas


@pytest.mark.parametrize(
    "texto,esperado",
    [("1.234,56", "1234.56"), ("0,10", "0.10"), ("1234.56", "1234.56")],
)
def test_valor_br(texto, esperado):
    assert decimal_br(texto) == Decimal(esperado)


@pytest.mark.parametrize("texto", ["NaN", "Infinity", "-1", "1,001", "texto"])
def test_valores_invalidos(texto):
    with pytest.raises(ValueError):
        decimal_br(texto)


def test_resultado_exclui_caucao_e_nao_duplica_receita():
    resultado = consolidar(
        [{"id": "m", "placa": "ABC1D23", "modelo": "CG"}],
        [{"id": "c", "moto_id": "m"}],
        [
            {"id": "parcela", "contrato_id": "c", "tipo": "locacao"},
            {"id": "caucao", "contrato_id": "c", "tipo": "caucao"},
        ],
        [
            {
                "cobranca_id": "parcela",
                "valor": "100.10",
                "multa_juros": "2.00",
                "data_pagamento": "2026-09-10",
            },
            {
                "cobranca_id": "caucao",
                "valor": "500",
                "multa_juros": 0,
                "data_pagamento": "2026-09-10",
            },
        ],
        [
            {
                "moto_id": "m",
                "status": "concluida",
                "data_entrada": "2026-09-10",
                "custo_total": "20.10",
            },
            {
                "moto_id": "m",
                "status": "cancelada",
                "data_entrada": "2026-09-10",
                "custo_total": "999",
            },
        ],
        [
            {
                "moto_id": "m",
                "regularizado": True,
                "data_regularizacao": "2026-09-11",
                "valor": "12",
            }
        ],
        [
            {"moto_id": "m", "data": "2026-08-31", "km": 100},
            {"moto_id": "m", "data": "2026-09-20", "km": 200},
        ],
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    linha = resultado["resultado"][0]
    assert linha["receita_recebida"] == Decimal("102.10")
    assert linha["resultado"] == Decimal("70.00")
    assert linha["km_rodados"] == 100
    assert linha["custo_por_km"] == Decimal("0.20")
    assert resultado["fluxo"][0]["resultado"] == Decimal("70.00")


def test_exportacao_preserva_acentos_valores_e_neutraliza_formulas():
    linhas = [{"descrição": "=1+1", "valor": Decimal("1234.56")}]
    csv = exportar_csv(linhas).decode("utf-8-sig")
    assert "descrição" in csv and "1234,56" in csv and "'=1+1" in csv
    livro = load_workbook(BytesIO(exportar_excel(linhas)))
    assert livro.active["A2"].data_type == "s"
    assert livro.active["B2"].value == 1234.56


def test_backup_contem_todas_tabelas(monkeypatch):
    monkeypatch.setattr(
        configuracoes,
        "todos",
        lambda nome, **_: [{"id": "1", "nome": "João"}] if nome == "clientes" else [],
    )
    with ZipFile(BytesIO(configuracoes.backup())) as arquivo:
        assert all(t + ".csv" in arquivo.namelist() for t in configuracoes.TABELAS)
        assert "João" in arquivo.read("clientes.csv").decode("utf-8-sig")


def test_paginacao_continua_mesmo_com_limite_menor_do_servidor(monkeypatch):
    class Consulta:
        def table(self, *_):
            return self

        def select(self, *_):
            return self

        def order(self, *_):
            return self

        def range(self, inicio, fim):
            self.inicio = inicio
            return self

        def execute(self):
            from types import SimpleNamespace

            return SimpleNamespace(
                data=list(range(1200))[self.inicio : self.inicio + 100]
            )

    monkeypatch.setattr(consultas, "get_client", lambda: Consulta())
    assert consultas.todos("motos") == list(range(1200))


def test_leitura_usa_cache_e_escrita_invalida(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        consultas,
        "_ler_todos",
        lambda tabela, ordem, selecao, filtros: chamadas.append(tabela) or [1],
    )
    consultas.limpar_cache()

    assert consultas.todos("tabela_cache") == [1]
    assert consultas.todos("tabela_cache") == [1]
    assert chamadas == ["tabela_cache"]

    @consultas.invalida_cache
    def escrever():
        return "ok"

    assert escrever() == "ok"
    consultas.todos("tabela_cache")
    assert chamadas == ["tabela_cache", "tabela_cache"]

    consultas.todos("tabela_cache", usar_cache=False)
    assert len(chamadas) == 3
    consultas.limpar_cache()


def test_ordem_composta_nao_acrescenta_id(monkeypatch):
    ordens = []

    class Consulta:
        def table(self, *_):
            return self

        def select(self, *_):
            return self

        def order(self, coluna):
            ordens.append(coluna)
            return self

        def range(self, *_):
            return self

        def execute(self):
            from types import SimpleNamespace

            return SimpleNamespace(data=[])

    monkeypatch.setattr(consultas, "get_client", lambda: Consulta())
    consultas.todos("vw_sem_id", ("moto_id", "item_id"), usar_cache=False)
    assert ordens == ["moto_id", "item_id"]
    ordens.clear()
    consultas.todos("motos", "placa", usar_cache=False)
    assert ordens == ["placa", "id"]


def test_geracao_de_cobrancas_roda_no_maximo_uma_vez_por_hora(monkeypatch):
    from src.services import cobrancas

    chamadas = []
    relogio = [100.0]
    monkeypatch.setattr(
        cobrancas.cobrancas,
        "gerar_pendentes_via_rpc",
        lambda horizonte: chamadas.append(horizonte) or {"cobrancas_geradas": 2},
    )
    monkeypatch.setattr(cobrancas, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(cobrancas.st, "session_state", {})

    assert cobrancas.gerar_cobrancas_pendentes() == {"cobrancas_geradas": 2}
    assert cobrancas.gerar_cobrancas_pendentes() == {"cobrancas_geradas": 0}
    assert len(chamadas) == 1

    relogio[0] += cobrancas._INTERVALO_GERACAO_SEGUNDOS + 1
    cobrancas.gerar_cobrancas_pendentes()
    assert len(chamadas) == 2
