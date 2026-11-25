"""Leitura do histórico exportado do claude.ai: domínio puro e o script de linha de comando (com um arquivo fictício)."""

import json
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.domain.chat_exportado import (
    conversas_do_titulo,
    markdown_da_conversa,
    mensagens_da_conversa,
    nome_do_arquivo,
    resumo_da_conversa,
    texto_da_mensagem,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extrair_chat_exportado as script  # noqa: E402

CONVERSA = {
    "uuid": "c1", "name": "Locadora - Acompanhamento Financeiro",
    "chat_messages": [
        {"sender": "assistant", "created_at": "2026-10-12T15:30:00.000000Z", "text": "Registrado."},
        {"sender": "human", "created_at": "2026-10-12T15:20:00.000000Z", "text": "Jhonatan pagou 275", "attachments": [{"file_name": "comprovante.pdf"}]},
        {"sender": "human", "created_at": "2026-11-03T02:10:00Z", "text": "", "content": [{"type": "text", "text": "Pago 12 de novembro"}, {"type": "image"}]},
        {"sender": "human", "created_at": "2026-11-04T10:00:00Z", "text": "   "},
        "lixo",
    ],
}
OUTRA = {"uuid": "c2", "name": "Receitas de bolo", "chat_messages": [{"sender": "human", "created_at": "2026-01-01T10:00:00Z", "text": "bolo"}]}


class TestDominio:
    def test_texto_do_campo_ou_dos_blocos_e_anexos(self):
        assert texto_da_mensagem({"text": " oi "}) == "oi"
        assert texto_da_mensagem({"text": "", "content": [{"type": "text", "text": "a"}, {"type": "image"}, {"type": "text", "text": "b"}]}) == "a\nb"
        assert texto_da_mensagem({"text": "x", "files": [{"name": "doc.pdf"}]}) == "x\n[anexo: doc.pdf]" and texto_da_mensagem({}) == ""

    def test_mensagens_em_ordem_no_fuso_de_brasilia_sem_as_vazias(self):
        m = mensagens_da_conversa(CONVERSA)
        assert [x["texto"] for x in m] == ["Jhonatan pagou 275\n[anexo: comprovante.pdf]", "Registrado.", "Pago 12 de novembro"]
        assert m[0]["autor"] == "Você" and m[1]["autor"] == "Claude" and f"{m[0]['data']:%d/%m/%Y %H:%M}" == "12/10/2026 12:20"
        assert f"{m[2]['data']:%d/%m/%Y %H:%M}" == "02/11/2026 23:10"  # 02:10 UTC é a noite do dia anterior em Brasília

    def test_conversas_pelo_titulo_sem_diferenciar_acento_nem_caixa(self):
        assert conversas_do_titulo([CONVERSA, OUTRA], ["acompanhamento FINANCEIRO"]) == [CONVERSA]
        assert conversas_do_titulo({"conversations": [CONVERSA, OUTRA]}, ["bolo", "financeiro"]) == [CONVERSA, OUTRA]
        assert conversas_do_titulo([CONVERSA], ["contratos"]) == [] and conversas_do_titulo([CONVERSA], [""]) == [] and conversas_do_titulo("x", ["a"]) == []

    def test_resumo_com_a_cobertura_por_mes(self):
        r = resumo_da_conversa(CONVERSA)
        assert r["mensagens"] == 3 and r["por_mes"] == {"2026-10": 2, "2026-11": 1} and f"{r['primeira']:%d/%m/%Y}" == "12/10/2026"
        assert resumo_da_conversa({"name": "x"}) == {"nome": "x", "mensagens": 0, "primeira": None, "ultima": None, "por_mes": {}}

    def test_markdown(self):
        md = markdown_da_conversa(CONVERSA)
        assert md.startswith("# Locadora - Acompanhamento Financeiro") and "Mensagens: 3" in md and "## [12/10/2026 12:20] Você" in md and "Pago 12 de novembro" in md

    def test_nome_do_arquivo(self):
        assert nome_do_arquivo("Locadora - Acompanhamento Financeiro", 2) == "02-locadora-acompanhamento-financeiro.md" and nome_do_arquivo("???") == "01-conversa.md"


class TestScript:
    def _exportacao(self, tmp_path, como_zip=True):
        dados = json.dumps([CONVERSA, OUTRA])
        if como_zip:
            caminho = tmp_path / "export.zip"
            with ZipFile(caminho, "w") as z:
                z.writestr("conversations.json", dados)
                z.writestr("users.json", "[]")
            return caminho
        caminho = tmp_path / "conversations.json"
        caminho.write_text(dados, encoding="utf-8")
        return caminho

    @pytest.mark.parametrize("como_zip", [True, False])
    def test_extrai_so_as_conversas_escolhidas(self, tmp_path, capsys, como_zip):
        saida = tmp_path / "saida"
        assert script.principal([str(self._exportacao(tmp_path, como_zip)), str(saida), "--titulo", "Acompanhamento Financeiro"]) == 0
        assert [p.name for p in sorted(saida.iterdir())] == ["01-locadora-acompanhamento-financeiro.md", "indice.txt"]
        indice = (saida / "indice.txt").read_text(encoding="utf-8")
        assert "3 mensagens | 12/10/2026 a 02/11/2026" in indice and "2026-10=2, 2026-11=1" in indice and "bolo" not in indice
        assert "Jhonatan pagou 275" in (saida / "01-locadora-acompanhamento-financeiro.md").read_text(encoding="utf-8")
        assert "3 mensagens" in capsys.readouterr().out

    def test_recusa_pasta_dentro_do_repositorio(self, tmp_path, capsys):
        assert script.principal([str(self._exportacao(tmp_path)), str(script.RAIZ / "tmp_saida_proibida"), "--titulo", "x"]) == 2
        assert not (script.RAIZ / "tmp_saida_proibida").exists() and "dentro do repositório" in capsys.readouterr().err

    def test_sem_conversa_com_o_titulo_ou_sem_arquivo(self, tmp_path, capsys):
        assert script.principal([str(self._exportacao(tmp_path)), str(tmp_path / "s"), "--titulo", "Contratos"]) == 1
        assert script.principal([str(tmp_path / "nao-existe.zip"), str(tmp_path / "s"), "--titulo", "x"]) == 2
        assert "Nenhuma conversa" in capsys.readouterr().err

    def test_zip_sem_conversations_json(self, tmp_path):
        caminho = tmp_path / "vazio.zip"
        with ZipFile(caminho, "w") as z:
            z.writestr("users.json", "[]")
        with pytest.raises(SystemExit):
            script.ler_conversas(caminho)
