"""Motos: formulários em diálogo (cadastrar, editar, atualizar km, regularizar documento) e inativar/reativar.

Os diálogos abrem por GET (o HTMX traz o formulário para #dlg-form). O POST valida campo a campo:
com erro devolve o mesmo formulário com a mensagem ao lado do campo (e o diálogo continua aberto);
com sucesso guarda um aviso na sessão e manda o navegador para a página (HX-Redirect)."""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from src.domain import erros, mensagens
from src.domain.entradas import texto_moeda, texto_placa
from src.domain.formulario_moto import ErroDeCampos, ler_km, ler_moto, ler_regularizacao
from src.domain.valores import hoje_br
from src.web import acoes_motos, dados_motos
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos import _moto_ou_404
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()

_TAMANHO_MAXIMO_CHAVE = 64


# ------------------------------------------------------------------ apoio --

def _tipo_do_aviso(aviso) -> str:
    if aviso.tom == mensagens.TOAST:
        return "sucesso"
    return "atencao" if aviso.atencao else "info"


def _concluir(request: Request, sessao: Sessao, destino: str, aviso=None, tipo: str | None = None, texto: str | None = None):
    """Guarda o aviso para a próxima página e leva o navegador ao destino."""
    sessao.avisos.append(
        {"tipo": tipo or _tipo_do_aviso(aviso), "texto": texto or aviso.texto}
    )
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": destino})
    return RedirectResponse(destino, status_code=303)


def _devolver_formulario(request: Request, modelo: str, contexto: dict, acao):
    """Roda `acao` (o POST); se falhar, devolve o formulário com a mensagem de erro e o diálogo aberto."""
    try:
        return acao()
    except ErroDeCampos as erro:
        contexto.update(erros=erro.erros, erro_geral="Corrija os campos destacados.")
        status = 422
    except ValueError as erro:
        contexto.update(erro_geral=str(erro))
        status = 422
    except HTTPException:
        raise
    except Exception as erro:
        falha = erros.classificar_erro(erro)
        if falha.categoria == erros.SESSAO_EXPIRADA:
            raise
        logger.exception("Falha ao gravar em %s", request.url.path)
        contexto.update(erro_geral=falha.mensagem)
        status = 503 if falha.recuperavel else 500
    return renderizar(request, modelo, contexto, status=status)


async def _entrada(request: Request) -> dict:
    return {chave: valor for chave, valor in (await request.form()).items() if isinstance(valor, str)}


# ------------------------------------------------------------- cadastrar --

def _valores_da_moto(moto: dict | None) -> dict:
    """Texto inicial dos campos: o que a moto já tem, ou os padrões de um cadastro novo."""
    moto = moto or {}
    ano = str(hoje_br().year)
    return {
        "placa": texto_placa(moto.get("placa")),
        "marca": moto.get("marca") or "",
        "modelo": moto.get("modelo") or "",
        "renavam": moto.get("renavam") or "",
        "chassi": moto.get("chassi") or "",
        "cor": moto.get("cor") or "",
        "ano_fabricacao": str(moto.get("ano_fabricacao") or ano),
        "ano_modelo": str(moto.get("ano_modelo") or ano),
        "km_atual": "0",
        "valor_aquisicao": texto_moeda(moto.get("valor_aquisicao")),
        "valor_locacao_sugerido": texto_moeda(moto.get("valor_locacao_sugerido")),
        "data_aquisicao": str(moto.get("data_aquisicao") or "")[:10],
        "observacoes": moto.get("observacoes") or "",
    }


@router.get("/motos/nova")
def formulario_nova(request: Request, _: Sessao = Depends(exigir_dono)):
    contexto = {"nova": True, "acao": "/motos/nova", "valores": _valores_da_moto(None), "erros": {}}
    return renderizar(request, "motos/_form_moto.html", contexto)


@router.post("/motos/nova", dependencies=[Depends(validar_csrf)])
async def cadastrar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_cadastrar, request, sessao, entrada)


def _cadastrar(request: Request, sessao: Sessao, entrada: dict):
    contexto = {"nova": True, "acao": "/motos/nova", "valores": entrada, "erros": {}}

    def acao():
        dados = ler_moto(entrada, nova=True)
        moto = acoes_motos.criar_moto(dados)
        aviso = mensagens.moto_salva(formatar_placa(dados["placa"]), nova=True)
        return _concluir(request, sessao, f"/motos/{moto['id']}", aviso)

    return _devolver_formulario(request, "motos/_form_moto.html", contexto, acao)


# ----------------------------------------------------------------- editar --

@router.get("/motos/{moto_id}/editar")
def formulario_editar(request: Request, moto_id: str, _: Sessao = Depends(exigir_dono)):
    moto = _moto_ou_404(moto_id)
    contexto = {"nova": False, "acao": f"/motos/{moto_id}/editar", "valores": _valores_da_moto(moto), "erros": {}}
    return renderizar(request, "motos/_form_moto.html", contexto)


@router.post("/motos/{moto_id}/editar", dependencies=[Depends(validar_csrf)])
async def editar(request: Request, moto_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_editar, request, sessao, moto_id, entrada)


