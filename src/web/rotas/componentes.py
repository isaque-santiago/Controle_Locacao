"""Catálogo visual dos componentes. Só existe com LOCACAO_AMBIENTE=dev.

Mostra dados fictícios e dispensa login para a conferência visual (largura, tema, teclado);
em produção a rota nem é registrada."""

from fastapi import APIRouter, Request

from src.web.templates import renderizar

router = APIRouter()


@router.get("/componentes")
def catalogo(request: Request):
    return renderizar(
        request,
        "componentes.html",
        {
            "titulo": "Componentes",
            "usuario_nome": "Usuário de teste",
            "catalogo_sem_login": True,
        },
    )
