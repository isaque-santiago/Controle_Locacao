"""Gaveta de pré-visualização: fragmentos de veículo, cliente e contrato e os botões nas listas."""

from tests.web.conftest import entrar

GAVETA = {"HX-Request": "true", "HX-Target": "gaveta-conteudo"}
MOTO = "00000000-0000-0000-0000-000000000001"
CLIENTE = "00000000-0000-0000-0000-0000000000c1"
CONTRATO = "00000000-0000-0000-0000-0000000000d1"


def test_previas_exigem_login_e_dono(cliente, base_motos, base_clientes, base_contratos):
    for caminho in (f"/motos/{MOTO}/previa", f"/clientes/{CLIENTE}/previa", f"/contratos/{CONTRATO}/previa"):
        assert cliente.get(caminho).status_code == 303
    entrar(cliente, identificador="123.456.789-09", senha="senha-locatario")
    for caminho in (f"/motos/{MOTO}/previa", f"/clientes/{CLIENTE}/previa", f"/contratos/{CONTRATO}/previa"):
        assert cliente.get(caminho).status_code == 403


def test_previa_inexistente_ou_id_invalido_da_404(cliente, base_motos, base_clientes, base_contratos):
    entrar(cliente)
    for tipo in ("motos", "clientes", "contratos"):
        assert cliente.get(f"/{tipo}/nao-e-um-uuid/previa").status_code == 404
        assert cliente.get(f"/{tipo}/00000000-0000-0000-0000-0000000000ff/previa").status_code == 404


def test_previa_da_moto_traz_dados_locatario_e_link_da_ficha(cliente, base_motos):
    entrar(cliente)
    html = cliente.get(f"/motos/{MOTO}/previa", headers=GAVETA).text
    assert "<html" not in html and 'id="gaveta-titulo"' in html and "ABC-1D01" in html
    assert "Honda CG 101" in html and "Joana &lt;b&gt;Prado&lt;/b&gt;" in html and "<b>Prado</b>" not in html
    assert f'href="/motos/{MOTO}"' in html and "Abrir ficha completa" in html and "data-fechar" in html


def test_previa_do_cliente_mascara_o_cpf(cliente, base_clientes):
    entrar(cliente)
    html = cliente.get(f"/clientes/{CLIENTE}/previa", headers=GAVETA).text
    assert "Maria &lt;b&gt;Silva&lt;/b&gt;" in html and "***.982.***-**" in html and "52998224725" not in html
    assert f'href="/clientes/{CLIENTE}"' in html


def test_previa_do_contrato_traz_valor_periodicidade_e_cliente(cliente, base_contratos):
    entrar(cliente)
    html = cliente.get(f"/contratos/{CONTRATO}/previa", headers=GAVETA).text
    assert "R$ 280,00" in html and "Semanal" in html and "01/08/2026" in html and "BRA-2E19" in html
    assert f'href="/contratos/{CONTRATO}"' in html


def test_listas_tem_o_botao_de_previa_e_o_layout_a_gaveta(cliente, base_motos, base_clientes, base_contratos):
    entrar(cliente)
    for caminho, trecho in (("/motos", f'hx-get="/motos/{MOTO}/previa"'), ("/clientes", f'hx-get="/clientes/{CLIENTE}/previa"'),
                            ("/contratos", f'hx-get="/contratos/{CONTRATO}/previa"')):
        html = cliente.get(caminho).text
        assert trecho in html and 'hx-target="#gaveta-conteudo"' in html and 'id="dlg-gaveta"' in html
        assert 'aria-label="Pré-visualizar ' in html
