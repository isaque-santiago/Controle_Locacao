"""Redução de fotos grandes no navegador: o JS e os campos de foto que o usam."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
JS = (RAIZ / "static" / "js" / "app.js").read_text(encoding="utf-8")
CAMPOS = {
    "src/web/templates/portal.html": 2,  # foto do painel e da nota
    "src/web/templates/vistorias/_campos_registro.html": 1,
    "src/web/templates/vistorias/_campos_fotos.html": 1,
    "src/web/templates/vistorias/_campo_camera.html": 1,  # «Tirar foto agora», incluído nas três telas de vistoria
    "src/web/templates/contratos/novo/_etapa_confirmar.html": 1,
}


def test_js_reduz_so_foto_grande_com_lado_maximo_e_espera_o_envio():
    assert "FOTO_LIMITE_BYTES = 4 * 1024 * 1024" in JS and "FOTO_LADO_MAXIMO = 3000" in JS
    assert "input[type=\"file\"][data-reduzir-foto]" in JS
    assert "imageOrientation: 'from-image'" in JS and "'image/jpeg'" in JS
    assert "b.disabled = true" in JS and "b.disabled = false" in JS  # o botão de enviar espera a redução
    assert "createImageBitmap" in JS and ".catch(function () { return arquivo; })" in JS  # formato que não abre segue como está


def test_todos_os_campos_de_foto_marcam_a_reducao():
    for caminho, quantidade in CAMPOS.items():
        html = (RAIZ / caminho).read_text(encoding="utf-8")
        assert html.count("data-reduzir-foto") == quantidade, caminho
    # Nenhum outro campo de imagem fica de fora (comprovante de documento aceita PDF e não é reduzido).
    for arquivo in (RAIZ / "src" / "web" / "templates").rglob("*.html"):
        html = arquivo.read_text(encoding="utf-8")
        if 'accept="image/*"' in html:
            assert "data-reduzir-foto" in html, arquivo
