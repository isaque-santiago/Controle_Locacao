"""Novo contrato: assistente de quatro etapas (Cliente, Moto, Condições, Confirmar).

Cada etapa tem URL própria (`/contratos/novo?etapa=N`) e funciona sem JavaScript. O que já foi escolhido ou digitado
fica no rascunho da sessão (`sessao.rascunho_contrato`), inclusive texto inválido, para voltar e revisar etapas
anteriores sem perder o progresso. O rascunho some ao concluir ou ao iniciar outro contrato."""

from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from src.domain import contratos_lista, formulario_contrato as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.domain.vistorias import CHECKLIST_PADRAO, ESTADOS_ITEM, NIVEIS_COMBUSTIVEL, rotulo_item
from src.web import acoes_contratos, dados_contratos
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

ETAPAS = (("Cliente", "Quem vai alugar"), ("Moto", "Disponível"), ("Condições", "Prazo e valores"), ("Confirmar", "Vistoria e agenda"))
_ESTADOS_ROTULO = {"ok": "OK", "avaria": "Avaria", "ausente": "Ausente", "nao_aplicavel": "N/A"}
_BASE = "/contratos/novo"
PREFIXO = formulario.PREFIXO_ITEM


def _so_resultado(request):
    return (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "resultado"
            and not request.headers.get("HX-History-Restore-Request"))


def _selecionados(rascunho):
    """Cliente e moto do rascunho que ainda podem ser usados; o que sumiu ou ficou indisponível é descartado."""
    cliente = dados_contratos.cliente_para_contrato(rascunho.get("cliente_id"))
    moto = dados_contratos.moto_para_contrato(rascunho.get("moto_id"))
    if cliente is None:
        rascunho.pop("cliente_id", None)
    if moto is None:
        rascunho.pop("moto_id", None)
    return cliente, moto


def _etapa_liberada(rascunho, cliente, moto):
    """Maior etapa que o rascunho permite abrir."""
    if cliente is None:
        return 1
    if moto is None:
        return 2
    return 4 if rascunho.get("condicoes") else 3


def _passos(etapa, cliente, moto):
    detalhes = {1: cliente["nome"] if cliente else None, 2: formatar_placa(moto["placa"]) if moto else None}
    return [
        {"titulo": titulo, "detalhe": detalhes.get(n) or sub,
         "estado": "feito" if n < etapa else ("atual" if n == etapa else "")}
        for n, (titulo, sub) in enumerate(ETAPAS, start=1)
    ]


def _contexto(etapa, rascunho, cliente, moto, **extra):
    return {
        "titulo": "Novo contrato", "etapa": etapa, "passos": _passos(etapa, cliente, moto), "total_etapas": len(ETAPAS),
        "subtitulo_etapa": ETAPAS[etapa - 1][0], "cliente": cliente, "moto": moto, "base": _BASE,
        "periodos_rotulo": contratos_lista.PERIODOS_ROTULO, **extra,
    }


def _extra_confirmar(rascunho, moto):
    """Resumo, prévia da agenda e campos da vistoria de entrega (etapa 4)."""
    condicoes = rascunho["condicoes"]
    digitada = rascunho.get("vistoria_texto") if rascunho.get("vistoria_moto") == moto["id"] else None
    return {
        "condicoes": condicoes, "agenda": dados_contratos.previa_agenda(condicoes), "tem_caucao": Decimal(condicoes["caucao_valor"]) > 0,
        "v": digitada or formulario.vistoria_inicial(moto["km_atual"]),
        "itens_checklist": [(PREFIXO + item, rotulo_item(item)) for item in CHECKLIST_PADRAO],
        "estados": [(e, _ESTADOS_ROTULO[e]) for e in ESTADOS_ITEM],
        "niveis": [(n, n.capitalize()) for n in NIVEIS_COMBUSTIVEL],
    }


def _renderizar_etapa(request, etapa, rascunho, cliente, moto, erros=None, erro_geral=None, busca="", status=200):
    extra = {"erros": erros or {}, "erro_geral": erro_geral, "busca": busca}
    if etapa == 1:
        extra["candidatos"] = dados_contratos.candidatos_cliente(busca)
        extra["selecionado_id"] = rascunho.get("cliente_id")
    elif etapa == 2:
        extra["candidatas"] = dados_contratos.candidatas_moto(busca)
        extra["selecionado_id"] = rascunho.get("moto_id")
    elif etapa == 3:
        extra["v"] = rascunho.get("condicoes_texto") or formulario.condicoes_iniciais(hoje_br(), moto.get("valor_locacao_sugerido"))
    else:
        extra.update(_extra_confirmar(rascunho, moto))
    modelo = "contratos/novo/_selecao.html" if etapa in (1, 2) and _so_resultado(request) else "contratos/novo/novo.html"
    return renderizar(request, modelo, _contexto(etapa, rascunho, cliente, moto, **extra), status=status)


