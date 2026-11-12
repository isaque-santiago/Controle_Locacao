"""Testes de src/domain/arquivos_orfaos.py: tamanho em texto, agrupamento por bucket, lotes e resumo da tela."""

from src.domain.arquivos_orfaos import agrupar_por_bucket, em_lotes, formatar_tamanho, resumir, rotulo_do_bucket

A = {"bucket": "trocas_oleo", "caminho": "c1/a.jpg", "tamanho": 2048, "criado_em": "2026-11-09T10:00:00+00:00"}
B = {"bucket": "documentos", "caminho": "portal/c1/b.pdf", "tamanho": 1048576, "criado_em": "2026-11-09T11:00:00+00:00"}
C = {"bucket": "trocas_oleo", "caminho": "c2/c.jpg", "tamanho": None, "criado_em": "2026-11-09T12:00:00+00:00"}


def test_tamanho_em_texto():
    assert formatar_tamanho(0) == "0 B" and formatar_tamanho(None) == "0 B" and formatar_tamanho(1023) == "1023 B"
    assert formatar_tamanho(1024) == "1,0 KB" and formatar_tamanho(1536) == "1,5 KB"
    assert formatar_tamanho(3 * 1024 * 1024) == "3,0 MB" and formatar_tamanho(5 * 1024 ** 3) == "5,0 GB"
    assert formatar_tamanho(2048 * 1024 ** 3) == "2048,0 GB"


def test_agrupa_por_bucket_na_ordem_e_sem_repetir_caminho():
    grupos = agrupar_por_bucket([A, B, C, A])
    assert list(grupos) == ["trocas_oleo", "documentos"]
    assert grupos["trocas_oleo"] == ["c1/a.jpg", "c2/c.jpg"] and grupos["documentos"] == ["portal/c1/b.pdf"]
    assert dict(agrupar_por_bucket([])) == {}


def test_lotes_de_cem_por_padrao():
    caminhos = [f"c/{i}.jpg" for i in range(250)]
    lotes = em_lotes(caminhos)
    assert [len(l) for l in lotes] == [100, 100, 50] and sum(lotes, []) == caminhos
    assert em_lotes([]) == [] and em_lotes(["a", "b", "c"], 2) == [["a", "b"], ["c"]]


def test_resumo_conta_soma_e_rotula():
    r = resumir([A, B, C])
    assert r["quantidade"] == 3 and r["tamanho"] == "1,0 MB"  # 2 KB + 1 MB, aproximado a uma casa
    assert r["por_bucket"] == [("Fotos de troca de óleo", 2), ("Comprovantes de documentos enviados pelo locatário", 1)]
    assert r["itens"][0]["rotulo"] == "Fotos de troca de óleo" and r["itens"][0]["tamanho_texto"] == "2,0 KB"
    assert r["itens"][2]["tamanho_texto"] == "0 B"


def test_resumo_vazio():
    r = resumir([])
    assert r == {"quantidade": 0, "tamanho": "0 B", "por_bucket": [], "itens": []}


def test_bucket_desconhecido_mostra_o_proprio_nome():
    assert rotulo_do_bucket("outro") == "outro" and rotulo_do_bucket("trocas_oleo") == "Fotos de troca de óleo"
