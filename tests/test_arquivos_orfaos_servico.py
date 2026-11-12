"""Testes do serviço e do repositório dos arquivos órfãos do portal, com o Supabase falso."""

from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.repositories import arquivos_orfaos as repositorio
from src.services import arquivos_orfaos as servico

REPO = "src.services.arquivos_orfaos.arquivos_orfaos"


def _arq(bucket, caminho, tamanho=1024):
    return {"bucket": bucket, "caminho": caminho, "tamanho": tamanho, "criado_em": "2026-11-09T10:00:00+00:00"}


# ------------------------------------------------------------------ procurar --


def test_procurar_resume_o_que_a_rpc_devolveu():
    with patch(f"{REPO}.listar", return_value=[_arq("trocas_oleo", "c1/a.jpg", 2048), _arq("documentos", "portal/c1/b.pdf", 1024)]) as listar:
        r = servico.procurar()
    listar.assert_called_once_with(24)
    assert r["quantidade"] == 2 and r["tamanho"] == "3,0 KB" and len(r["por_bucket"]) == 2


def test_procurar_sem_orfaos():
    with patch(f"{REPO}.listar", return_value=[]):
        assert servico.procurar()["quantidade"] == 0


def test_recusa_do_banco_vira_mensagem_e_outros_erros_sobem():
    with patch(f"{REPO}.listar", side_effect=APIError({"message": "Informe pelo menos 1 hora de idade para os arquivos.", "code": "P0001"})):
        with pytest.raises(ValueError, match="pelo menos 1 hora"):
            servico.procurar(0)
    with patch(f"{REPO}.listar", side_effect=APIError({"message": "Acesso negado.", "code": "42501"})):
        with pytest.raises(APIError):
            servico.procurar()


# -------------------------------------------------------------------- apagar --


def test_apagar_remove_por_bucket_e_soma_o_que_foi_confirmado():
    arquivos = [_arq("trocas_oleo", "c1/a.jpg", 2048), _arq("documentos", "portal/c1/b.pdf", 1024), _arq("trocas_oleo", "c1/c.jpg", 2048)]
    with patch(f"{REPO}.listar", return_value=arquivos), \
         patch(f"{REPO}.remover", side_effect=lambda bucket, caminhos: [{"name": c} for c in caminhos]) as remover:
        r = servico.apagar()
    assert r == {"apagados": 3, "tamanho": "5,0 KB", "falhas": 0}
    assert [c.args for c in remover.call_args_list] == [("trocas_oleo", ["c1/a.jpg", "c1/c.jpg"]), ("documentos", ["portal/c1/b.pdf"])]


def test_apagar_recalcula_a_lista_no_banco_e_nao_aceita_lista_de_fora():
    with patch(f"{REPO}.listar", return_value=[]) as listar, patch(f"{REPO}.remover") as remover:
        assert servico.apagar() == {"apagados": 0, "tamanho": "0 B", "falhas": 0}
    listar.assert_called_once_with(24)
    remover.assert_not_called()


def test_apagar_em_lotes_de_cem():
    arquivos = [_arq("trocas_oleo", f"c1/{i}.jpg") for i in range(230)]
    with patch(f"{REPO}.listar", return_value=arquivos), \
         patch(f"{REPO}.remover", side_effect=lambda bucket, caminhos: [{"name": c} for c in caminhos]) as remover:
        r = servico.apagar()
    assert [len(c.args[1]) for c in remover.call_args_list] == [100, 100, 30] and r["apagados"] == 230


def test_falha_em_um_lote_nao_impede_os_outros():
    arquivos = [_arq("trocas_oleo", "c1/a.jpg"), _arq("documentos", "portal/c1/b.pdf")]

    def remover(bucket, caminhos):
        if bucket == "trocas_oleo":
            raise RuntimeError("Storage fora do ar")
        return [{"name": c} for c in caminhos]

    with patch(f"{REPO}.listar", return_value=arquivos), patch(f"{REPO}.remover", side_effect=remover):
        assert servico.apagar() == {"apagados": 1, "tamanho": "1,0 KB", "falhas": 1}


def test_so_o_que_o_storage_confirmou_conta_como_apagado():
    arquivos = [_arq("trocas_oleo", "c1/a.jpg"), _arq("trocas_oleo", "c1/b.jpg")]
    with patch(f"{REPO}.listar", return_value=arquivos), patch(f"{REPO}.remover", return_value=[{"name": "c1/b.jpg"}]):
        assert servico.apagar() == {"apagados": 1, "tamanho": "1,0 KB", "falhas": 1}


# -------------------------------------------------------------- repositório --


def test_repositorio_lista_pela_rpc_com_a_idade_minima():
    cliente = MagicMock()
    cliente.rpc.return_value.execute.return_value.data = [_arq("trocas_oleo", "c1/a.jpg")]
    with patch("src.repositories.arquivos_orfaos.get_client", return_value=cliente):
        assert repositorio.listar(24) == [_arq("trocas_oleo", "c1/a.jpg")]
    cliente.rpc.assert_called_once_with("rpc_listar_arquivos_orfaos", {"p_horas": 24})
    cliente.rpc.return_value.execute.return_value.data = None
    with patch("src.repositories.arquivos_orfaos.get_client", return_value=cliente):
        assert repositorio.listar(24) == []


def test_repositorio_remove_pela_api_do_storage_do_bucket():
    cliente = MagicMock()
    cliente.storage.from_.return_value.remove.return_value = [{"name": "c1/a.jpg"}]
    with patch("src.repositories.arquivos_orfaos.get_client", return_value=cliente):
        assert repositorio.remover("trocas_oleo", ["c1/a.jpg"]) == [{"name": "c1/a.jpg"}]
    cliente.storage.from_.assert_called_once_with("trocas_oleo")
    cliente.storage.from_.return_value.remove.assert_called_once_with(["c1/a.jpg"])
