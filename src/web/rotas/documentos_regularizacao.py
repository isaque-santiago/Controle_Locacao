"""Regularizar documento (pago ou renovado): data, comprovante opcional e o cadastro do ano seguinte.

O mesmo formulário em diálogo (HTMX) e em página (sem JavaScript). O comprovante é validado antes de qualquer gravação
e enviado antes de marcar o documento como regularizado: se o envio falhar, nada muda e o formulário volta com o erro.
Se o dono pedir o próximo documento (IPVA, licenciamento e seguro renovam todo ano), o navegador segue para o cadastro
novo já preenchido, com o vencimento em branco para ele informar."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from src.domain import documentos_lista, formulario_documento as formulario, mensagens
from src.domain.documentos import sugerir_proximo_documento
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.web import acoes_documentos
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.documentos_formularios import _documento_ou_404, _htmx, _ler_envio, _resumo_comprovante
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _modelo(request):
    return "documentos/_form_regularizar.html" if _htmx(request) else "documentos/regularizar.html"


def _contexto(registro, v, erros=None, erro_geral=None):
    documento = registro["documento"]
    return {
        "titulo": "Marcar como regularizado", "registro": registro, "v": v, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": f"/documentos/{documento['id']}/regularizar", "tipo_rotulo": documentos_lista.TIPOS_ROTULO.get(documento["tipo"], documento["tipo"]),
        "proximo": sugerir_proximo_documento(documento["tipo"], documento.get("ano_referencia")),
    }


@router.get("/documentos/{documento_id}/regularizar")
def formulario_regularizar(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    registro = _documento_ou_404(documento_id)
    if registro["documento"]["regularizado"]:
        return _concluir(request, sessao, "/documentos", tipo="info", texto="Este documento já está regularizado.")
    return renderizar(request, _modelo(request), _contexto(registro, formulario.regularizacao_inicial(hoje_br())))


def _regularizar(request, sessao, documento_id, entrada, arquivo):
    registro = _documento_ou_404(documento_id)
    documento, moto = registro["documento"], registro["moto"]
    contexto = _contexto(registro, formulario.texto_da_regularizacao(entrada))

    def gravar():
        if documento["regularizado"]:
            raise ValueError("Este documento já foi regularizado.")
        erros, dados = {}, None
        try:
            dados = formulario.ler_regularizacao(entrada)
        except ErroDeCampos as erro:
            erros.update(erro.erros)
        if arquivo is not None:
            try:
                formulario.validar_comprovante(*_resumo_comprovante(arquivo))
            except ErroDeCampos as erro:
                erros.update(erro.erros)
        if erros:
            raise ErroDeCampos(erros)
        if arquivo is not None:
            acoes_documentos.anexar_comprovante(documento["id"], documento["moto_id"], arquivo)
        resultado = acoes_documentos.regularizar_documento(documento["id"], dados["data"])
        sugestao = resultado.get("sugestao_proximo") if dados["criar_proximo"] else None
        referencia = documento.get("ano_referencia") or documento.get("descricao") or ""
        descricao = f"{contexto['tipo_rotulo']} {referencia} da moto {formatar_placa(moto['placa'])}".replace("  ", " ")
        aviso = mensagens.documento_regularizado(descricao, bool(sugestao))
        if sugestao:
            parametros = urlencode({"moto": documento["moto_id"], "tipo": sugestao["tipo"], "ano": sugestao["ano_referencia"]})
            return _concluir(request, sessao, f"/documentos/novo?{parametros}", aviso)
        return _concluir(request, sessao, "/documentos", aviso)

    return _devolver_formulario(request, _modelo(request), contexto, gravar)


@router.post("/documentos/{documento_id}/regularizar", dependencies=[Depends(validar_csrf)])
async def regularizar(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada, arquivo = await _ler_envio(request)
    return await run_in_threadpool(_regularizar, request, sessao, documento_id, entrada, arquivo)
