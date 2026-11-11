"""Portal do locatário: envio do comprovante de um documento da moto (IPVA, licenciamento, seguro...).

O envio NÃO regulariza o documento: fica aguardando o dono, que confere e aceita ou recusa (Etapa 6 da seção 20 do plano).
O formulário é uma página comum (sem JavaScript obrigatório): com erro volta o portal com a mensagem ao lado do campo."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.domain import comprovante_documento as regras, mensagens
from src.web import acoes_portal, dados_portal
from src.web.dependencias import exigir_locatario, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.rotas.portal import _PAGINA, _contexto, _resumo_arquivo
from src.web.sessao import Sessao

router = APIRouter()


def _enviar(request, sessao, documento_id, entrada, arquivo):
    dados, documento = dados_portal.documento_do_locatario(documento_id)
    if documento is None:
        raise HTTPException(status_code=404)
    contexto = _contexto(dados, alvo=documento_id)
    observacao_digitada = str(entrada.get("observacao") or "").strip()
    contexto["observacao_digitada"] = observacao_digitada

    def gravar():
        if not documento["pode_enviar"]:
            raise ValueError("Já há um comprovante deste documento aguardando conferência do proprietário.")
        observacao = regras.ler_envio(entrada, _resumo_arquivo(arquivo))
        acoes_portal.enviar_comprovante_documento(
            dados["cliente_id"], documento_id, (arquivo.filename, arquivo.file.read()), observacao)
        return _concluir(request, sessao, "/portal#documentos", mensagens.comprovante_enviado(documento["nome"]))

    return _devolver_formulario(request, _PAGINA, contexto, gravar)


@router.post("/portal/documentos/{documento_id}/comprovante", dependencies=[Depends(validar_csrf)])
async def enviar_comprovante(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_locatario)):
    try:
        documento_id = str(UUID(documento_id))
    except ValueError:
        raise HTTPException(status_code=404)
    enviado = await request.form()
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    arquivo = enviado.get("comprovante")
    arquivo = arquivo if isinstance(arquivo, UploadFile) and arquivo.filename else None
    return await run_in_threadpool(_enviar, request, sessao, documento_id, entrada, arquivo)
