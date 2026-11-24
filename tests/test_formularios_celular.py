"""Fase 6 do redesign (formulários e celular): seções, validação imediata e contratos de CSS/JS.

Sem navegador nos testes unitários: renderiza os templates com o Jinja do app e confere o texto do JS e do CSS."""

import re
from pathlib import Path

from src.web.templates import templates

RAIZ = Path(__file__).resolve().parents[1]
JS = (RAIZ / "static" / "js" / "app.js").read_text(encoding="utf-8")
CSS = (RAIZ / "src" / "web" / "estilos" / "app.css").read_text(encoding="utf-8")
CSS_GERADO = (RAIZ / "static" / "css" / "app.css").read_text(encoding="utf-8")

CAMPOS_MOTO = {
    "placa", "renavam", "marca", "modelo", "chassi", "motor", "cor", "combustivel", "ano_fabricacao", "ano_modelo",
    "km_atual", "valor_aquisicao", "valor_locacao_sugerido", "data_aquisicao", "observacoes",
}


def _moto(nova=True, erros=None):
    valores = {c: "" for c in CAMPOS_MOTO}
    return templates.env.get_template("motos/_form_moto.html").render(
        valores=valores, erros=erros or {}, nova=nova, acao="/motos/nova", csrf_token="t", erro_geral="")


def test_macro_secao_gera_grupo_nomeado_com_titulo_e_grade():
    html = templates.env.from_string(
        '{% from "componentes/macros.html" import secao %}{% call secao("Aquisição", "Dados da compra.") %}<i>x</i>{% endcall %}'
    ).render()
    assert 'data-secao' in html and 'aria-labelledby="sec-aquisição"' in html
    assert '<h3 id="sec-aquisição">Aquisição</h3>' in html
    assert "Dados da compra." in html and 'class="form-secao-grade"' in html and "<i>x</i>" in html


def test_novo_veiculo_agrupa_em_tres_secoes_sem_perder_nenhum_campo():
    html = _moto()
    titulos = re.findall(r'<h3 id="sec-[^"]+">([^<]+)</h3>', html)
    assert titulos == ["Identificação", "Características", "Aquisição"]
    nomes = set(re.findall(r'name="([a-z_]+)"', html)) - {"csrf_token"}
    assert nomes == CAMPOS_MOTO


def test_edicao_do_veiculo_nao_tem_km_inicial():
    assert 'name="km_atual"' not in _moto(nova=False)


def test_erro_do_servidor_traz_icone_e_liga_o_campo_a_mensagem():
    html = _moto(erros={"marca": "Informe a marca."})
    assert 'aria-invalid="true"' in html and 'aria-describedby="f-marca-erro"' in html
    assert re.search(r'<small class="msg-erro" id="f-marca-erro"><svg[^>]*>.*?</svg><span>Informe a marca\.</span></small>', html)


def test_formularios_do_plano_usam_secoes():
    for caminho, minimo in [
        ("clientes/_form_cliente.html", 4), ("documentos/_campos_documento.html", 3),
        ("dividas/nova_divida.html", 4), ("dividas/nova.html", 4),
    ]:
        texto = (RAIZ / "src" / "web" / "templates" / caminho).read_text(encoding="utf-8")
        assert texto.count("{% call secao(") >= minimo, caminho


def test_telefone_do_cliente_usa_teclado_de_telefone():
    texto = (RAIZ / "src" / "web" / "templates" / "clientes" / "_form_cliente.html").read_text(encoding="utf-8")
    assert texto.count('tipo="tel", inputmode="tel"') == 2


def test_js_valida_no_blur_e_no_envio_com_aria_e_foco():
    assert "addEventListener('focusout'" in JS
    assert "setAttribute('aria-invalid', 'true')" in JS and "aria-describedby" in JS
    assert "primeiro.focus()" in JS and "e.preventDefault()" in JS
    assert not re.search(r"\beval\s*\(|new Function\s*\(", JS)


def test_navegacao_por_secoes_respeita_movimento_reduzido():
    assert "prefers-reduced-motion: reduce" in JS and "form-nav" in JS
    assert "reduzMovimento.matches ? 'auto' : 'smooth'" in JS


def test_css_celular_kpis_em_duas_colunas_e_seletor_de_mes_sem_corte():
    bloco = CSS.split("Celular: sensação de aplicativo (Fase 6)")[1]
    assert re.search(r"\.kpis, \.kpis\.kpis-3, \.kpis\.kpis-5 \{grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)", bloco)
    assert ".seletor-mes .mes-segmentado" in bloco and "flex: 1 1 100%" in bloco
    assert "env(safe-area-inset-left)" in bloco and "overflow-x: clip" in bloco


def test_css_gerado_esta_em_dia_com_a_fonte():
    # a classe nova do formulário precisa ter ido para o CSS publicado (rodar scripts/construir_css.py)
    assert ".form-secao" in CSS_GERADO and ".form-nav" in CSS_GERADO
