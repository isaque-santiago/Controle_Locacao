"""Registrar pagamento de cobrança: o mesmo formulário em diálogo (HTMX) e em página (sem JavaScript).

O GET devolve o diálogo quando vem do HTMX e a página inteira nos demais casos (por exemplo, o "Pagar" do Dashboard).
A prévia dos encargos é recalculada pelo servidor quando a data muda; o POST valida campo a campo e grava com
`chave_operacao`, então reenviar o mesmo formulário não lança o pagamento duas vezes."""

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import cobrancas_lista, formulario_pagamento as formulario, mensagens
from src.domain.valores import hoje_br
from src.web import acoes_cobrancas, dados_cobrancas
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

_TAMANHO_MAXIMO_CHAVE = 64
_DIALOGO = "cobrancas/_form_pagamento.html"
_PAGINA = "cobrancas/pagamento.html"


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _aberta_ou_404(cobranca_id):
    cobranca = dados_cobrancas.obter_para_pagamento(cobranca_id)
    if cobranca is None:
        raise HTTPException(status_code=404)
    return cobranca


def _data_ou_none(texto):
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def _contexto(c, v, erros=None, erro_geral=None):
    base = f"/cobrancas/{c['id']}/pagar"
    return {
        "titulo": "Registrar pagamento", "c": c, "v": v, "erros": erros or {}, "erro_geral": erro_geral, "acao": base,
        "acao_previa": f"{base}/previa", "formas": list(cobrancas_lista.FORMAS_ROTULO.items()),
        "enc": dados_cobrancas.encargos_em(c, _data_ou_none(v.get("data_pagamento"))),
    }


@router.get("/cobrancas/{cobranca_id}/pagar")
def formulario_pagamento(request: Request, cobranca_id: str, _: Sessao = Depends(exigir_dono)):
    c = _aberta_ou_404(cobranca_id)
    hoje = hoje_br()
    enc = dados_cobrancas.encargos_em(c, hoje)
    v = {**formulario.pagamento_inicial(hoje, c["saldo"], enc["encargos"]), "chave_operacao": str(uuid4())}
    return renderizar(request, _DIALOGO if _htmx(request) else _PAGINA, _contexto(c, v))


@router.post("/cobrancas/{cobranca_id}/pagar/previa", dependencies=[Depends(validar_csrf)])
async def previa_pagamento(request: Request, cobranca_id: str, _: Sessao = Depends(exigir_dono)):
    """Encargos e valores sugeridos para a data escolhida (data inválida: sem encargos)."""
    entrada = await _entrada(request)
    c = await run_in_threadpool(_aberta_ou_404, cobranca_id)
    data = _data_ou_none(entrada.get("data_pagamento"))
    enc = await run_in_threadpool(dados_cobrancas.encargos_em, c, data)
    v = formulario.pagamento_inicial(data or hoje_br(), c["saldo"], enc["encargos"])
    return renderizar(request, "cobrancas/_bloco_pagamento.html", {"c": c, "v": v, "erros": {}, "enc": enc})


def _pagar(request, sessao, cobranca_id, entrada):
    c = _aberta_ou_404(cobranca_id)
    chave = (entrada.get("chave_operacao") or "").strip()[:_TAMANHO_MAXIMO_CHAVE] or str(uuid4())
    v = {**formulario.texto_do_pagamento(entrada), "chave_operacao": chave}
    contexto = _contexto(c, v)

    def pagar():
        dados = formulario.ler_pagamento(entrada, c["saldo"])
        acoes_cobrancas.registrar_pagamento(
            c["id"], dados["data"], dados["principal"], dados["extras"], dados["forma"], dados["observacoes"], chave,
        )
        aba = formulario.aba_da_cobranca(c["situacao"], c["vencimento"], hoje_br())
        aviso = mensagens.pagamento_registrado(dados["principal"], dados["extras"], dados["quitada"])
        return _concluir(request, sessao, f"/cobrancas?aba={aba}", aviso)

    return _devolver_formulario(request, _DIALOGO if _htmx(request) else _PAGINA, contexto, pagar)


@router.post("/cobrancas/{cobranca_id}/pagar", dependencies=[Depends(validar_csrf)])
async def pagar(request: Request, cobranca_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_pagar, request, sessao, cobranca_id, await _entrada(request))
