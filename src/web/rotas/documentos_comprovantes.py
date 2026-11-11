"""Conferir o comprovante que o locatário enviou pelo portal: aceitar (regulariza o documento) ou recusar com um motivo.

Só o dono. O arquivo do locatário abre por URL assinada de curta duração (o bucket é privado). Aceitar é uma transação no banco
(documento regularizado + envio fechado); se o dono pedir o próximo documento (IPVA, licenciamento e seguro renovam todo ano), o
navegador segue para o cadastro novo já preenchido, como na regularização comum."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from src.domain import comprovante_documento as regras, documentos_lista, mensagens
from src.domain.documentos import sugerir_proximo_documento
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.web import acoes_documentos, dados_documentos
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.documentos_formularios import _documento_ou_404
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()
_MODELO = "documentos/conferir.html"


def _nome(registro):
    d = registro["documento"]
    return f"{regras.nome_do_documento(d['tipo'], d.get('descricao'), d.get('ano_referencia'))} da moto {formatar_placa(registro['moto']['placa'])}"


def _contexto(registro, v=None, erros=None, erro_geral=None, motivo="", erros_recusa=None):
    documento = registro["documento"]
    dados = dados_documentos.comprovante_do_documento(documento["id"])
    return {
        "titulo": "Conferir comprovante", "registro": registro, "nome": _nome(registro), **dados,
        "tipo_rotulo": documentos_lista.TIPOS_ROTULO.get(documento["tipo"], documento["tipo"]),
        "v": v or {"data": hoje_br().isoformat(), "criar_proximo": True}, "erros": erros or {}, "erro_geral": erro_geral,
        "motivo": motivo, "erros_recusa": erros_recusa or {},
        "proximo": sugerir_proximo_documento(documento["tipo"], documento.get("ano_referencia")),
        "status_rotulo": regras.STATUS_ROTULO, "status_tom": regras.STATUS_TOM,
    }


@router.get("/documentos/{documento_id}/comprovante-enviado")
def conferir(request: Request, documento_id: str, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, _MODELO, _contexto(_documento_ou_404(documento_id)))


@router.get("/documentos/{documento_id}/comprovante-enviado/arquivo")
async def arquivo(documento_id: str, _: Sessao = Depends(exigir_dono)):
    """Assina o link na hora do clique (vale 5 minutos) e leva o navegador até o arquivo do locatário."""
    registro = await run_in_threadpool(_documento_ou_404, documento_id)
    url = await run_in_threadpool(dados_documentos.url_do_comprovante_enviado, registro["documento"]["id"])
    if not url:
        raise HTTPException(status_code=404)
    return RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})


def _aceitar(request, sessao, documento_id, entrada):
    registro = _documento_ou_404(documento_id)
    contexto = _contexto(registro, v={"data": str(entrada.get("data") or "").strip(), "criar_proximo": bool(entrada.get("criar_proximo"))})
    envio = contexto["envio"]

    def gravar():
        if envio is None:
            raise ValueError("Não há comprovante aguardando conferência para este documento.")
        dados = regras.ler_aceite(entrada, hoje_br())
        resultado = acoes_documentos.aceitar_comprovante(envio["id"], dados["data"])
        sugestao = resultado.get("sugestao_proximo") if dados["criar_proximo"] else None
        aviso = mensagens.documento_regularizado(contexto["nome"], bool(sugestao))
        if sugestao:
            parametros = urlencode({"moto": registro["documento"]["moto_id"], "tipo": sugestao["tipo"], "ano": sugestao["ano_referencia"]})
            return _concluir(request, sessao, f"/documentos/novo?{parametros}", aviso)
        return _concluir(request, sessao, "/documentos", aviso)

    return _devolver_formulario(request, _MODELO, contexto, gravar)


@router.post("/documentos/{documento_id}/comprovante-enviado/aceitar", dependencies=[Depends(validar_csrf)])
async def aceitar(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_aceitar, request, sessao, documento_id, await _entrada(request))


def _recusar(request, sessao, documento_id, entrada):
    registro = _documento_ou_404(documento_id)
    contexto = _contexto(registro, motivo=str(entrada.get("motivo") or "").strip())
    envio = contexto["envio"]
    try:
        if envio is None:
            raise ValueError("Não há comprovante aguardando conferência para este documento.")
        motivo = regras.ler_recusa(entrada)
        acoes_documentos.recusar_comprovante(envio["id"], motivo)
    except ErroDeCampos as erro:
        contexto["erros_recusa"] = erro.erros
        return renderizar(request, _MODELO, contexto, status=422)
    except ValueError as erro:
        contexto["erro_geral"] = str(erro)
        return renderizar(request, _MODELO, contexto, status=422)
    return _concluir(request, sessao, "/documentos", mensagens.comprovante_recusado(contexto["nome"]))


@router.post("/documentos/{documento_id}/comprovante-enviado/recusar", dependencies=[Depends(validar_csrf)])
async def recusar(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_recusar, request, sessao, documento_id, await _entrada(request))
