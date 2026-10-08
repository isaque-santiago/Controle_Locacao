"""Portal do Locatário: o contrato ativo, a troca de óleo (com foto do painel e da nota fiscal) e a troca de senha.

Pensado para o celular e sem JavaScript obrigatório: formulários comuns que voltam à mesma página, com a mensagem ao
lado do campo em caso de erro e um aviso depois de gravar. O locatário só enxerga e grava o que é dele: o contrato do
formulário é sempre procurado entre os contratos que a RPC devolve para ele, nunca aceito pelo identificador recebido."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.responses import RedirectResponse

from src.domain import formulario_portal as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.services.autenticacao import PAPEL_DONO, SenhaNaoAlterada, SessaoSupabaseInvalida
from src.web import acoes_portal, dados_portal
from src.web.dependencias import exigir_locatario, exigir_sessao, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

_PAGINA = "portal.html"
_ALVO_SENHA = "senha"


def _contexto(dados, alvo=None, km=None, erros=None, erro_geral=None):
    return {
        "titulo": "Portal do locatário", "d": dados, "alvo": alvo, "km_digitado": km or "",
        "erros": erros or {}, "erro_geral": erro_geral, "tamanho_minimo_senha": 8,
    }


@router.get("/portal")
def pagina(request: Request, sessao: Sessao = Depends(exigir_sessao)):
    if sessao.papel == PAPEL_DONO:
        return RedirectResponse("/", status_code=303)
    return renderizar(request, _PAGINA, _contexto(dados_portal.carregar()))


def _resumo_arquivo(arquivo):
    """(nome, tamanho, primeiros bytes) da imagem enviada, ou None se o campo veio vazio."""
    if arquivo is None:
        return None
    cabecalho = arquivo.file.read(formulario.BYTES_DA_ASSINATURA)
    arquivo.file.seek(0)
    return arquivo.filename, arquivo.size or 0, cabecalho


def _enviar_troca(request, sessao, contrato_id, entrada, arquivos):
    dados, contrato = dados_portal.contrato_do_locatario(contrato_id)
    if contrato is None:
        raise HTTPException(status_code=404)
    contexto = _contexto(dados, alvo=contrato_id, km=formulario.texto_da_troca(entrada)["km"])

    def gravar():
        if not contrato["plano_configurado"]:
            raise ValueError("O plano de troca de óleo desta moto ainda não foi configurado. Fale com o proprietário.")
        km = formulario.ler_troca_oleo(
            entrada, contrato, {campo: _resumo_arquivo(arquivo) for campo, arquivo in arquivos.items()}, contrato["multa"]
        )
        resultado = acoes_portal.registrar_troca_oleo(
            dados["cliente_id"], contrato, str(km),
            (arquivos["foto"].filename, arquivos["foto"].file.read()),
            (arquivos["nota"].filename, arquivos["nota"].file.read()),
            contrato["multa"],
        ) or {}
        return _concluir(request, sessao, "/portal", mensagens.troca_oleo_registrada(resultado.get("excedeu"), resultado.get("multa_valor")))

    return _devolver_formulario(request, _PAGINA, contexto, gravar)


@router.post("/portal/troca-oleo/{contrato_id}", dependencies=[Depends(validar_csrf)])
async def enviar_troca(request: Request, contrato_id: str, sessao: Sessao = Depends(exigir_locatario)):
    try:
        contrato_id = str(UUID(contrato_id))
    except ValueError:
        raise HTTPException(status_code=404)
    enviado = await request.form()
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    arquivos = {}
    for campo in ("foto", "nota"):
        arquivo = enviado.get(campo)
        arquivos[campo] = arquivo if isinstance(arquivo, UploadFile) and arquivo.filename else None
    return await run_in_threadpool(_enviar_troca, request, sessao, contrato_id, entrada, arquivos)


def _alterar_senha(request, sessao, entrada):
    contexto = _contexto(dados_portal.carregar(), alvo=_ALVO_SENHA)
    cpf = sessao.email.split("@")[0]

    def gravar():
        nova = formulario.ler_nova_senha(entrada.get("nova", ""), entrada.get("confirmacao", ""), cpf)
        try:
            acoes_portal.alterar_senha(request.app.state.servico, sessao.access_token, nova)
        except SenhaNaoAlterada as erro:
            raise ErroDeCampos({"nova": str(erro)}) from None
        except SessaoSupabaseInvalida:
            raise ValueError("Sua sessão expirou. Saia e entre de novo para trocar a senha.") from None
        return _concluir(request, sessao, "/portal", mensagens.senha_alterada())

    return _devolver_formulario(request, _PAGINA, contexto, gravar)


@router.post("/portal/senha", dependencies=[Depends(validar_csrf)])
async def alterar_senha(request: Request, sessao: Sessao = Depends(exigir_locatario)):
    enviado = await request.form()
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    return await run_in_threadpool(_alterar_senha, request, sessao, entrada)
