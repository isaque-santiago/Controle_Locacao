"""Leitura, validação e prévia do formulário de registro de manutenção."""

from datetime import date
from decimal import Decimal

from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto

TIPOS = ("preventiva", "corretiva")
STATUS = ("concluida", "aberta")


def valores_iniciais(hoje: date, moto: dict | None) -> dict:
    return {
        "moto_id": moto["id"] if moto else "", "tipo": "preventiva", "status": "concluida",
        "data_entrada": hoje.isoformat(), "data_saida": hoje.isoformat(),
        "km": str(moto.get("km_atual", 0) if moto else 0), "oficina": "", "descricao": "",
        "custo_mao_obra": texto_moeda(0), "cobrar_do_cliente": False,
        "extras_ids": "", "chave_operacao": "",
    }


def texto_da_entrada(entrada: dict) -> dict:
    return {**entrada, "cobrar_do_cliente": bool(entrada.get("cobrar_do_cliente"))}


def ids_extras(valores: dict) -> list[int]:
    ids = []
    for texto in str(valores.get("extras_ids") or "").split(","):
        try:
            numero = int(texto)
            if numero >= 0 and numero not in ids:
                ids.append(numero)
        except ValueError:
            pass
    return ids[:20]


def alterar_linhas(valores: dict, acao: str | None) -> dict:
    ids = ids_extras(valores)
    if acao == "adicionar" and len(ids) < 20:
        ids.append(max(ids, default=-1) + 1)
    elif acao and acao.startswith("remover:"):
        try:
            ids.remove(int(acao.partition(":")[2]))
        except (ValueError, TypeError):
            pass
    return {**valores, "extras_ids": ",".join(map(str, ids))}


def _decimal_tolerante(valor, positivo=False):
    try:
        return decimal_campo(valor, "Campo", positivo=positivo)
    except ValueError:
        return Decimal("0")


def previa(valores: dict, catalogo: list[dict]) -> dict:
    pecas = Decimal("0")
    selecionados = []
    for item in catalogo:
        chave = f"item_{item['id']}"
        if valores.get(chave):
            quantidade = _decimal_tolerante(valores.get(f"qtd_{item['id']}", "1"), positivo=True)
            valor = _decimal_tolerante(valores.get(f"valor_{item['id']}", "0"))
            subtotal = quantidade * valor
            pecas += subtotal
            selecionados.append({"item": item, "quantidade": quantidade, "valor": valor, "subtotal": subtotal})
    for numero in ids_extras(valores):
        if _texto(valores, f"extra_descricao_{numero}"):
            pecas += _decimal_tolerante(valores.get(f"extra_qtd_{numero}", "1"), positivo=True) * _decimal_tolerante(
                valores.get(f"extra_valor_{numero}", "0")
            )
    mao_obra = _decimal_tolerante(valores.get("custo_mao_obra", "0"))
    return {"pecas": pecas, "mao_obra": mao_obra, "total": pecas + mao_obra, "selecionados": selecionados}


def ler(valores: dict, moto: dict, catalogo: list[dict]) -> dict:
    erros = {}
    tipo = _texto(valores, "tipo")
    status = _texto(valores, "status")
    if tipo not in TIPOS:
        erros["tipo"] = "Tipo: escolha Preventiva ou Corretiva."
    if status not in STATUS:
        erros["status"] = "Status: escolha Concluída ou Aberta."
    entrada = _coletar(erros, "data_entrada", _data_iso, _texto(valores, "data_entrada"), "Data de entrada", True)
    saida = None
    if status == "concluida":
        saida = _coletar(erros, "data_saida", _data_iso, _texto(valores, "data_saida"), "Data de saída", True)
        if entrada and saida and saida < entrada:
            erros["data_saida"] = "Data de saída: escolha uma data igual ou posterior à entrada."
    km = _coletar(erros, "km", inteiro_campo, _texto(valores, "km"), "Quilometragem", int(moto["km_atual"]))
    descricao = _texto(valores, "descricao")
    if not descricao:
        erros["descricao"] = "Descrição: informe o serviço realizado."
    mao_obra = _coletar(erros, "custo_mao_obra", decimal_campo, valores.get("custo_mao_obra"), "Custo de mão de obra")
    itens = []
    for item in catalogo:
        if not valores.get(f"item_{item['id']}"):
            continue
        qtd = _coletar(erros, f"qtd_{item['id']}", decimal_campo, valores.get(f"qtd_{item['id']}", "1"), f"Quantidade de {item['nome']}", positivo=True)
        valor = _coletar(erros, f"valor_{item['id']}", decimal_campo, valores.get(f"valor_{item['id']}", "0"), f"Valor unitário de {item['nome']}")
        if qtd is not None and valor is not None:
            itens.append({"item_id": item["id"], "descricao": item["nome"], "quantidade": qtd, "valor_unitario": valor})
    for numero in ids_extras(valores):
        descricao_extra = _texto(valores, f"extra_descricao_{numero}")
        qtd_bruta = valores.get(f"extra_qtd_{numero}", "1")
        valor_bruto = valores.get(f"extra_valor_{numero}", "0")
        if not descricao_extra and str(qtd_bruta).strip() in ("", "1") and str(valor_bruto).strip() in ("", "0", "0,00"):
            continue
        if not descricao_extra:
            erros[f"extra_descricao_{numero}"] = "Descrição: informe a peça ou o serviço."
        qtd = _coletar(erros, f"extra_qtd_{numero}", decimal_campo, qtd_bruta, f"Quantidade de {descricao_extra or 'item adicional'}", positivo=True)
        valor = _coletar(erros, f"extra_valor_{numero}", decimal_campo, valor_bruto, f"Valor unitário de {descricao_extra or 'item adicional'}")
        if descricao_extra and qtd is not None and valor is not None:
            itens.append({"descricao": descricao_extra, "quantidade": qtd, "valor_unitario": valor})
    if erros:
        raise ErroDeCampos(erros)
    return {
        "moto_id": moto["id"], "tipo": tipo, "data_entrada": date.fromisoformat(entrada), "km": km,
        "descricao": descricao, "status": status, "data_saida": date.fromisoformat(saida) if saida else None,
        "oficina": _texto(valores, "oficina") or None, "custo_mao_obra": mao_obra,
        "cobrar_do_cliente": bool(valores.get("cobrar_do_cliente")), "itens": itens,
    }
