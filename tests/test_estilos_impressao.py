"""Folha de impressão: o CSS compilado e versionado precisa trazer o bloco @media print."""

from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_css_compilado_tem_regras_de_impressao_para_papel_claro_e_sem_menus():
    bloco = CSS.split("@media print", 1)[1]
    assert "--fundo:#fff" in bloco and "color-scheme:light" in bloco  # tema escuro vira papel claro
    assert ".lateral" in bloco and ".barra-inferior" in bloco and "dialog" in bloco and "display:none!important" in bloco
