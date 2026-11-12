"""Cancelar cobrança (dono): o mesmo formulário em diálogo (HTMX) e em página (sem JavaScript).

Só a cobrança em aberto e sem pagamento pode ser cancelada, e o motivo é obrigatório (regra em `domain/cancelamento_cobranca.py`,
conferida de novo no banco). O GET devolve o diálogo quando vem do HTMX e a página inteira nos demais casos; depois de cancelar,
a tela volta para a aba onde a cobrança estava."""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import cancelamento_cobranca as regras, formulario_pagamento, mensagens
from src.domain.valores import hoje_br
from src.web import acoes_cobrancas, dados_cobrancas
from src.web.apresentacao import rotulo_tipo_cobranca
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

_DIALOGO = "cobrancas/_form_cancelar.html"
_PAGINA = "cobrancas/cancelar.html"


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _aberta_ou_404(cobranca_id):
    cobranca = dados_cobrancas.obter_para_cancelamento(cobranca_id)
    if cobranca is None:
        raise HTTPException(status_code=404)
    return cobranca


def _contexto(c, motivo="", erros=None, erro_geral=None):
    return {
        "titulo": "Cancelar cobrança", "c": c, "motivo": motivo, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": f"/cobrancas/{c['id']}/cancelar", "maximo": regras.MOTIVO_MAXIMO,
    }


@router.get("/cobrancas/{cobranca_id}/cancelar")
def formulario_cancelamento(request: Request, cobranca_id: str, _: Sessao = Depends(exigir_dono)):
    c = _aberta_ou_404(cobranca_id)
    contexto = _contexto(c, erro_geral=None if regras.pode_cancelar(c) else regras.motivo_da_recusa(c))
    return renderizar(request, _DIALOGO if _htmx(request) else _PAGINA, contexto)


def _cancelar(request, sessao, cobranca_id, entrada):
    c = _aberta_ou_404(cobranca_id)
    contexto = _contexto(c, motivo=str(entrada.get("motivo") or "").strip())

    def cancelar():
        if not regras.pode_cancelar(c):
            raise ValueError(regras.motivo_da_recusa(c))
        motivo = regras.ler_cancelamento(entrada)
        acoes_cobrancas.cancelar_cobranca(c["id"], motivo)
        aba = formulario_pagamento.aba_da_cobranca(c["situacao"], c["vencimento"], hoje_br())
        aviso = mensagens.cobranca_cancelada(rotulo_tipo_cobranca(c["tipo"]), c.get("cliente") or "cliente", c["valor"])
        return _concluir(request, sessao, f"/cobrancas?aba={aba}", aviso)

    return _devolver_formulario(request, _DIALOGO if _htmx(request) else _PAGINA, contexto, cancelar)


@router.post("/cobrancas/{cobranca_id}/cancelar", dependencies=[Depends(validar_csrf)])
async def cancelar(request: Request, cobranca_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_cancelar, request, sessao, cobranca_id, await _entrada(request))