def _ir(etapa, busca=""):
    parametros = {"etapa": etapa, **({"q": busca} if busca else {})}
    return RedirectResponse(f"{_BASE}?{urlencode(parametros)}", status_code=303)


@router.get("/contratos/novo/iniciar")
def iniciar(sessao: Sessao = Depends(exigir_dono)):
    """Começa um contrato do zero: descarta o rascunho anterior."""
    sessao.rascunho_contrato.clear()
    return _ir(1)


@router.get("/contratos/novo")
def etapa(request: Request, etapa: str | None = None, q: str | None = None, sessao: Sessao = Depends(exigir_dono)):
    rascunho = sessao.rascunho_contrato
    cliente, moto = _selecionados(rascunho)
    liberada = _etapa_liberada(rascunho, cliente, moto)
    try:
        pedida = int(etapa) if etapa else 1
    except ValueError:
        pedida = 1
    numero = min(max(pedida, 1), liberada)
    if numero != pedida:
        return _ir(numero)
    return _renderizar_etapa(request, numero, rascunho, cliente, moto, busca=(q or "").strip()[:80])


@router.post("/contratos/novo/cliente", dependencies=[Depends(validar_csrf)])
async def escolher_cliente(request: Request, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    busca = (entrada.get("q") or "").strip()[:80]
    cliente = await run_in_threadpool(dados_contratos.cliente_para_contrato, entrada.get("cliente_id"))
    if cliente is None:
        sessao.avisos.append({"tipo": "erro", "texto": "Este cliente não pode alugar: confira se está ativo."})
    else:
        sessao.rascunho_contrato["cliente_id"] = cliente["id"]
    return _ir(1, busca)


@router.post("/contratos/novo/moto", dependencies=[Depends(validar_csrf)])
async def escolher_moto(request: Request, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    busca = (entrada.get("q") or "").strip()[:80]
    moto = await run_in_threadpool(dados_contratos.moto_para_contrato, entrada.get("moto_id"))
    if moto is None:
        sessao.avisos.append({"tipo": "erro", "texto": "Esta moto não está mais disponível."})
    else:
        sessao.rascunho_contrato["moto_id"] = moto["id"]
    return _ir(2, busca)


def _condicoes(request, sessao, entrada):
    rascunho = sessao.rascunho_contrato
    cliente, moto = _selecionados(rascunho)
    if cliente is None or moto is None:
        return _ir(_etapa_liberada(rascunho, cliente, moto))
    rascunho["condicoes_texto"] = formulario.texto_das_condicoes(entrada)
    if entrada.get("acao") == "voltar":
        return _ir(2)
    contexto = _contexto(3, rascunho, cliente, moto, v=rascunho["condicoes_texto"], erros={}, erro_geral=None, busca="")

    def avancar():
        rascunho["condicoes"] = formulario.ler_condicoes(entrada)
        return _ir(4)

    return _devolver_formulario(request, "contratos/novo/novo.html", contexto, avancar)


@router.post("/contratos/novo/condicoes", dependencies=[Depends(validar_csrf)])
async def enviar_condicoes(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_condicoes, request, sessao, await _entrada(request))


def _criar(request, sessao, entrada):
    rascunho = sessao.rascunho_contrato
    cliente, moto = _selecionados(rascunho)
    condicoes = rascunho.get("condicoes")
    if cliente is None or moto is None or not condicoes:
        return _ir(_etapa_liberada(rascunho, cliente, moto))
    rascunho["vistoria_texto"] = formulario.texto_da_vistoria(entrada)
    rascunho["vistoria_moto"] = moto["id"]
    if entrada.get("acao") == "voltar":
        return _ir(3)
    contexto = _contexto(
        4, rascunho, cliente, moto, erros={}, erro_geral=None, busca="",
        **{**_extra_confirmar(rascunho, moto), "v": rascunho["vistoria_texto"]},
    )

    def criar():
        vistoria = formulario.ler_vistoria(entrada, moto["km_atual"])
        resultado = acoes_contratos.criar_contrato_com_vistoria(
            {"moto_id": moto["id"], "cliente_id": cliente["id"], "km_inicial": vistoria["km"], **condicoes}, vistoria,
        )
        rascunho.clear()
        destino = f"/contratos/{resultado['contrato_id']}" if resultado and resultado.get("contrato_id") else "/contratos"
        return _concluir(request, sessao, destino, mensagens.contrato_criado(cliente["nome"], formatar_placa(moto["placa"])))

    return _devolver_formulario(request, "contratos/novo/novo.html", contexto, criar)


@router.post("/contratos/novo/criar", dependencies=[Depends(validar_csrf)])
async def criar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_criar, request, sessao, await _entrada(request))


@router.post("/contratos/novo/cancelar", dependencies=[Depends(validar_csrf)])
def cancelar(sessao: Sessao = Depends(exigir_dono)):
    sessao.rascunho_contrato.clear()
    return RedirectResponse("/contratos", status_code=303)
