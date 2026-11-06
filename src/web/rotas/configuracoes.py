"""Configurações: encargos por atraso, alertas e backup manual.

O formulário é uma página comum (sem diálogo): com erro volta a mesma página com a mensagem ao lado de cada campo; com
sucesso redireciona com o aviso. O backup é um POST (com CSRF) que responde com o ZIP para baixar, e a página continua
onde está. O arquivo traz dados pessoais, então só o dono o gera e a resposta nunca vai para cache."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.domain import erros as classificacao
from src.domain import formulario_configuracao as formulario, formulario_whatsapp, mensagens
from src.domain.formulario_moto import ErroDeCampos
from src.domain.whatsapp_painel import estado_da_instancia
from src.domain.configuracoes import LIMITE_INTEIRO, campos_alterados
from src.domain.valores import hoje_br
from src.web import acoes_configuracoes, acoes_whatsapp, dados_configuracoes
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()
logger = logging.getLogger(__name__)
_PAGINA = "configuracoes/pagina.html"


def _contexto(config, valores, erros=None, erro_geral=None):
    return {
        "titulo": "Configurações", "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
        "exemplo": dados_configuracoes.exemplo(config), "limite": LIMITE_INTEIRO,
        "w": formulario_whatsapp.valores_iniciais(config), "werros": {}, "werro_geral": None,
        "zap": {"estado": estado_da_instancia(config.get("whatsapp_ultimo_estado")),
                "ultima_rodada": config.get("whatsapp_ultima_rodada_em")},
    }


@router.get("/configuracoes")
def pagina(request: Request, _: Sessao = Depends(exigir_dono)):
    config = dados_configuracoes.obter()
    return renderizar(request, _PAGINA, _contexto(config, formulario.valores_iniciais(config)))


def _salvar(request, sessao, entrada):
    config = dados_configuracoes.obter()
    contexto = _contexto(config, formulario.texto_da_entrada(entrada))

    def gravar():
        dados = formulario.ler_configuracao(entrada)
        salvo = acoes_configuracoes.atualizar(dados)
        return _concluir(request, sessao, "/configuracoes", mensagens.configuracoes_salvas(campos_alterados(config, salvo)))

    return _devolver_formulario(request, _PAGINA, contexto, gravar)


@router.post("/configuracoes", dependencies=[Depends(validar_csrf)])
async def salvar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_salvar, request, sessao, await _entrada(request))


@router.post("/configuracoes/backup", dependencies=[Depends(validar_csrf)])
async def backup(_: Sessao = Depends(exigir_dono)):
    arquivo = await run_in_threadpool(dados_configuracoes.gerar_backup)
    return Response(arquivo, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="backup-{hoje_br().isoformat()}.zip"'})


def _salvar_whatsapp(request, sessao, entrada):
    """Controles do envio de WhatsApp: formulário próprio, com erros ao lado dos campos dele."""
    config = dados_configuracoes.obter()
    contexto = _contexto(config, formulario.valores_iniciais(config))
    contexto["w"] = formulario_whatsapp.texto_da_entrada(entrada)
    try:
        dados = formulario_whatsapp.ler_whatsapp(entrada)
        acoes_whatsapp.atualizar_controles(dados)
        return _concluir(request, sessao, "/configuracoes#cfg-whatsapp",
                         mensagens.whatsapp_controles_salvos(dados["whatsapp_ativo"], dados["whatsapp_modo_teste"]))
    except ErroDeCampos as erro:
        contexto.update(werros=erro.erros, werro_geral="Corrija os campos destacados.")
        status = 422
    except ValueError as erro:
        contexto.update(werro_geral=str(erro))
        status = 422
    except HTTPException:
        raise
    except Exception as erro:
        falha = classificacao.classificar_erro(erro)
        if falha.categoria == classificacao.SESSAO_EXPIRADA:
            raise
        logger.exception("Falha ao gravar os controles do WhatsApp")
        contexto.update(werro_geral=falha.mensagem)
        status = 503 if falha.recuperavel else 500
    return renderizar(request, _PAGINA, contexto, status=status)


@router.post("/configuracoes/whatsapp", dependencies=[Depends(validar_csrf)])
async def salvar_whatsapp(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_salvar_whatsapp, request, sessao, await _entrada(request))
