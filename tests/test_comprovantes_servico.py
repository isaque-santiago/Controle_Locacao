"""Testes dos serviços e repositórios do comprovante de documento (lado do locatário e do dono), com o Supabase falso."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from src.repositories import documento_comprovantes as repo_dono
from src.repositories import portal_locatario as repo_portal
from src.services import documentos, portal_locatario

PDF = b"%PDF-1.7 comprovante"
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20
REPO_PORTAL = "src.services.portal_locatario.portal_locatario"


# ----------------------------------------------------------- locatário (serviço) --


def test_envia_o_pdf_e_registra_pela_rpc():
    with patch(f"{REPO_PORTAL}.enviar_comprovante_arquivo", return_value="portal/c1/abc.pdf") as envio, \
         patch(f"{REPO_PORTAL}.registrar_comprovante", return_value={"id": "e1", "status": "enviado"}) as rpc:
        r = portal_locatario.enviar_comprovante_documento("c1", "d1", "comprovante.PDF", PDF, "Paguei hoje")
    assert r == {"id": "e1", "status": "enviado"}
    envio.assert_called_once_with("c1", "comprovante.PDF", PDF, "application/pdf")
    rpc.assert_called_once_with({"documento_id": "d1", "arquivo_path": "portal/c1/abc.pdf", "observacao": "Paguei hoje"})


def test_arquivo_invalido_nao_vai_ao_storage():
    with patch(f"{REPO_PORTAL}.enviar_comprovante_arquivo") as envio, patch(f"{REPO_PORTAL}.registrar_comprovante") as rpc:
        for nome, conteudo in (("c.exe", b"MZ"), ("c.pdf", b"nao e pdf"), ("c.pdf", b"")):
            with pytest.raises(ValueError):
                portal_locatario.enviar_comprovante_documento("c1", "d1", nome, conteudo, None)
    envio.assert_not_called()
    rpc.assert_not_called()


def test_foto_perde_os_dados_pessoais_antes_de_subir():
    with patch(f"{REPO_PORTAL}.enviar_comprovante_arquivo", return_value="portal/c1/x.jpg") as envio, \
         patch(f"{REPO_PORTAL}.registrar_comprovante", return_value={}), \
         patch("src.services.portal_locatario.remover_dados_pessoais", return_value=b"limpo") as limpar:
        portal_locatario.enviar_comprovante_documento("c1", "d1", "foto.jpg", JPG, None)
    limpar.assert_called_once_with("foto.jpg", JPG)
    assert envio.call_args.args[2] == b"limpo" and envio.call_args.args[3] == "image/jpeg"


def test_regra_de_negocio_da_rpc_vira_mensagem_para_o_locatario():
    erro = APIError({"message": "Já existe um comprovante aguardando conferência para este documento.", "code": "P0001"})
    with patch(f"{REPO_PORTAL}.enviar_comprovante_arquivo", return_value="portal/c1/x.pdf"), \
         patch(f"{REPO_PORTAL}.registrar_comprovante", side_effect=erro):
        with pytest.raises(ValueError, match="Já existe um comprovante aguardando"):
            portal_locatario.enviar_comprovante_documento("c1", "d1", "c.pdf", PDF, None)


def test_outro_erro_da_rpc_nao_e_escondido():
    erro = APIError({"message": "Acesso negado.", "code": "42501"})
    with patch(f"{REPO_PORTAL}.enviar_comprovante_arquivo", return_value="portal/c1/x.pdf"), \
         patch(f"{REPO_PORTAL}.registrar_comprovante", side_effect=erro):
        with pytest.raises(APIError):
            portal_locatario.enviar_comprovante_documento("c1", "d1", "c.pdf", PDF, None)


def test_lista_de_documentos_do_locatario_vem_da_rpc():
    with patch(f"{REPO_PORTAL}.documentos", return_value=[{"documento_id": "d1"}]):
        assert portal_locatario.documentos_do_locatario() == [{"documento_id": "d1"}]


# -------------------------------------------------------- locatário (repositório) --


def _com_cliente(modulo):
    cliente = MagicMock()
    return cliente, patch.object(modulo, "get_client", return_value=cliente)


def test_repositorio_sobe_para_a_pasta_do_proprio_locatario_sem_sobrescrever():
    cliente, patcher = _com_cliente(repo_portal)
    with patcher:
        caminho = repo_portal.enviar_comprovante_arquivo("c1", "Foto.JPG", b"x", "image/jpeg")
    assert caminho.startswith("portal/c1/") and caminho.endswith(".jpg") and len(caminho) == len("portal/c1/") + 32 + 4
    cliente.storage.from_.assert_called_once_with("documentos")
    cliente.storage.from_.return_value.upload.assert_called_once_with(caminho, b"x", {"content-type": "image/jpeg", "upsert": "false"})


def test_repositorio_chama_as_rpcs_do_portal():
    cliente, patcher = _com_cliente(repo_portal)
    with patcher:
        repo_portal.documentos()
        repo_portal.registrar_comprovante({"documento_id": "d1"})
    assert [c.args for c in cliente.rpc.call_args_list] == [
        ("rpc_portal_documentos",), ("rpc_portal_enviar_comprovante", {"payload": {"documento_id": "d1"}})]


# ---------------------------------------------------------------- dono (serviço) --

REPO_DONO = "src.services.documentos.documento_comprovantes"
REPO_DOC = "src.services.documentos.documentos_moto"


def test_aceitar_devolve_o_documento_e_a_sugestao_do_ano_seguinte():
    documento = {"id": "d1", "tipo": "ipva", "ano_referencia": 2026, "regularizado": True}
    with patch(f"{REPO_DONO}.aceitar", return_value={"documento_id": "d1", "status": "aceito"}) as aceitar, \
         patch(f"{REPO_DOC}.obter", return_value=documento):
        r = documentos.aceitar_comprovante("e1", date(2026, 11, 12))
    aceitar.assert_called_once_with("e1", date(2026, 11, 12))
    assert r["documento"] == documento and r["sugestao_proximo"]["ano_referencia"] == 2027


def test_aceitar_documento_sem_renovacao_anual_nao_sugere():
    with patch(f"{REPO_DONO}.aceitar", return_value={"documento_id": "d1"}), \
         patch(f"{REPO_DOC}.obter", return_value={"id": "d1", "tipo": "vistoria_detran", "ano_referencia": None}):
        assert documentos.aceitar_comprovante("e1", date(2026, 11, 12))["sugestao_proximo"] is None


def test_aceitar_ja_conferido_vira_mensagem():
    erro = APIError({"message": "Este comprovante já foi conferido.", "code": "P0001"})
    with patch(f"{REPO_DONO}.aceitar", side_effect=erro):
        with pytest.raises(ValueError, match="já foi conferido"):
            documentos.aceitar_comprovante("e1", date(2026, 11, 12))
    with patch(f"{REPO_DONO}.aceitar", side_effect=APIError({"message": "x", "code": "42501"})):
        with pytest.raises(APIError):
            documentos.aceitar_comprovante("e1", date(2026, 11, 12))


def test_recusar_avisa_quando_o_envio_ja_foi_conferido():
    with patch(f"{REPO_DONO}.recusar", return_value=[{"id": "e1"}]) as recusar:
        documentos.recusar_comprovante("e1", "Foto cortada")
    recusar.assert_called_once_with("e1", "Foto cortada")
    with patch(f"{REPO_DONO}.recusar", return_value=[]):
        with pytest.raises(ValueError, match="já foi conferido"):
            documentos.recusar_comprovante("e1", "Foto cortada")


def test_leituras_do_dono_passam_pelo_repositorio():
    with patch(f"{REPO_DONO}.listar_aguardando", return_value=[1]), patch(f"{REPO_DONO}.aguardando_do_documento", return_value={"id": "e1"}), \
         patch(f"{REPO_DONO}.historico_do_documento", return_value=[2]):
        assert documentos.comprovantes_aguardando() == [1]
        assert documentos.comprovante_aguardando("d1") == {"id": "e1"}
        assert documentos.historico_de_comprovantes("d1") == [2]


# ------------------------------------------------------------ dono (repositório) --


def test_repositorio_do_dono_aceita_pela_rpc_e_recusa_so_o_que_aguarda():
    cliente, patcher = _com_cliente(repo_dono)
    cliente.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "e1"}]
    with patcher:
        repo_dono.aceitar("e1", date(2026, 11, 12))
        assert repo_dono.recusar("e1", "Foto cortada") == [{"id": "e1"}]
    assert cliente.rpc.call_args.args == ("rpc_aceitar_comprovante_documento", {"p_envio": "e1", "p_data": "2026-11-12"})
    atualizacao = cliente.table.return_value.update.call_args.args[0]
    assert atualizacao["status"] == "recusado" and atualizacao["motivo_recusa"] == "Foto cortada" and atualizacao["conferido_em"]
    cliente.table.return_value.update.return_value.eq.assert_called_once_with("id", "e1")
    cliente.table.return_value.update.return_value.eq.return_value.eq.assert_called_once_with("status", "enviado")


# ------------------------------------------------------------- alerta do Dashboard --


def test_alerta_do_dashboard_nomeia_cliente_documento_e_moto():
    envios = [{"clientes": {"nome": "Maria Souza"},
               "documentos_moto": {"tipo": "ipva", "descricao": None, "ano_referencia": 2026, "motos": {"placa": "ABC1D23"}}},
              {"clientes": {"nome": "João"}, "documentos_moto": {"tipo": "outro", "descricao": "Taxa do rastreador", "ano_referencia": None, "motos": None}}]
    with patch(f"{REPO_DONO}.listar_aguardando", return_value=envios):
        itens = documentos.alertas_de_comprovantes()
    assert len(itens) == 1
    assert (itens[0].quantidade, itens[0].titulo, itens[0].area) == (2, "Comprovante a conferir", "documentos")
    assert itens[0].descricao == "Maria Souza · IPVA 2026 · ABC1D23 e mais 1"


def test_alerta_do_dashboard_sem_envios_ou_com_falha_de_leitura():
    with patch(f"{REPO_DONO}.listar_aguardando", return_value=[]):
        assert documentos.alertas_de_comprovantes() == []
    with patch(f"{REPO_DONO}.listar_aguardando", side_effect=RuntimeError("tabela inexistente")):
        assert documentos.alertas_de_comprovantes() == []
