"""Planilha de conferência do histórico dos chats (gerada pelo app, só para o dono; seção 24.9 do plano).

Em vez de cada chat montar a sua planilha, o sistema monta uma só, igual para os dois: todos os registros do rascunho, com o id de cada
um, a situação da comparação, o trecho do chat e uma coluna «Decisão» para o dono marcar. O id permite ligar a decisão ao registro
quando a carga for gerada. Funções puras: quem monta o arquivo é `src/services/historico_chat.py`."""

from src.domain.formatadores import formatar_data
from src.domain.historico_chat import lacunas, periodos_cobertos

NOME_DA_FONTE = {"chat_financeiro": "Acompanhamento Financeiro", "chat_contratos": "Contratos Locadora"}
ROTULO_DA_SITUACAO = {"diverge": "Diverge", "nova": "Nova", "sem_comparacao": "Sem comparação", "ja_existe": "Já existe",
                      "descartada": "Descartada", "aplicada": "Aplicada"}
ORDEM_DA_SITUACAO = ("diverge", "nova", "sem_comparacao", "ja_existe", "descartada", "aplicada")
ROTULO_DO_TIPO = {"pagamento": "Pagamento", "despesa": "Despesa", "multa": "Multa", "divida": "Dívida", "movimento_socio": "Movimento de sócio",
                  "cliente": "Cliente", "veiculo": "Veículo", "contrato": "Contrato", "outro": "Outro"}
DECISOES = ("Aplicar", "Ignorar", "Corrigir", "Perguntar ao dono")
COLUNAS = ("ID", "Chat", "Tipo", "Data", "Situação", "Resumo", "No sistema / motivo", "Trecho do chat", "Marcas", "Lote", "Decisão", "Observação do dono")
COLUNA_DA_DECISAO = COLUNAS.index("Decisão") + 1  # 1 = A


def _posicao(situacao: str) -> int:
    return ORDEM_DA_SITUACAO.index(situacao) if situacao in ORDEM_DA_SITUACAO else len(ORDEM_DA_SITUACAO)


def ordenar(linhas: list[dict]) -> list[dict]:
    """Primeiro o chat, depois o que precisa de decisão (diverge, nova, sem comparação, já existe) e, dentro disso, a data."""
    return sorted(linhas, key=lambda x: (x["fonte"], _posicao(x["situacao"]), str(x.get("data") or "9999"), str(x.get("entregue_em") or ""), str(x["id"])))


def marcas(linha: dict) -> str:
    """O que o chat avisou sobre o dado: data estimada, valor ou campo inferido, o que faltou."""
    partes = []
    if linha.get("data_estimada"):
        partes.append("data estimada")
    if linha.get("inferido"):
        partes.append("inferido" if linha["inferido"] == "true" else f"inferido: {linha['inferido']}")
    if linha.get("faltando"):
        partes.append(f"falta: {linha['faltando']}")
    return "; ".join(partes)


def linha_da_planilha(linha: dict) -> tuple:
    """Os valores da linha, na ordem de COLUNAS (as duas últimas, de decisão, ficam vazias para o dono)."""
    return (
        linha["id"], NOME_DA_FONTE.get(linha["fonte"], linha["fonte"]), ROTULO_DO_TIPO.get(linha["tipo"], linha["tipo"]),
        linha.get("data"), ROTULO_DA_SITUACAO.get(linha["situacao"], linha["situacao"]), linha["resumo"], linha.get("detalhe") or "",
        linha.get("trecho") or "", marcas(linha), linha.get("lote") or "", None, None,
    )


def resumo_por_fonte(lotes: list[dict], linhas: list[dict]) -> list[dict]:
    """Por chat: lotes, períodos entregues, buracos entre eles e a contagem por tipo e situação."""
    saida = []
    for fonte in sorted({x["fonte"] for x in lotes} | {x["fonte"] for x in linhas}):
        meus = [x for x in lotes if x["fonte"] == fonte]
        periodos = [(x["periodo_inicio"], x["periodo_fim"]) for x in meus]
        por_tipo: dict[str, dict[str, int]] = {}
        for x in linhas:
            if x["fonte"] == fonte:
                por_tipo.setdefault(x["tipo"], {}).setdefault(x["situacao"], 0)
                por_tipo[x["tipo"]][x["situacao"]] += 1
        saida.append({
            "fonte": fonte, "nome": NOME_DA_FONTE.get(fonte, fonte), "lotes": len(meus), "registros": sum(x["registros_recebidos"] for x in meus),
            "periodos": periodos_cobertos(periodos), "buracos": lacunas(periodos), "por_tipo": por_tipo,
        })
    return saida


def texto_do_periodo(inicio, fim) -> str:
    return f"{formatar_data(inicio)} a {formatar_data(fim)}"
