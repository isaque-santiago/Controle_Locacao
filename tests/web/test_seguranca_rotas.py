"""Varredura de todas as rotas: sessão/papel obrigatórios e CSRF em toda mutação (revisão de segurança, Fase 4)."""

from fastapi.routing import APIRoute

from src.web.app import criar_app

# Rotas públicas de propósito: login, saúde (healthcheck) e a página de componentes (só em desenvolvimento).
PUBLICAS = {("GET", "/login"), ("POST", "/login"), ("GET", "/saude"), ("HEAD", "/saude")}
PROTEGIDAS_POR_SESSAO = {"exigir_dono", "exigir_locatario", "exigir_sessao"}
CSRF = {"validar_csrf", "validar_csrf_login"}


def _dependencias(dependente) -> set[str]:
    nomes = set()
    for sub in dependente.dependencies:
        nomes.add(sub.call.__name__)
        nomes |= _dependencias(sub)
    return nomes


def _rotas(rotas):
    for rota in rotas:
        if isinstance(rota, APIRoute):
            yield rota
        elif hasattr(rota, "original_router"):  # include_router (FastAPI novo)
            yield from _rotas(rota.original_router.routes)
        elif hasattr(rota, "routes"):
            yield from _rotas(rota.routes)


def _todas():
    app = criar_app(desenvolvimento=False)
    return list(_rotas(app.routes))


def test_a_varredura_enxerga_as_rotas():
    assert len(_todas()) > 50


def test_toda_rota_exige_sessao_ou_e_publica_de_proposito():
    sem_protecao = [
        (m, r.path)
        for r in _todas()
        for m in sorted(r.methods)
        if (m, r.path) not in PUBLICAS and not (PROTEGIDAS_POR_SESSAO & _dependencias(r.dependant))
    ]
    assert not sem_protecao, sem_protecao


def test_toda_mutacao_exige_csrf():
    sem_csrf = [
        (m, r.path)
        for r in _todas()
        for m in sorted(r.methods)
        if m in {"POST", "PUT", "PATCH", "DELETE"} and not (CSRF & _dependencias(r.dependant))
    ]
    assert not sem_csrf, sem_csrf


def test_nenhuma_mutacao_aceita_get():
    """Gravar por GET escaparia do CSRF: nenhuma rota GET pode ser de escrita (exportar/baixar só leem)."""
    perigosas = [
        r.path
        for r in _todas()
        if "GET" in r.methods and any(p in r.path for p in ("/excluir", "/apagar", "/remover", "/encerrar/confirmar"))
    ]
    assert not perigosas, perigosas


def test_rotas_do_dono_recusam_o_locatario_e_as_do_locatario_recusam_o_dono():
    dono, locatario = [], []
    for r in _todas():
        nomes = _dependencias(r.dependant)
        if "exigir_dono" in nomes:
            dono.append(r.path)
        if "exigir_locatario" in nomes:
            locatario.append(r.path)
    assert dono and locatario and not (set(dono) & set(locatario))
    assert all(not p.startswith("/portal") for p in dono)
