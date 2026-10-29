"""Folha de impressão: o CSS compilado e versionado precisa trazer o bloco @media print."""

from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_css_compilado_tem_regras_de_impressao_para_papel_claro_e_sem_menus():
    bloco = CSS.split("@media print", 1)[1]
    assert "--fundo:#fff" in bloco and "color-scheme:light" in bloco  # tema escuro vira papel claro
    assert ".lateral" in bloco and ".barra-inferior" in bloco and "dialog" in bloco and "display:none!important" in bloco


def test_impressao_nao_esconde_o_formulario_de_busca_inteiro():
    """O <form role="search"> embrulha a barra de filtros e o #resultado (a lista): escondê-lo sumia com a tabela da folha."""
    bloco = CSS.split("@media print", 1)[1]
    escondidos = bloco.split("{display:none!important}", 1)[0]
    assert "form[role=search] .barra-filtros" in escondidos
    assert "form[role=search]," not in escondidos and not escondidos.endswith("form[role=search]")


def test_impressao_tira_rolagem_e_container_query_da_tabela():
    """Firefox imprime a página só com o título quando a tabela está num contêiner com container-type e rolagem."""
    bloco = CSS.split("@media print", 1)[1]
    assert ".tabela-caixa{overflow:visible!important;container-type:normal!important}" in bloco
