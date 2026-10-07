"""Manutenção: alertas, histórico e catálogo (parte 1, somente leitura)."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request

from src.web import dados_manutencao
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _inteiro(valor, padrao=1):
    try:
        return int(valor) if valor is not None else padrao
    except ValueError:
        return padrao


def _valor_valido(valor, opcoes, padrao="todas"):
    return valor if valor in dict(opcoes) else padrao


def _url(aba, situacao="todas", tipo="todas", busca="", pagina=1, parcial=False):
    parametros = {}
    if aba == "alertas" and situacao != "todas":
        parametros["situacao"] = situacao
    if aba == "historico":
        if tipo != "todas":
            parametros["tipo"] = tipo
        if busca:
            parametros["q"] = busca
        if pagina > 1:
            parametros["pagina"] = pagina
    base = f"/manutencao/abas/{aba}" if parcial else "/manutencao"
    if not parcial and aba != "alertas":
        parametros = {"aba": aba, **parametros}
    return base + (f"?{urlencode(parametros)}" if parametros else "")


def _contexto(aba, situacao, tipo, busca, pagina):
    d = dados_manutencao.carregar(aba, situacao, tipo, busca, pagina)
    contexto = {
        "titulo": "Manutenção", "aba": aba, "situacao": situacao, "tipo": tipo,
        "busca": busca, "d": d, "status_rotulo": dados_manutencao.STATUS_ROTULO,
        "abas_da_lista": [
            (chave, rotulo, f"/manutencao/abas/{chave}", _url(chave))
            for chave, rotulo in dados_manutencao.ABAS
        ],
    }
    if aba == "alertas":
        contexto["chips"] = [
            (chave, rotulo, d["alertas"]["contagem"][chave], _url(aba, situacao=chave), _url(aba, situacao=chave, parcial=True))
            for chave, rotulo in dados_manutencao.SITUACOES_ALERTA
        ]
    elif aba == "historico":
        p = d["historico"]["pagina"]
        contexto.update({
            "chips": [
                (chave, rotulo, d["historico"]["contagem"][chave], _url(aba, tipo=chave, busca=busca), _url(aba, tipo=chave, busca=busca, parcial=True))
                for chave, rotulo in dados_manutencao.TIPOS_MANUTENCAO
            ],
            "url_anterior": _url(aba, tipo=tipo, busca=busca, pagina=p.pagina - 1) if p.tem_anterior else None,
            "url_proxima": _url(aba, tipo=tipo, busca=busca, pagina=p.pagina + 1) if p.tem_proxima else None,
            "parcial_anterior": _url(aba, tipo=tipo, busca=busca, pagina=p.pagina - 1, parcial=True) if p.tem_anterior else None,
            "parcial_proxima": _url(aba, tipo=tipo, busca=busca, pagina=p.pagina + 1, parcial=True) if p.tem_proxima else None,
        })
    return contexto


def _parametros(aba, situacao, tipo, q, pagina):
    return (
        dados_manutencao.aba_valida(aba),
        _valor_valido(situacao, dados_manutencao.SITUACOES_ALERTA),
        _valor_valido(tipo, dados_manutencao.TIPOS_MANUTENCAO),
        (q or "").strip()[:80],
        _inteiro(pagina),
    )


def _so_painel(request):
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "painel-aba"
        and not request.headers.get("HX-History-Restore-Request")
    )


@router.get("/manutencao")
def lista(request: Request, aba: str | None = None, situacao: str | None = None, tipo: str | None = None,
          q: str | None = None, pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    modelo = "manutencao/_resposta_aba.html" if _so_painel(request) else "manutencao/lista.html"
    return renderizar(request, modelo, _contexto(*_parametros(aba, situacao, tipo, q, pagina)))


@router.get("/manutencao/abas/{aba}")
def painel(request: Request, aba: str, situacao: str | None = None, tipo: str | None = None,
           q: str | None = None, pagina: str | None = None, _: Sessao = Depends(exigir_dono)):
    if aba not in dict(dados_manutencao.ABAS):
        raise HTTPException(status_code=404)
    return renderizar(request, "manutencao/_resposta_aba.html", _contexto(*_parametros(aba, situacao, tipo, q, pagina)))
