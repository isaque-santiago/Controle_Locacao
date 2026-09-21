"""Checklist padrão de vistoria e comparação entrega x devolução."""

CHECKLIST_PADRAO = (
    "farol_dianteiro",
    "farol_traseiro",
    "pisca_alerta",
    "freio_dianteiro",
    "freio_traseiro",
    "pneu_dianteiro",
    "pneu_traseiro",
    "retrovisores",
    "buzina",
    "escapamento",
    "carenagem",
    "banco",
    "capacete",
    "chave_reserva",
    "documentos_do_veiculo",
)


def checklist_inicial() -> dict:
    """Checklist padrão com todos os itens 'ok', para pré-preencher a tela
    de vistoria (o dono ajusta o que estiver diferente)."""
    return {item: "ok" for item in CHECKLIST_PADRAO}


def comparar_checklists(checklist_entrega: dict, checklist_devolucao: dict) -> dict:
    """Itens cujo valor mudou entre a vistoria de entrega e a de devolução
    (inclui itens presentes em só um dos dois lados)."""
    checklist_entrega = checklist_entrega or {}
    checklist_devolucao = checklist_devolucao or {}
    todas_as_chaves = set(checklist_entrega) | set(checklist_devolucao)

    diferencas = {}
    for chave in todas_as_chaves:
        valor_entrega = checklist_entrega.get(chave)
        valor_devolucao = checklist_devolucao.get(chave)
        if valor_entrega != valor_devolucao:
            diferencas[chave] = {"entrega": valor_entrega, "devolucao": valor_devolucao}
    return diferencas
