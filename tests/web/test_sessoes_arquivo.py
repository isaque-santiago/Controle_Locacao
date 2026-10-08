"""Sessões espelhadas em arquivo (só em desenvolvimento): o login sobrevive à recarga do servidor."""

import json

from fastapi.testclient import TestClient

from src.web.app import arquivo_de_sessoes, criar_app
from src.web.sessao import INTERVALO_SALVAR_ATIVIDADE_SEGUNDOS, ArmazemSessoes
from tests.web.conftest import VALIDADE_TOKEN, Relogio, entrar


def _criar(armazem, email="dono@exemplo.com"):
    return armazem.criar(usuario_id="u1", email=email, papel="dono", access_token="acesso", refresh_token="renovacao",
                         expira_em=2_000_000.0)


def _conteudo(arquivo):
    return json.loads(arquivo.read_text(encoding="utf-8"))


def test_sessao_criada_vai_para_o_arquivo_e_sobrevive_a_um_novo_armazem(tmp_path):
    arquivo, relogio = tmp_path / "sessoes.json", Relogio()
    sessao = _criar(ArmazemSessoes(relogio=relogio, arquivo=arquivo))
    assert [s["id"] for s in _conteudo(arquivo)] == [sessao.id]
    novo = ArmazemSessoes(relogio=relogio, arquivo=arquivo)  # o servidor recarregou
    recuperada = novo.obter(sessao.id)
    assert recuperada is not None and recuperada.email == "dono@exemplo.com" and recuperada.papel == "dono"
    assert (recuperada.access_token, recuperada.refresh_token, recuperada.expira_em) == ("acesso", "renovacao", 2_000_000.0)
    assert recuperada.csrf_token == sessao.csrf_token and recuperada.cliente is None  # o cliente Supabase é refeito


def test_sessao_vencida_por_inatividade_nao_volta(tmp_path):
    arquivo, relogio = tmp_path / "sessoes.json", Relogio()
    sessao = _criar(ArmazemSessoes(limite_inatividade=100, relogio=relogio, arquivo=arquivo))
    relogio.avancar(101)
    novo = ArmazemSessoes(limite_inatividade=100, relogio=relogio, arquivo=arquivo)
    assert novo.quantidade() == 0 and novo.obter(sessao.id) is None


def test_sair_remove_a_sessao_do_arquivo(tmp_path):
    arquivo = tmp_path / "sessoes.json"
    armazem = ArmazemSessoes(relogio=Relogio(), arquivo=arquivo)
    sessao, outra = _criar(armazem), _criar(armazem, "outro@exemplo.com")
    armazem.encerrar(sessao.id)
    assert [s["id"] for s in _conteudo(arquivo)] == [outra.id]
    assert ArmazemSessoes(relogio=Relogio(), arquivo=arquivo).obter(sessao.id) is None


def test_atividade_so_e_regravada_de_tempos_em_tempos(tmp_path):
    arquivo, relogio = tmp_path / "sessoes.json", Relogio()
    armazem = ArmazemSessoes(relogio=relogio, arquivo=arquivo)
    sessao = _criar(armazem)
    inicial = _conteudo(arquivo)[0]["ultima_atividade"]
    relogio.avancar(INTERVALO_SALVAR_ATIVIDADE_SEGUNDOS - 1)
    armazem.obter(sessao.id)
    assert _conteudo(arquivo)[0]["ultima_atividade"] == inicial  # muito cedo para regravar
    relogio.avancar(2)
    armazem.obter(sessao.id)
    assert _conteudo(arquivo)[0]["ultima_atividade"] == relogio()


def test_salvar_grava_os_tokens_renovados(tmp_path):
    arquivo = tmp_path / "sessoes.json"
    armazem = ArmazemSessoes(relogio=Relogio(), arquivo=arquivo)
    sessao = _criar(armazem)
    sessao.refresh_token = "renovacao-nova"
    armazem.salvar()
    assert _conteudo(arquivo)[0]["refresh_token"] == "renovacao-nova"


