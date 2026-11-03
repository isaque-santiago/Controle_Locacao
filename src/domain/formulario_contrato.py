"""Leitura e validação do assistente de novo contrato (condições e vistoria de entrega).

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

import re
from datetime import date, timedelta
from decimal import Decimal

from src.domain.contratos_lista import PERIODOS_ROTULO
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _sem_milhar, _texto
from src.domain.vistorias import CHECKLIST_PADRAO, ESTADOS_ITEM, NIVEIS_COMBUSTIVEL, rotulo_item

PERIODOS = tuple(PERIODOS_ROTULO)
PRAZO_PADRAO_DIAS = 30  # sugestão de fim previsto quando o dono desmarca "prazo indeterminado"
PREFIXO_ITEM = "item_"
TIPOS = {"locacao": "Locação", "promessa_compra": "Promessa de compra"}


def condicoes_iniciais(hoje: date, valor_sugerido) -> dict:
    """Texto inicial dos campos da etapa Condições (contrato novo, sem rascunho)."""
    return {
        "data_inicio": hoje.isoformat(),
        "indeterminado": True,
        "data_fim_prevista": (hoje + timedelta(days=PRAZO_PADRAO_DIAS)).isoformat(),
        "periodicidade": "semanal",
        "valor_periodo": texto_moeda(valor_sugerido) if valor_sugerido else "",
        "caucao_valor": texto_moeda(0),
        "tipo_contrato": "locacao",
        "valor_entrada": texto_moeda(0),
        "numero_parcelas": "",
        "parcelas_pagas_inicial": "0",
        "dia_cobranca": "",
        "primeira_cobranca": "",
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
        "tipo_contrato": _texto(entrada, "tipo_contrato") or "locacao",
        "valor_entrada": _texto(entrada, "valor_entrada"),
        "numero_parcelas": _texto(entrada, "numero_parcelas"),
        "parcelas_pagas_inicial": _texto(entrada, "parcelas_pagas_inicial"),
        "dia_cobranca": _texto(entrada, "dia_cobranca"),
        "primeira_cobranca": _texto(entrada, "primeira_cobranca"),
    }


def ler_condicoes(entrada: dict) -> dict:
    """Condições do contrato prontas para `contratos.criar_com_vistoria` (dinheiro como texto decimal)."""
    erros: dict[str, str] = {}
    inicio = _coletar(erros, "data_inicio", _data_iso, _texto(entrada, "data_inicio"), "Data de início", True)
    tipo = _texto(entrada, "tipo_contrato") or "locacao"
    if tipo not in TIPOS:
        erros["tipo_contrato"] = "Tipo do contrato: escolha uma das opções."
    promessa = tipo == "promessa_compra"
    indeterminado = bool(entrada.get("indeterminado"))
    fim = None
    if not indeterminado and not promessa:
        fim = _coletar(erros, "data_fim_prevista", _data_iso, _texto(entrada, "data_fim_prevista"), "Fim previsto", True)
        if inicio and fim and fim < inicio:
            erros["data_fim_prevista"] = "Fim previsto: escolha uma data igual ou posterior ao início."
    periodicidade = _texto(entrada, "periodicidade")
    if periodicidade not in PERIODOS:
        erros["periodicidade"] = "Periodicidade: escolha uma das opções."
    valor = _coletar(erros, "valor_periodo", decimal_campo, entrada.get("valor_periodo"), "Valor do período", positivo=True)
    caucao = _coletar(erros, "caucao_valor", decimal_campo, entrada.get("caucao_valor"), "Caução")
    promessa_dados = _ler_promessa(entrada, erros, periodicidade) if promessa else {}
    if erros:
        raise ErroDeCampos(erros)
    return {
        "data_inicio": inicio,
        "data_fim_prevista": fim,
        "periodicidade": periodicidade,
        "valor_periodo": str(valor),
        "caucao_valor": str(caucao),
        **promessa_dados,
    }


def _ler_promessa(entrada: dict, erros: dict, periodicidade: str) -> dict:
    """Campos da promessa de compra (mesmas regras da RPC `rpc_criar_contrato`). Só entram no resultado
    quando o contrato é promessa; a locação comum segue com o payload de sempre."""
    entrada_valor = _coletar(erros, "valor_entrada", decimal_campo, entrada.get("valor_entrada") or "0", "Entrada")
    parcelas = _coletar(erros, "numero_parcelas", inteiro_campo, entrada.get("numero_parcelas"), "Número de parcelas", 1, 600)
    pagas = _coletar(erros, "parcelas_pagas_inicial", inteiro_campo, entrada.get("parcelas_pagas_inicial") or "0", "Parcelas já pagas", 0, 600)
    if parcelas is not None and pagas is not None and pagas > parcelas:
        erros["parcelas_pagas_inicial"] = "Parcelas já pagas: não pode superar o número de parcelas."
    dia = None
    if _texto(entrada, "dia_cobranca"):
        maximo = 7 if periodicidade == "semanal" else 31
        ajuda = "1 = domingo até 7 = sábado" if periodicidade == "semanal" else "dia do mês"
        dia = _coletar(erros, "dia_cobranca", inteiro_campo, entrada.get("dia_cobranca"), f"Dia da cobrança ({ajuda})", 1, maximo)
    primeira = _coletar(erros, "primeira_cobranca", _data_iso, _texto(entrada, "primeira_cobranca"), "Primeira cobrança", False)
    dados = {
        "tipo_contrato": "promessa_compra",
        "numero_parcelas": parcelas,
        "valor_entrada": str(entrada_valor) if entrada_valor is not None else None,
        "parcelas_pagas_inicial": pagas,
    }
    if dia is not None:
        dados["dia_cobranca"] = dia
    if primeira:
        dados["primeira_cobranca"] = primeira
    return dados


def valor_total_promessa(condicoes: dict) -> Decimal | None:
    """Entrada + parcelas x valor do período, para a tela; None quando o contrato é locação comum."""
    if condicoes.get("tipo_contrato") != "promessa_compra":
        return None
    return Decimal(condicoes["valor_entrada"]) + condicoes["numero_parcelas"] * Decimal(condicoes["valor_periodo"])


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


def _juntar(erros: dict, funcao, *args):
    """Roda uma leitura que levanta `ErroDeCampos` e acumula os erros dela em `erros`."""
    try:
        return funcao(*args)
    except ErroDeCampos as erro:
        erros.update(erro.erros)
    return None


def condicoes_do_encerramento(hoje: date, data_inicio: str) -> dict:
    """Texto inicial dos campos do diálogo de encerramento (a data não pode ser anterior ao início)."""
    inicio = date.fromisoformat(str(data_inicio)[:10])
    return {"data_encerramento": max(hoje, inicio).isoformat(), "valor_danos": texto_moeda(0), "descricao_danos": "", "confirmar": False}


def texto_do_encerramento(entrada: dict) -> dict:
    return {
        "data_encerramento": _texto(entrada, "data_encerramento"),
        "valor_danos": _texto(entrada, "valor_danos"),
        "descricao_danos": _texto(entrada, "descricao_danos"),
        "confirmar": bool(entrada.get("confirmar")),
    }


def ler_encerramento(entrada: dict, data_inicio: str, km_minimo: int) -> dict:
    """Encerramento pronto para `contratos.encerrar_com_vistoria`: data, vistoria de devolução, danos e
    confirmação. Os danos são descontados da caução e exigem descrição."""
    erros: dict[str, str] = {}
    inicio = date.fromisoformat(str(data_inicio)[:10])
    data = _coletar(erros, "data_encerramento", _data_iso, _texto(entrada, "data_encerramento"), "Data de encerramento", True)
    if data and date.fromisoformat(data) < inicio:
        erros["data_encerramento"] = "Data de encerramento: escolha uma data igual ou posterior ao início do contrato."
    danos = _coletar(erros, "valor_danos", decimal_campo, entrada.get("valor_danos"), "Danos a descontar da caução")
    descricao = _texto(entrada, "descricao_danos")
    if danos and danos > 0 and not descricao:
        erros["descricao_danos"] = "Descrição dos danos: informe o que foi danificado."
    vistoria = _juntar(erros, ler_vistoria, entrada, km_minimo)
    if not entrada.get("confirmar"):
        erros["confirmar"] = "Marque a confirmação para encerrar o contrato."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "data": date.fromisoformat(data),
        "vistoria": vistoria,
        "valor_danos": Decimal(danos),
        "descricao_danos": descricao or None,
    }
