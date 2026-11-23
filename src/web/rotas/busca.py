"""Busca global (paleta de comandos): GET /busca devolve os resultados; o HTMX troca só o trecho da paleta.

Sem JavaScript a mesma rota abre uma página com o campo e a lista. `ocultar=1` (o modo "ocultar dados pessoais" do
Dashboard) mascara nomes, CPFs e placas nos resultados."""

from fastapi import APIRouter, Depends, Request

from src.domain import busca_global
from src.web import dados_busca
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


@router.get("/busca")
def busca(request: Request, q: str | None = None, ocultar: str | None = None, _: Sessao = Depends(exigir_dono)):
    termo = busca_global.normalizar_termo(q)
    contexto = {
        "titulo": "Buscar",
        "q": termo,
        "r": dados_busca.buscar(termo),
        "ocultar": ocultar == "1",
        "curto": 0 < len(termo) < busca_global.MINIMO_CARACTERES,
        "digitou": bool(termo),
    }
    htmx = request.headers.get("HX-Request") == "true" and not request.headers.get("HX-History-Restore-Request")
    return renderizar(request, "busca/_resultados.html" if htmx else "busca/pagina.html", contexto)
