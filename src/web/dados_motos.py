"""Dados das telas de Motos: reúne os serviços e as regras de src/domain num dicionário.

Fronteira entre a rota e a camada de dados; os testes das rotas trocam estas funções por
dados fictícios."""

from collections import defaultdict

from src.domain import motos_lista
from src.domain.paginacao import calcular_pagina
from src.services import alertas, clientes, contratos, motos


def _locatarios_por_moto() -> dict[str, str]:
    """Nome do cliente do contrato ativo de cada moto."""
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    return {
        c["moto_id"]: nomes.get(c["cliente_id"], "—")
        for c in contratos.listar()
        if c["status"] == "ativo"
    }


def carregar_lista(situacao: str, busca: str, pagina: int, por_pagina: int) -> dict:
    registros = motos.listar()
    locatarios = _locatarios_por_moto()
    filtradas = motos_lista.filtrar_motos(registros, situacao, busca, locatarios)
    recorte = calcular_pagina(len(filtradas), pagina, por_pagina)

    pagina_atual = filtradas[recorte.inicio : recorte.fim]
    ids_da_pagina = {m["id"] for m in pagina_atual}
    plano_por_moto = defaultdict(list)
    for linha in alertas.listar_manutencao():
        if linha["moto_id"] in ids_da_pagina:
            plano_por_moto[linha["moto_id"]].append(linha)

    itens = [
        {
            "moto": m,
            "locatario": locatarios.get(m["id"]),
            "proxima_manutencao": motos_lista.proxima_manutencao(plano_por_moto[m["id"]]),
        }
        for m in pagina_atual
    ]
    return {
        "itens": itens,
        "pagina": recorte,
        "contagem": motos_lista.contagem_por_status(registros),
        "total_cadastradas": len(registros),
    }
