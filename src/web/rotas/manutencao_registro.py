"""Registro de manutenção em diálogo HTMX ou página completa."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from src.domain import formulario_manutencao as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.web import acoes_manutencao, dados_manutencao
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()
_DIALOGO = "manutencao/_form_registro.html"
_PAGINA = "manutencao/registro.html"


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _moto(frota, moto_id):
    return next((m for m in frota if m["id"] == moto_id), frota[0] if frota else None)


def _contexto(valores, erros=None, erro_geral=None):
    frota, catalogo = dados_manutencao.opcoes_do_registro()
    moto = _moto(frota, valores.get("moto_id"))
    if moto and not valores.get("moto_id"):
        valores = {**valores, "moto_id": moto["id"], "moto_id_referencia": moto["id"], "km": str(moto["km_atual"])}
    return {
        "titulo": "Registrar manutenção", "acao": "/manutencao/registrar", "acao_previa": "/manutencao/registrar/previa",
        "v": valores, "erros": erros or {}, "erro_geral": erro_geral, "frota": frota, "catalogo": catalogo,
        "moto": moto, "previa": formulario.previa(valores, catalogo), "extras_ids": formulario.ids_extras(valores),
    }


@router.get("/manutencao/registrar")
def abrir(request: Request, _: Sessao = Depends(exigir_dono)):
    frota, _ = dados_manutencao.opcoes_do_registro()
    valores = formulario.valores_iniciais(hoje_br(), frota[0] if frota else None)
    valores["chave_operacao"] = str(uuid4())
    return renderizar(request, _DIALOGO if _htmx(request) else _PAGINA, _contexto(valores))


@router.post("/manutencao/registrar/previa", dependencies=[Depends(validar_csrf)])
async def atualizar_previa(request: Request, _: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    valores = formulario.alterar_linhas(formulario.texto_da_entrada(entrada), entrada.get("acao_linha"))
    if valores.get("moto_id") != valores.get("moto_id_referencia"):
        frota, _ = dados_manutencao.opcoes_do_registro()
        moto = _moto(frota, valores.get("moto_id"))
        if moto:
            valores["km"] = str(moto["km_atual"])
            valores["moto_id_referencia"] = moto["id"]
    return renderizar(request, "manutencao/_campos_registro.html", _contexto(valores))


def _registrar(request, sessao, entrada):
    valores = formulario.texto_da_entrada(entrada)
    contexto = _contexto(valores)

    def gravar():
        frota = contexto["frota"]
        moto = next((m for m in frota if m["id"] == valores.get("moto_id")), None)
        if not frota:
            raise ValueError("Cadastre uma moto ativa antes de registrar manutenções.")
        if moto is None:
            raise ErroDeCampos({"moto_id": "Moto: escolha uma das motos disponíveis."})
        if valores.get("moto_id_referencia") != moto["id"]:
            contexto["v"] = {**valores, "km": str(moto["km_atual"]), "moto_id_referencia": moto["id"]}
            raise ErroDeCampos({"km": "Quilometragem: a moto mudou; confira a leitura atualizada e salve novamente."})
        chave = (valores.get("chave_operacao") or "").strip()[:64] or str(uuid4())
        dados = formulario.ler(valores, moto, contexto["catalogo"])
        acoes_manutencao.registrar(dados, chave)
        custo = dados["custo_mao_obra"] + sum((i["quantidade"] * i["valor_unitario"] for i in dados["itens"]), start=0)
        aviso = mensagens.manutencao_registrada(formatar_placa(moto["placa"]), dados["status"] == "concluida", custo)
        return _concluir(request, sessao, "/manutencao?aba=historico", aviso)

    return _devolver_formulario(request, _DIALOGO if _htmx(request) else _PAGINA, contexto, gravar)


@router.post("/manutencao/registrar", dependencies=[Depends(validar_csrf)])
async def registrar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_registrar, request, sessao, await _entrada(request))
