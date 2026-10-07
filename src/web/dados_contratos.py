"""Dados das telas de Contratos: reúne os serviços e as regras de src/domain num dicionário.

Fronteira de leitura entre a rota e a camada de dados; os testes das rotas trocam estes serviços
por dados fictícios."""

from datetime import date
from decimal import Decimal

from src.domain import clientes_lista, contratos_lista
from src.domain.valores import hoje_br
from src.services import clientes, cobrancas, contratos, manutencao, motos, vistorias

_TIPOS_VISTORIA = (("entrega", "Entrega"), ("devolucao", "Devolução"))


def carregar_lista(status, busca, pagina, por_pagina):
    registros = contratos.listar()
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    frota = {m["id"]: m for m in motos.listar()}
    itens = [
        {"contrato": c, "cliente_nome": nomes.get(c["cliente_id"], "—"), "moto": frota.get(c["moto_id"]),
         "placa": (frota.get(c["moto_id"]) or {}).get("placa", "")}
        for c in registros
    ]
    pagina_itens, recorte, contagem = contratos_lista.montar_pagina(itens, status, busca, pagina, por_pagina)
    return {"itens": pagina_itens, "pagina": recorte, "contagem": contagem, "total_cadastrados": len(registros),
            "total_ativos": contagem["ativo"]}


def obter_contrato(contrato_id):
    """O contrato com cliente e moto, ou None se algum dos três não existir."""
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if contrato is None:
        return None
    cliente = clientes.obter(contrato["cliente_id"])
    moto = motos.obter(contrato["moto_id"])
    if cliente is None or moto is None:
        return None
    return {"contrato": contrato, "cliente": cliente, "moto": moto}


def _avarias(checklist):
    nomes = [nome.replace("_", " ") for nome, estado in (checklist or {}).items() if estado == "avaria"]
    return ", ".join(nomes) or "Nenhuma"


def carregar_ficha(contrato, aba):
    """Cabeçalho de dados (sempre) e o conteúdo da aba pedida."""
    parcelas = sorted(cobrancas.listar_por_contrato(contrato["id"]), key=lambda c: c["vencimento"])
    proximas = [c["vencimento"] for c in parcelas if c["situacao"] == "aberta" and c["tipo"] == "locacao"]
    dados = {"proxima_cobranca": proximas[0] if proximas else None, "prazo": contratos_lista.prazo_texto(contrato.get("data_fim_prevista")),
             "cobrancas": [], "vistorias": [], "manutencoes": []}
    if aba == "cobrancas":
        historicos = cobrancas.historicos_pagamentos([c["id"] for c in parcelas])
        dados["cobrancas"] = [
            {**c, "pago_em": (historicos.get(c["id"]) or [{}])[-1].get("data_pagamento")} for c in parcelas
        ]
    elif aba == "vistorias":
        por_tipo = {v["tipo"]: v for v in vistorias.listar_por_contrato(contrato["id"])}
        dados["vistorias"] = [
            {"tipo": tipo, "titulo": titulo, "registro": por_tipo.get(tipo),
             "avarias": _avarias((por_tipo.get(tipo) or {}).get("checklist"))}
            for tipo, titulo in _TIPOS_VISTORIA
        ]
    elif aba == "manutencoes":
        limite = str(contrato.get("data_encerramento") or hoje_br().isoformat())[:10]
        inicio = str(contrato["data_inicio"])[:10]
        dados["manutencoes"] = sorted(
            (m for m in manutencao.listar_manutencoes(contrato["moto_id"]) if inicio <= str(m["data_entrada"])[:10] <= limite),
            key=lambda m: m["data_entrada"], reverse=True,
        )
    return dados


# ----------------------------------------------------- assistente de novo contrato --

def candidatos_cliente(busca):
    """Clientes que casam com a busca, com a moto que já alugam (informativo) e se podem alugar (status ativo)."""
    ativos = {c["cliente_id"]: c["moto_id"] for c in contratos.listar() if c["status"] == "ativo"}
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    return [
        {"cliente": c, "elegivel": c["status"] == "ativo", "placa_atual": placas.get(ativos.get(c["id"]))}
        for c in clientes_lista.filtrar(clientes.listar(), clientes_lista.TODOS, busca)
    ]


def candidatas_moto(busca):
    disponiveis = [m for m in motos.listar() if m["status"] == "disponivel"]
    return contratos_lista.filtrar_motos(disponiveis, busca)


def cliente_para_contrato(cliente_id):
    """O cliente, se existir e puder alugar; senão None."""
    cliente = clientes.obter(cliente_id) if cliente_id else None
    return cliente if cliente and cliente["status"] == "ativo" else None


def moto_para_contrato(moto_id):
    """A moto, se existir e estiver disponível; senão None."""
    moto = motos.obter(moto_id) if moto_id else None
    return moto if moto and moto["status"] == "disponivel" else None


def previa_agenda(condicoes):
    """Parcelas previstas (a mesma lógica da RPC). Prazo indeterminado mostra só a janela inicial."""
    fim = condicoes.get("data_fim_prevista")
    return contratos.previa_agenda(
        date.fromisoformat(condicoes["data_inicio"]), condicoes["periodicidade"],
        Decimal(condicoes["valor_periodo"]), date.fromisoformat(fim) if fim else None,
    )
