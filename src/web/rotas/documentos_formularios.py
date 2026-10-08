"""Novo e editar documento da moto: o mesmo formulário em diálogo (HTMX) e em página (sem JavaScript).

O comprovante (PDF ou imagem) é opcional e validado antes de gravar. O documento é gravado primeiro; se o envio do
comprovante falhar, o documento continua salvo e o aviso pede para anexá-lo de novo pela edição. No cadastro novo a
`chave_operacao` torna o reenvio do formulário idempotente."""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.domain import documentos_lista, formulario_documento as formulario, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.web import acoes_documentos, dados_documentos
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario
from src.web.sessao import Sessao
from src.web.templates import renderizar

logger = logging.getLogger(__name__)
router = APIRouter()

_TAMANHO_MAXIMO_CHAVE = 64


def _htmx(request):
    return request.headers.get("HX-Request") == "true"


def _modelo(request):
    return "documentos/_form_documento.html" if _htmx(request) else "documentos/documento.html"


def _uuid_ou_vazio(texto):
    try:
        return str(UUID((texto or "").strip()))
    except ValueError:
        return ""


def _documento_ou_404(documento_id):
    registro = dados_documentos.obter_documento(_uuid_ou_vazio(documento_id))
    if registro is None:
        raise HTTPException(status_code=404)
    return registro


def _contexto(registro, v, erros=None, erro_geral=None):
    editando = registro is not None
    frota = dados_documentos.motos_do_cadastro(registro["moto"]["id"] if editando else None)
    return {
        "titulo": "Editar documento" if editando else "Novo documento", "editando": editando,
        "acao": f"/documentos/{registro['documento']['id']}/editar" if editando else "/documentos/novo",
        "v": v, "erros": erros or {}, "erro_geral": erro_geral, "registro": registro,
        "tem_comprovante": editando and bool(registro["documento"].get("arquivo_path")),
        "motos": [(m["id"], f"{formatar_placa(m['placa'])} · {m['marca']} {m['modelo']}") for m in frota],
        "tipos": list(documentos_lista.TIPOS_ROTULO.items()),
    }


@router.get("/documentos/novo")
def formulario_novo(request: Request, moto: str | None = None, tipo: str | None = None, ano: str | None = None,
                    _: Sessao = Depends(exigir_dono)):
    """Os parâmetros preenchem o cadastro sugerido depois de regularizar (moto, tipo e ano seguinte)."""
    ids = {m["id"] for m in dados_documentos.motos_do_cadastro()}
    ano_sugerido = int(ano) if (ano or "").isdigit() else None
    v = formulario.documento_inicial(hoje_br(), moto if moto in ids else None, tipo, ano_sugerido)
    v["chave_operacao"] = str(uuid4())
    return renderizar(request, _modelo(request), _contexto(None, v))


@router.get("/documentos/{documento_id}/editar")
def formulario_editar(request: Request, documento_id: str, _: Sessao = Depends(exigir_dono)):
    registro = _documento_ou_404(documento_id)
    return renderizar(request, _modelo(request), _contexto(registro, formulario.valores_do_documento(registro["documento"])))


def _resumo_comprovante(arquivo):
    cabecalho = arquivo.file.read(formulario.BYTES_DA_ASSINATURA)
    arquivo.file.seek(0)
    return arquivo.filename, arquivo.size or 0, cabecalho


def _gravar(request, sessao, entrada, arquivo, registro):
    editando = registro is not None
    v = {**formulario.texto_do_documento(entrada), "chave_operacao": (entrada.get("chave_operacao") or "").strip()[:_TAMANHO_MAXIMO_CHAVE] or str(uuid4())}
    contexto = _contexto(registro, v)
    motos_validas = {m[0] for m in contexto["motos"]}

    def gravar():
        erros, dados = {}, None
        try:
            dados = formulario.ler_documento(entrada, motos_validas, registro["moto"]["id"] if editando else None)
        except ErroDeCampos as erro:
            erros.update(erro.erros)
        if arquivo is not None:
            try:
                formulario.validar_comprovante(*_resumo_comprovante(arquivo))
            except ErroDeCampos as erro:
                erros.update(erro.erros)
        if erros:
            raise ErroDeCampos(erros)
        if editando:
            salvo = acoes_documentos.atualizar_documento(registro["documento"]["id"], dados)
        else:
            salvo = acoes_documentos.criar_documento(dados, v["chave_operacao"])
        moto = next(m for m in contexto["motos"] if m[0] == dados["moto_id"])[1].split(" · ")[0]
        descricao = f"{documentos_lista.TIPOS_ROTULO[dados['tipo']]} {dados['ano_referencia']} da moto {moto}"
        if arquivo is not None:
            try:
                acoes_documentos.anexar_comprovante(salvo["id"], dados["moto_id"], arquivo)
            except Exception:
                logger.exception("Falha ao enviar o comprovante do documento %s", salvo["id"])
                return _concluir(
                    request, sessao, "/documentos", tipo="atencao",
                    texto=f"Documento {descricao} salvo, mas o comprovante não foi enviado. Edite o documento para anexá-lo de novo.",
                )
        return _concluir(request, sessao, "/documentos", mensagens.documento_salvo(descricao, novo=not editando))

    return _devolver_formulario(request, _modelo(request), contexto, gravar)


async def _ler_envio(request):
    enviado = await request.form()
    entrada = {chave: valor for chave, valor in enviado.items() if isinstance(valor, str)}
    arquivo = next((valor for chave, valor in enviado.multi_items()
                    if chave == "comprovante" and isinstance(valor, UploadFile) and valor.filename), None)
    return entrada, arquivo


@router.post("/documentos/novo", dependencies=[Depends(validar_csrf)])
async def criar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    entrada, arquivo = await _ler_envio(request)
    return await run_in_threadpool(_gravar, request, sessao, entrada, arquivo, None)


@router.post("/documentos/{documento_id}/editar", dependencies=[Depends(validar_csrf)])
async def editar(request: Request, documento_id: str, sessao: Sessao = Depends(exigir_dono)):
    entrada, arquivo = await _ler_envio(request)
    registro = await run_in_threadpool(_documento_ou_404, documento_id)
    return await run_in_threadpool(_gravar, request, sessao, entrada, arquivo, registro)
