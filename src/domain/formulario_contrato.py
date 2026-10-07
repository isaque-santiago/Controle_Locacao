"""Leitura e validação do assistente de novo contrato (condições e vistoria de entrega).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

import re
from datetime import date, timedelta

from src.domain.contratos_lista import PERIODOS_ROTULO
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _sem_milhar, _texto
from src.domain.vistorias import CHECKLIST_PADRAO, ESTADOS_ITEM, NIVEIS_COMBUSTIVEL, rotulo_item

PERIODOS = tuple(PERIODOS_ROTULO)
PRAZO_PADRAO_DIAS = 30  # sugestão de fim previsto quando o dono desmarca "prazo indeterminado"
PREFIXO_ITEM = "item_"


def condicoes_iniciais(hoje: date, valor_sugerido) -> dict:
    """Texto inicial dos campos da etapa Condições (contrato novo, sem rascunho)."""
    return {
        "data_inicio": hoje.isoformat(),
        "indeterminado": True,
        "data_fim_prevista": (hoje + timedelta(days=PRAZO_PADRAO_DIAS)).isoformat(),
        "periodicidade": "semanal",
        "valor_periodo": texto_moeda(valor_sugerido) if valor_sugerido else "",
        "caucao_valor": texto_moeda(0),
    }


def texto_das_condicoes(entrada: dict) -> dict:
    """O que o navegador enviou, guardado como rascunho (mesmo inválido) para voltar e revisar."""
    return {
        "data_inicio": _texto(entrada, "data_inicio"),
        "indeterminado": bool(entrada.get("indeterminado")),
        "data_fim_prevista": _texto(entrada, "data_fim_prevista"),
        "periodicidade": _texto(entrada, "periodicidade"),
        "valor_periodo": _texto(entrada, "valor_periodo"),
        "caucao_valor": _texto(entrada, "caucao_valor"),
    }


def ler_condicoes(entrada: dict) -> dict:
    """Condições do contrato prontas para `contratos.criar_com_vistoria` (dinheiro como texto decimal)."""
    erros: dict[str, str] = {}
    inicio = _coletar(erros, "data_inicio", _data_iso, _texto(entrada, "data_inicio"), "Data de início", True)
    indeterminado = bool(entrada.get("indeterminado"))
    fim = None
    if not indeterminado:
        fim = _coletar(erros, "data_fim_prevista", _data_iso, _texto(entrada, "data_fim_prevista"), "Fim previsto", True)
        if inicio and fim and fim < inicio:
            erros["data_fim_prevista"] = "Fim previsto: escolha uma data igual ou posterior ao início."
    periodicidade = _texto(entrada, "periodicidade")
    if periodicidade not in PERIODOS:
        erros["periodicidade"] = "Periodicidade: escolha uma das opções."
    valor = _coletar(erros, "valor_periodo", decimal_campo, entrada.get("valor_periodo"), "Valor do período", positivo=True)
    caucao = _coletar(erros, "caucao_valor", decimal_campo, entrada.get("caucao_valor"), "Caução")
    if erros:
        raise ErroDeCampos(erros)
    return {
        "data_inicio": inicio,
        "data_fim_prevista": fim,
        "periodicidade": periodicidade,
        "valor_periodo": str(valor),
        "caucao_valor": str(caucao),
    }


def vistoria_inicial(km_atual: int) -> dict:
    """Texto inicial da vistoria de entrega: km da moto, combustível vazio e checklist todo 'ok'."""
    return {
        "km": str(km_atual), "nivel_combustivel": NIVEIS_COMBUSTIVEL[0], "adicionais": "", "avarias": "",
        **{PREFIXO_ITEM + item: ESTADOS_ITEM[0] for item in CHECKLIST_PADRAO},
    }


def texto_da_vistoria(entrada: dict) -> dict:
    texto = {chave: _texto(entrada, chave) for chave in ("km", "nivel_combustivel", "avarias")}
    texto["adicionais"] = str(entrada.get("adicionais") or "")
    for item in CHECKLIST_PADRAO:
        texto[PREFIXO_ITEM + item] = _texto(entrada, PREFIXO_ITEM + item)
    return texto


def _itens_adicionais(texto: str) -> dict[str, str]:
    """Uma linha por item, no formato `nome=estado`."""
    itens = {}
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        nome, separador, estado = linha.partition("=")
        if not separador or not nome.strip() or estado.strip() not in ESTADOS_ITEM:
            raise ValueError(
                "Itens adicionais: use nome=estado, com estado ok, avaria, ausente ou nao_aplicavel."
            )
        itens[nome.strip()] = estado.strip()
    return itens


def ler_vistoria(entrada: dict, km_minimo: int) -> dict:
    """Vistoria de entrega pronta para a RPC. O km não pode ser menor que a leitura atual da moto
    e vira o km inicial do contrato."""
    erros: dict[str, str] = {}
    km = _coletar(erros, "km", inteiro_campo, _sem_milhar(_texto(entrada, "km")), "Quilometragem da vistoria", km_minimo)
    combustivel = _texto(entrada, "nivel_combustivel")
    if combustivel not in NIVEIS_COMBUSTIVEL:
        erros["nivel_combustivel"] = "Combustível: escolha um dos níveis."
    checklist = {}
    for item in CHECKLIST_PADRAO:
        estado = _texto(entrada, PREFIXO_ITEM + item)
        if estado not in ESTADOS_ITEM:
            erros[PREFIXO_ITEM + item] = f"{rotulo_item(item)}: escolha o estado do item."
        checklist[item] = estado
    adicionais = _coletar(erros, "adicionais", _itens_adicionais, str(entrada.get("adicionais") or ""))
    if erros:
        raise ErroDeCampos(erros)
    return {
        "km": km,
        "nivel_combustivel": combustivel,
        "checklist": {**checklist, **(adicionais or {})},
        "avarias": _texto(entrada, "avarias"),
    }
