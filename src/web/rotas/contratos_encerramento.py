"""Encerramento de contrato em diálogo HTMX: vistoria de devolução, danos descontados da caução e prévia do impacto.

O GET abre o diálogo; a prévia (caução e cobranças canceladas) é recalculada pelo servidor quando a data ou os
danos mudam; o POST valida campo a campo e encerra pela RPC única. Com erro o mesmo formulário volta com as mensagens;
com sucesso vem `HX-Redirect` para a ficha, com o aviso de devolução da caução."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import formulario_contrato as formulario, mensagens
from src.domain.entradas import decimal_campo
from src.domain.valores import hoje_br
from src.domain.vistorias import CHECKLIST_PADRAO, ESTADOS_ITEM, NIVEIS_COMBUSTIVEL, rotulo_item
from src.web import acoes_contratos, dados_contratos
from src.web.apresentacao import formatar_milhar, formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.contratos import _contrato_ou_404
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

LIMITE_IMPACTO = 8  # cobranças listadas na prévia; as demais viram "e mais N"
_ESTADOS_ROTULO = {"ok": "OK", "avaria": "Avaria", "ausente": "Ausente", "nao_aplicavel": "N/A"}


def _ativo_ou_404(contrato_id):
    registro = _contrato_ou_404(contrato_id)
    if registro["contrato"]["status"] != "ativo":
        raise HTTPException(status_code=404)
    return registro


def _data_ou_none(texto):
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def _danos_ou_none(texto):
    try:
        return decimal_campo(texto, "Danos")
    except ValueError:
        return None


def _previa(registro, v):
    return dados_contratos.previa_encerramento(
        registro["contrato"]["id"], _data_ou_none(v.get("data_encerramento")), _danos_ou_none(v.get("valor_danos")),
    )


def _contexto(registro, v, erros=None, erro_geral=None):
    contrato, moto = registro["contrato"], registro["moto"]
    base = f"/contratos/{contrato['id']}/encerrar"
    return {
        **registro, "v": v, "erros": erros or {}, "erro_geral": erro_geral, "acao": base, "acao_previa": f"{base}/previa",
        "resumo": _previa(registro, v), "limite_impacto": LIMITE_IMPACTO,
        "avarias_resumo": dados_contratos.avarias_da_entrega(contrato["id"]),
        "ajuda_km": f"Vale como km final do contrato (início: {formatar_milhar(contrato['km_inicial'])} km).",
        "itens_checklist": [(formulario.PREFIXO_ITEM + item, rotulo_item(item)) for item in CHECKLIST_PADRAO],
        "estados": [(e, _ESTADOS_ROTULO[e]) for e in ESTADOS_ITEM], "niveis": [(n, n.capitalize()) for n in NIVEIS_COMBUSTIVEL],
    }


@router.get("/contratos/{contrato_id}/encerrar")
def formulario_encerrar(request: Request, contrato_id: str, _: Sessao = Depends(exigir_dono)):
    registro = _ativo_ou_404(contrato_id)
    v = {**formulario.condicoes_do_encerramento(hoje_br(), registro["contrato"]["data_inicio"]),
         **formulario.vistoria_inicial(registro["moto"]["km_atual"])}
    return renderizar(request, "contratos/_form_encerrar.html", _contexto(registro, v))


@router.post("/contratos/{contrato_id}/encerrar/previa", dependencies=[Depends(validar_csrf)])
async def previa_encerrar(request: Request, contrato_id: str, _: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    registro = await run_in_threadpool(_ativo_ou_404, contrato_id)
    resumo = await run_in_threadpool(_previa, registro, entrada)
    return renderizar(request, "contratos/_previa_encerramento.html", {"resumo": resumo, "limite_impacto": LIMITE_IMPACTO})


def _encerrar(request, sessao, contrato_id, entrada):
    registro = _ativo_ou_404(contrato_id)
    contrato, cliente, moto = registro["contrato"], registro["cliente"], registro["moto"]
    v = {**formulario.texto_do_encerramento(entrada), **formulario.texto_da_vistoria(entrada)}
    contexto = _contexto(registro, v)

    def encerrar():
        dados = formulario.ler_encerramento(entrada, contrato["data_inicio"], moto["km_atual"])
        resumo = dados_contratos.previa_encerramento(contrato["id"], dados["data"], dados["valor_danos"])
        acoes_contratos.encerrar_contrato_com_vistoria(
            contrato["id"], dados["data"], dados["vistoria"], dados["valor_danos"], dados["descricao_danos"],
        )
        devolucao = resumo["devolucao"]
        aviso = mensagens.contrato_encerrado(
            cliente["nome"], formatar_placa(moto["placa"]),
            devolucao=devolucao["devolucao"] if resumo["caucao_recebida"] > 0 else None,
            desconto=devolucao["desconto"], excedente=devolucao["excedente"],
        )
        return _concluir(request, sessao, f"/contratos/{contrato['id']}", aviso)

    return _devolver_formulario(request, "contratos/_form_encerrar.html", contexto, encerrar)


@router.post("/contratos/{contrato_id}/encerrar", dependencies=[Depends(validar_csrf)])
async def encerrar(request: Request, contrato_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_encerrar, request, sessao, contrato_id, await _entrada(request))
