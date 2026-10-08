"""Páginas: saúde, Dashboard do dono, portal do locatário e telas em migração."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from src.services.autenticacao import PAPEL_DONO, PAPEL_LOCATARIO
from src.web import dados_painel, navegacao
from src.web.dependencias import exigir_dono, exigir_sessao
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


@router.api_route("/saude", methods=["GET", "HEAD"])
def saude():
    """Verificação de saúde para o proxy e o monitoramento: não exige login nem toca o banco."""
    return {"status": "ok"}


@router.get("/")
def inicio(request: Request, sessao: Sessao = Depends(exigir_sessao)):
    if sessao.papel == PAPEL_LOCATARIO:
        return RedirectResponse("/portal", status_code=303)
    return renderizar(request, "dashboard.html", {"titulo": "Dashboard", "d": dados_painel.carregar()})


@router.get("/portal")
def portal(request: Request, sessao: Sessao = Depends(exigir_sessao)):
    if sessao.papel == PAPEL_DONO:
        return RedirectResponse("/", status_code=303)
    return renderizar(request, "portal.html", {"titulo": "Portal do locatário"})


def _registrar_em_migracao(item: navegacao.ItemNavegacao) -> None:
    def pagina(request: Request, _: Sessao = Depends(exigir_dono)):
        return renderizar(request, "em_migracao.html", {"titulo": item.rotulo, "item": item})

    pagina.__name__ = f"em_migracao_{item.chave}"
    router.add_api_route(item.caminho, pagina, methods=["GET"])


# As demais telas seguem no Streamlit até a sua fase; a rota existe para o menu não dar 404.
_JA_MIGRADAS = {
    navegacao.DASHBOARD,
    navegacao.MOTOS,
    navegacao.CLIENTES,
    navegacao.CONTRATOS,
    navegacao.COBRANCAS,
    navegacao.MANUTENCAO,
    navegacao.DOCUMENTOS,
    navegacao.RELATORIOS,
    navegacao.CONFIGURACOES,
    navegacao.VISTORIAS,
}
for _item in navegacao.TODOS:
    if _item not in _JA_MIGRADAS:
        _registrar_em_migracao(_item)
