"""Registrar vistoria: o mesmo formulário em diálogo (HTMX) e em página (sem JavaScript), em duas etapas.

Etapa 1 escolhe o contrato (só os que ainda não têm as duas vistorias); a etapa 2 traz o formulário já com o tipo
que falta, o km da moto e o checklist todo "ok". O POST valida campo a campo (inclusive as fotos, antes de gravar),
registra pela RPC e só então envia as fotos: se alguma falhar, a vistoria continua salva e o aviso diz quantas."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.domain import formulario_vistoria as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.domain.vistorias import CHECKLIST_PADRAO, ESTADOS_ITEM, NIVEIS_COMBUSTIVEL, rotulo_item
from src.domain.vistorias_lista import TIPO_ROTULO
from src.web import acoes_vistorias, dados_vistorias
from src.web.apresentacao import formatar_milhar, formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

PREFIXO_ITEM = "item_"
_ESTADOS_ROTULO = {"ok": "OK", "avaria": "Avaria", "ausente": "Ausente", "nao_aplicavel": "N/A"}
_ALTERAR_HX = ' hx-get="/vistorias/registrar" hx-target="#form-dialogo" hx-swap="outerHTML"'


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _modelo_do_formulario(request):
    return "vistorias/_form_registro.html" if _htmx(request) else "vistorias/registro.html"


def _uuid_ou_vazio(texto):
    try:
        return str(UUID((texto or "").strip()))
    except ValueError:
        return ""


def _para_registro_ou_404(contrato_id):
    registro = dados_vistorias.obter_para_registro(_uuid_ou_vazio(contrato_id))
    if registro is None:
        raise HTTPException(status_code=404)
    return registro


def _contexto(request, registro, v, erros=None, erro_geral=None):
    moto = registro["moto"]
    return {
        "titulo": "Registrar vistoria", "c": registro, "v": v, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": "/vistorias/registrar", "hoje": hoje_br().isoformat(), "limite_fotos": formulario.LIMITE_FOTOS,
        "alterar_hx": _ALTERAR_HX if _htmx(request) else "",
        "ajuda_km": f"Não pode ser menor que o km atual da moto ({formatar_milhar(moto['km_atual'])} km).",
        "tipos": [(t, TIPO_ROTULO[t]) for t in registro["faltantes"]],
        "itens_checklist": [(PREFIXO_ITEM + item, rotulo_item(item)) for item in CHECKLIST_PADRAO],
        "estados": [(e, _ESTADOS_ROTULO[e]) for e in ESTADOS_ITEM],
        "niveis": [(n, n.capitalize()) for n in NIVEIS_COMBUSTIVEL],
    }


@router.get("/vistorias/registrar")
def formulario_registro(request: Request, contrato: str | None = None, sessao: Sessao = Depends(exigir_dono)):
    if not contrato:
        modelo = "vistorias/_escolher.html" if _htmx(request) else "vistorias/escolher.html"
        return renderizar(request, modelo, {"titulo": "Registrar vistoria", "contratos": dados_vistorias.contratos_pendentes()})
    registro = _para_registro_ou_404(contrato)
    if not registro["faltantes"]:
        return _concluir(request, sessao, f"/vistorias/contrato/{registro['contrato']['id']}",
                         tipo="info", texto="Este contrato já tem as vistorias de entrega e de devolução.")
    v = formulario.registro_inicial(hoje_br(), registro["moto"]["km_atual"], registro["faltantes"])
    return renderizar(request, _modelo_do_formulario(request), _contexto(request, registro, v))


def _resumo_fotos(fotos):
    """(nome, tamanho, primeiros bytes) de cada foto, sem ler o arquivo inteiro."""
    resumo = []
    for foto in fotos:
        cabecalho = foto.file.read(formulario.BYTES_DA_ASSINATURA)
        foto.file.seek(0)
        resumo.append((foto.filename, foto.size or 0, cabecalho))
    return resumo


def _registrar(request, sessao, entrada, fotos):
    registro = _para_registro_ou_404(entrada.get("contrato"))
    contrato, moto = registro["contrato"], registro["moto"]
    contexto = _contexto(request, registro, formulario.texto_do_registro(entrada))

    def gravar():
        erros, dados = {}, None
        try:
            dados = formulario.ler_registro(
                entrada, hoje_br(), contrato["data_inicio"], moto["km_atual"], registro["faltantes"]
            )
        except ErroDeCampos as erro:
            erros.update(erro.erros)
        try:
            formulario.validar_fotos(_resumo_fotos(fotos))
        except ErroDeCampos as erro:
            erros.update(erro.erros)
        if erros:
            raise ErroDeCampos(erros)
        resultado = acoes_vistorias.registrar_vistoria(
            contrato["id"], moto["id"], dados["tipo"], dados["dia"], dados["vistoria"]
        )
        falhas = acoes_vistorias.anexar_fotos((resultado or {}).get("vistoria_id"), fotos)
        aviso = mensagens.vistoria_registrada(TIPO_ROTULO[dados["tipo"]].lower(), formatar_placa(moto["placa"]), falhas)
        return _concluir(request, sessao, f"/vistorias/contrato/{contrato['id']}", aviso)

    return _devolver_formulario(request, _modelo_do_formulario(request), contexto, gravar)


@router.post("/vistorias/registrar", dependencies=[Depends(validar_csrf)])
async def registrar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    enviado = await request.form()
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    fotos = [valor for chave, valor in enviado.multi_items()
             if chave == "fotos" and isinstance(valor, UploadFile) and valor.filename]
    return await run_in_threadpool(_registrar, request, sessao, entrada, fotos)