def test_arquivo_ausente_estragado_ou_incompleto_vale_como_sem_sessoes(tmp_path):
    assert ArmazemSessoes(arquivo=tmp_path / "nao-existe.json").quantidade() == 0
    estragado = tmp_path / "estragado.json"
    estragado.write_text("{isto nao e json", encoding="utf-8")
    assert ArmazemSessoes(arquivo=estragado).quantidade() == 0
    incompleto = tmp_path / "incompleto.json"
    incompleto.write_text(json.dumps([{"id": "x"}, "texto", {"id": "y", "email": "a"}]), encoding="utf-8")
    assert ArmazemSessoes(arquivo=incompleto).quantidade() == 0


def test_sem_arquivo_nada_vai_para_o_disco(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    armazem = ArmazemSessoes(relogio=Relogio())
    _criar(armazem)
    armazem.salvar()
    assert list(tmp_path.iterdir()) == []


def test_falha_ao_gravar_nao_derruba_o_login(tmp_path):
    armazem = ArmazemSessoes(relogio=Relogio(), arquivo=tmp_path / "pasta-que-nao-existe" / "sessoes.json")
    assert armazem.obter(_criar(armazem).id) is not None


def test_arquivo_so_vale_em_desenvolvimento_e_quando_pedido(monkeypatch):
    monkeypatch.setenv("LOCACAO_SESSOES_ARQUIVO", "/tmp/sessoes.json")
    assert arquivo_de_sessoes(True) == "/tmp/sessoes.json"
    assert arquivo_de_sessoes(False) is None  # produção nunca grava sessões em disco
    monkeypatch.delenv("LOCACAO_SESSOES_ARQUIVO")
    assert arquivo_de_sessoes(True) is None
    monkeypatch.setenv("LOCACAO_SESSOES_ARQUIVO", "")
    assert arquivo_de_sessoes(True) is None


def test_login_sobrevive_a_recarga_do_servidor_e_o_formulario_aberto_continua_valido(servico, relogio, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCACAO_SESSOES_ARQUIVO", str(tmp_path / "sessoes.json"))
    antes = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=True), follow_redirects=False)
    entrar(antes)
    assert antes.get("/").status_code == 200
    pagina = antes.get("/relatorios").text
    depois = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=True), follow_redirects=False)  # reinício
    depois.cookies.update(antes.cookies)
    assert depois.get("/").status_code == 200  # ainda logado
    token = pagina.split('name="csrf_token" value="')[1].split('"')[0]
    assert depois.post("/logout", data={"csrf_token": token}).status_code == 303  # o token da página antiga ainda vale
    assert depois.get("/").status_code == 303  # e sair funciona depois da recarga


def test_producao_nao_grava_sessoes_mesmo_com_a_variavel(servico, relogio, tmp_path, monkeypatch):
    arquivo = tmp_path / "sessoes.json"
    monkeypatch.setenv("LOCACAO_SESSOES_ARQUIVO", str(arquivo))
    cliente = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=False), follow_redirects=False)
    entrar(cliente)
    assert cliente.get("/").status_code == 200 and not arquivo.exists()


def test_renovar_o_token_regrava_o_arquivo(servico, relogio, tmp_path, monkeypatch):
    arquivo = tmp_path / "sessoes.json"
    monkeypatch.setenv("LOCACAO_SESSOES_ARQUIVO", str(arquivo))
    cliente = TestClient(criar_app(servico=servico, relogio=relogio, desenvolvimento=True), follow_redirects=False)
    entrar(cliente)
    antigo = _conteudo(arquivo)[0]["refresh_token"]
    for passo in (1700, 1700):  # navegando, para a sessão não vencer por inatividade (30 min)
        relogio.avancar(passo)
        assert cliente.get("/").status_code == 200
    relogio.avancar(VALIDADE_TOKEN - 3400 - 10)  # o access token está para vencer
    assert cliente.get("/").status_code == 200 and servico.renovacoes == 1
    novo = _conteudo(arquivo)[0]["refresh_token"]
    assert novo != antigo and novo.startswith("refresh-")
