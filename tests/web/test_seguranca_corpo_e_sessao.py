"""Revisão de segurança (Fase 4): limite do corpo das requisições e vida máxima da sessão."""

from fastapi.testclient import TestClient

from src.web.app import criar_app
from src.web.seguranca import LIMITE_CORPO_ARQUIVOS, LIMITE_CORPO_FORMULARIO
from src.web.sessao import LIMITE_VIDA_SEGUNDOS, ArmazemSessoes
from tests.web.conftest import Relogio


def _cliente():
    return TestClient(criar_app(desenvolvimento=False), raise_server_exceptions=False)


def test_formulario_comum_acima_de_1_mb_e_recusado_com_413():
    resposta = _cliente().post(
        "/login", content=b"a=" + b"x" * (LIMITE_CORPO_FORMULARIO + 10),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resposta.status_code == 413


def test_formulario_pequeno_segue_para_a_rota():
    resposta = _cliente().post("/login", data={"identificador": "a", "senha": "b"})
    assert resposta.status_code != 413  # recusado pelo CSRF, mas chegou à rota


def test_envio_de_arquivos_tem_limite_proprio_maior():
    pequeno = _cliente().post("/login", files={"foto": ("a.png", b"x" * (LIMITE_CORPO_FORMULARIO + 10))})
    assert pequeno.status_code != 413
    assert LIMITE_CORPO_ARQUIVOS >= 10 * 10 * 1024 * 1024  # 10 fotos de 10 MB por vistoria


def test_corpo_que_estoura_sem_content_length_tambem_e_barrado():
    def pedacos():
        for _ in range(LIMITE_CORPO_FORMULARIO // 65536 + 2):
            yield b"x" * 65536

    resposta = _cliente().post("/login", content=pedacos(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert resposta.status_code == 413


def _abrir(armazem):
    return armazem.criar(usuario_id="u", email="e", papel="dono", access_token="a", refresh_token="r", expira_em=9e9)


def test_sessao_ativa_expira_pela_vida_maxima():
    relogio = Relogio()
    armazem = ArmazemSessoes(relogio=relogio)
    sessao = _abrir(armazem)
    for _ in range(int(LIMITE_VIDA_SEGUNDOS // 600) - 1):  # uso contínuo: atividade a cada 10 min
        relogio.avancar(600)
        assert armazem.obter(sessao.id) is not None
    relogio.avancar(1200)
    assert armazem.obter(sessao.id) is None


def test_vida_maxima_sobrevive_ao_espelho_em_arquivo(tmp_path):
    relogio = Relogio()
    arquivo = tmp_path / "sessoes.json"
    armazem = ArmazemSessoes(relogio=relogio, arquivo=arquivo)
    sessao = _abrir(armazem)
    relogio.avancar(LIMITE_VIDA_SEGUNDOS - 100)
    armazem.obter(sessao.id)
    armazem.salvar()
    relogio.avancar(200)  # 100 s além da vida máxima, mas só 200 s de inatividade
    assert ArmazemSessoes(relogio=relogio, arquivo=arquivo).obter(sessao.id) is None
