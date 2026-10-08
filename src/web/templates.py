"""Ambiente Jinja2 e função de renderização comum a todas as rotas."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from src.web import navegacao
from src.web.apresentacao import (
    TOM_STATUS_MOTO,
    formatar_data,
    formatar_milhar,
    formatar_moeda,
    formatar_moeda_compacta,
    formatar_placa,
    nome_de_exibicao,
    rotulo_tipo_cobranca,
    tema_do_cookie,
)
from src.domain.entradas import formatar_telefone
from src.domain.formatadores import mascarar_cpf

RAIZ = Path(__file__).resolve().parents[2]
PASTA_ESTATICOS = RAIZ / "static"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def url_estatico(caminho: str) -> str:
    """URL de um arquivo de /static com a data de modificação, para o navegador não usar cópia velha."""
    try:
        versao = int((PASTA_ESTATICOS / caminho).stat().st_mtime)
    except OSError:
        versao = 0
    return f"/static/{caminho}?v={versao}"


templates.env.globals.update(
    url_estatico=url_estatico,
    grupos_nav=navegacao.GRUPOS,
    barra_inferior=navegacao.BARRA_INFERIOR,
    folha_mais=navegacao.FOLHA_MAIS,
    item_ativo=navegacao.item_ativo,
    mais_esta_ativo=navegacao.mais_esta_ativo,
)
templates.env.filters["moeda"] = formatar_moeda
templates.env.filters["tipo_cobranca"] = rotulo_tipo_cobranca
templates.env.filters["data_br"] = formatar_data
templates.env.filters["moeda_compacta"] = formatar_moeda_compacta
templates.env.filters["placa_br"] = formatar_placa
templates.env.filters["milhar"] = formatar_milhar
templates.env.filters["cpf_mascarado"] = mascarar_cpf
templates.env.filters["telefone_br"] = formatar_telefone
templates.env.globals["tom_status_moto"] = TOM_STATUS_MOTO


def _consumir_avisos(sessao, nome_do_modelo: str) -> list:
    """Avisos guardados na sessão, entregues uma única vez e só a páginas inteiras (não a trechos HTMX)."""
    if sessao is None or nome_do_modelo.rsplit("/", 1)[-1].startswith("_"):
        return []
    avisos, sessao.avisos[:] = list(sessao.avisos), []
    return avisos


def renderizar(
    request: Request,
    nome: str,
    contexto: dict | None = None,
    status: int = 200,
):
    """Renderiza um template com o contexto comum (usuário, CSRF, tema, caminho atual)."""
    sessao = getattr(request.state, "sessao", None)
    comum = {
        "sessao": sessao,
        "usuario_nome": nome_de_exibicao(sessao.email) if sessao else "",
        "csrf_token": sessao.csrf_token if sessao else "",
        "tema": tema_do_cookie(request.cookies.get("tema")),
        "caminho_atual": request.url.path,
    }
    comum["avisos"] = _consumir_avisos(sessao, nome)
    comum.update(contexto or {})
    return templates.TemplateResponse(request, nome, comum, status_code=status)