def _editar(request: Request, sessao: Sessao, moto_id: str, entrada: dict):
    _moto_ou_404(moto_id)
    contexto = {"nova": False, "acao": f"/motos/{moto_id}/editar", "valores": entrada, "erros": {}}

    def acao():
        dados = ler_moto(entrada, nova=False)
        acoes_motos.atualizar_moto(moto_id, dados)
        aviso = mensagens.moto_salva(formatar_placa(dados["placa"]), nova=False)
        return _concluir(request, sessao, f"/motos/{moto_id}", aviso)

    return _devolver_formulario(request, "motos/_form_moto.html", contexto, acao)


# --------------------------------------------------------------------- km --

def _contexto_km(moto: dict, valores: dict) -> dict:
    return {
        "moto": moto,
        "acao": f"/motos/{moto['id']}/km",
        "valores": valores,
        "erros": {},
    }


@router.get("/motos/{moto_id}/km")
def formulario_km(request: Request, moto_id: str, _: Sessao = Depends(exigir_dono)):
    moto = _moto_ou_404(moto_id)
    valores = {"km": str(moto["km_atual"]), "chave_operacao": str(uuid4())}
    return renderizar(request, "motos/_form_km.html", _contexto_km(moto, valores))


@router.post("/motos/{moto_id}/km", dependencies=[Depends(validar_csrf)])
async def registrar_km(request: Request, moto_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_registrar_km, request, sessao, moto_id, entrada)


def _registrar_km(request: Request, sessao: Sessao, moto_id: str, entrada: dict):
    moto = _moto_ou_404(moto_id)
    chave = (entrada.get("chave_operacao") or "").strip()[:_TAMANHO_MAXIMO_CHAVE]
    entrada = {**entrada, "chave_operacao": chave or str(uuid4())}
    contexto = _contexto_km(moto, entrada)

    def acao():
        km, confirmar = ler_km(entrada)
        acoes_motos.registrar_km(moto_id, km, confirmar, entrada["chave_operacao"])
        aviso = mensagens.km_atualizado(formatar_placa(moto["placa"]), km)
        return _concluir(request, sessao, f"/motos/{moto_id}", aviso)

    return _devolver_formulario(request, "motos/_form_km.html", contexto, acao)


# --------------------------------------------------------------- situação --

@router.post("/motos/{moto_id}/situacao", dependencies=[Depends(validar_csrf)])
def alterar_situacao(request: Request, moto_id: str, sessao: Sessao = Depends(exigir_dono)):
    """Inativa a moto disponível ou reativa a inativa (botão da ficha, sem diálogo)."""
    moto = _moto_ou_404(moto_id)
    destino = f"/motos/{moto_id}"
    if moto["status"] not in ("disponivel", "inativa"):
        return _concluir(
            request, sessao, destino, tipo="erro",
            texto="Só é possível inativar ou reativar motos disponíveis ou inativas; esta moto está em uso.",
        )
    inativando = moto["status"] != "inativa"
    try:
        acoes_motos.alterar_situacao(moto_id, inativando)
    except Exception as erro:
        falha = erros.classificar_erro(erro)
        if falha.categoria == erros.SESSAO_EXPIRADA:
            raise
        logger.exception("Falha ao alterar a situação da moto %s", moto_id)
        return _concluir(request, sessao, destino, tipo="erro", texto=falha.mensagem)
    return _concluir(request, sessao, destino, mensagens.moto_status_alterado(formatar_placa(moto["placa"]), inativando))


# ----------------------------------------------------------- documentos --

def _documento_da_moto(moto_id: str, documento_id: str) -> dict:
    try:
        UUID(documento_id)
    except ValueError:
        raise HTTPException(status_code=404)
    documento = acoes_motos.obter_documento(documento_id)
    if documento is None or documento.get("moto_id") != moto_id:
        raise HTTPException(status_code=404)
    return documento


def _contexto_regularizacao(moto_id: str, documento: dict, valores: dict) -> dict:
    return {
        "documento": documento,
        "acao": f"/motos/{moto_id}/documentos/{documento['id']}/regularizar",
        "valores": valores,
        "erros": {},
    }


@router.get("/motos/{moto_id}/documentos/{documento_id}/regularizar")
def formulario_regularizar(request: Request, moto_id: str, documento_id: str, _: Sessao = Depends(exigir_dono)):
    _moto_ou_404(moto_id)
    documento = _documento_da_moto(moto_id, documento_id)
    contexto = _contexto_regularizacao(moto_id, documento, {"data": hoje_br().isoformat()})
    return renderizar(request, "motos/_form_regularizar.html", contexto)


@router.post("/motos/{moto_id}/documentos/{documento_id}/regularizar", dependencies=[Depends(validar_csrf)])
async def regularizar(request: Request, moto_id: str, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada = await _entrada(request)
    return await run_in_threadpool(_regularizar, request, sessao, moto_id, documento_id, entrada)


def _regularizar(request: Request, sessao: Sessao, moto_id: str, documento_id: str, entrada: dict):
    _moto_ou_404(moto_id)
    documento = _documento_da_moto(moto_id, documento_id)
    contexto = _contexto_regularizacao(moto_id, documento, entrada)

    def acao():
        if documento.get("regularizado"):
            raise ValueError("Este documento já foi regularizado.")
        data = ler_regularizacao(entrada)
        acoes_motos.regularizar_documento(documento_id, data)
        descricao = f"{documento['tipo'].upper()} {documento.get('ano_referencia') or ''}".strip()
        aviso = mensagens.documento_regularizado(descricao)
        return _concluir(request, sessao, f"/motos/{moto_id}?aba=documentos", aviso)

    return _devolver_formulario(request, "motos/_form_regularizar.html", contexto, acao)
