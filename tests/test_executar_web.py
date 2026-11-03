"""Partes puras da recarga automática do `executar_web.py` (observar os .py e dizer o que mudou)."""

import executar_web


def test_assinatura_lista_so_os_py_das_pastas_observadas(tmp_path, monkeypatch):
    (tmp_path / "src" / "web").mkdir(parents=True)
    (tmp_path / "static").mkdir()
    (tmp_path / "src" / "web" / "app.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "src" / "web" / "pagina.html").write_text("<p>", encoding="utf-8")  # template: relido a cada requisição
    (tmp_path / "static" / "script.py").write_text("x = 2", encoding="utf-8")  # fora das pastas observadas
    monkeypatch.setattr(executar_web, "RAIZ", tmp_path)
    assert [c.replace("\\", "/").rsplit("/", 2)[-2:] for c in executar_web._assinatura()] == [["web", "app.py"]]


def test_mudancas_apontam_arquivo_editado_novo_e_apagado(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    a, b = tmp_path / "src" / "a.py", tmp_path / "src" / "b.py"
    a.write_text("1", encoding="utf-8")
    b.write_text("1", encoding="utf-8")
    monkeypatch.setattr(executar_web, "RAIZ", tmp_path)
    antes = executar_web._assinatura()
    assert executar_web._mudancas(antes, executar_web._assinatura()) == []  # nada mudou
    a.write_text("22", encoding="utf-8")
    import os
    os.utime(a, ns=(antes[str(a)] + 5_000_000_000, antes[str(a)] + 5_000_000_000))  # garante instante diferente
    novo = tmp_path / "src" / "c.py"
    novo.write_text("1", encoding="utf-8")
    b.unlink()
    assert [c.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for c in executar_web._mudancas(antes, executar_web._assinatura())] == ["a.py", "b.py", "c.py"]


def test_arquivo_apagado_durante_a_leitura_nao_derruba_o_observador(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    arquivo = tmp_path / "src" / "efemero.py"
    arquivo.write_text("1", encoding="utf-8")
    monkeypatch.setattr(executar_web, "RAIZ", tmp_path)

    original = type(arquivo).stat

    def stat_que_falha(self, *a, **k):
        if self.name == "efemero.py":
            raise FileNotFoundError(self)
        return original(self, *a, **k)

    monkeypatch.setattr(type(arquivo), "stat", stat_que_falha)
    assert executar_web._assinatura() == {}
