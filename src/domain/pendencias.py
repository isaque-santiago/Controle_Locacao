"""Lançamentos do conector do claude.ai (seção 24 do plano).

Modelo de 24/11/2026: o chat **grava direto** o que está limpo (cadastro de cliente e de veículo; pagamento e despesa sem aviso e
abaixo do teto) e, na dúvida, **não grava** e devolve o motivo para o Claude perguntar ao usuário na conversa. A tabela de pendências
guarda o histórico (e as propostas manuais, que o dono aprova). Estas regras puras normalizam e validam a proposta, calculam os
avisos de divergência e identificam o cliente/veículo citado. O banco repete as mesmas conferências nas RPCs
(`rpc_pendencia_criar`, `rpc_pendencia_aprovar`), que são a palavra final: aqui ficam o que a tela e as ferramentas do conector
usam antes de chegar lá. Dinheiro sempre em Decimal."""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from src.domain.entradas import apenas_digitos, formatar_telefone, normalizar_placa
from src.domain.formatadores import formatar_data, formatar_moeda
from src.domain.validadores import validar_cpf, validar_placa, validar_telefone
from src.domain.valores import decimal_br, hoje_br

TIPOS = ("pagamento", "despesa")
TIPOS_DE_HISTORICO = TIPOS + ("cliente", "veiculo")  # o histórico também registra os cadastros feitos pelo chat
ORIGENS_DO_CONECTOR = ("chat_financeiro", "chat_contratos")
ORIGENS = ORIGENS_DO_CONECTOR + ("comprovante_grupo", "manual")
STATUS = ("pendente", "aprovada", "recusada", "desfeita")
# O chat não propõe «abatimento» (desconto sem dinheiro): isso é decisão do dono.
FORMAS_PAGAMENTO = ("pix", "dinheiro", "cartao", "transferencia", "outro")
CATEGORIAS_DESPESA = ("manutencao", "documentacao", "seguro_rastreador", "multas", "combustivel", "outros")

LIMITE_PAGAMENTO = Decimal("20000.00")
LIMITE_DESPESA = Decimal("50000.00")
# Acima destes valores a ferramenta não grava direto (decisão do dono em 24/11/2026); ficam dentro dos limites absolutos acima.
TETO_PAGAMENTO_DIRETO = Decimal("10000.00")
TETO_DESPESA_DIRETA = Decimal("5000.00")
JANELA_DESFAZER_DIAS = 7  # só dá para desfazer um lançamento automático nesse prazo
LIMITE_PENDENTES_ABERTAS = 200  # trava contra enxurrada de propostas
DIAS_DE_FUTURO_TOLERADOS = 1  # fuso e virada do dia
TAMANHO_OBSERVACAO = 500
TAMANHO_DESCRICAO_VEICULO = 120
TAMANHO_TRECHO = 600
TAMANHO_CHAVE = 120

# Com estes avisos a pendência não pode ser aprovada como está: o dono corrige (editar e aprovar) ou recusa.
AVISOS_BLOQUEANTES = ("cobranca_nao_identificada", "cobranca_paga", "cobranca_cancelada", "valor_acima_do_saldo", "veiculo_nao_identificado")

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_PLACA = re.compile(r"\b([A-Za-z]{3})-?(\d[A-Za-z0-9]\d{2})\b")
_ROTULO_FORMA = {"pix": "Pix", "dinheiro": "dinheiro", "cartao": "cartão", "transferencia": "transferência", "outro": "outro meio"}


# ---------------------------------------------------------------- normalização --

def _simplificar(texto) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _valor(bruto, limite: Decimal, campo: str = "valor") -> Decimal:
    if isinstance(bruto, bool) or bruto is None or str(bruto).strip() == "":
        raise ValueError(f"Informe o {campo}.")
    try:
        numero = decimal_br(Decimal(str(bruto)) if isinstance(bruto, (int, float, Decimal)) else bruto, positivo=True)
    except (ValueError, InvalidOperation):
        raise ValueError(f"O {campo} precisa ser um valor positivo com até duas casas decimais.") from None
    if numero > limite:
        raise ValueError(f"O {campo} passa do limite de {formatar_moeda(limite)} para uma proposta do chat.")
    return numero


def _data(bruto, hoje: date, campo: str = "data") -> date:
    if bruto in (None, ""):
        return hoje
    texto = str(bruto).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            dia = datetime.strptime(texto, formato).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"A {campo} precisa estar no formato dd/mm/aaaa.")
    if dia > hoje + timedelta(days=DIAS_DE_FUTURO_TOLERADOS):
        raise ValueError(f"A {campo} não pode estar no futuro.")
    return dia


def _id(bruto, campo: str) -> str | None:
    if bruto in (None, ""):
        return None
    if not _UUID.match(str(bruto)):
        raise ValueError(f"O identificador de {campo} é inválido.")
    return str(bruto).lower()


def _texto(bruto, limite: int, campo: str) -> str | None:
    texto = re.sub(r"\s+", " ", str(bruto or "")).strip()
    if len(texto) > limite:
        raise ValueError(f"O campo {campo} passa de {limite} caracteres.")
    return texto or None


def normalizar_pagamento(entrada: dict, hoje: date) -> dict:
    """Proposta de pagamento pronta para gravar (textos, datas ISO, dinheiro como '275.00'). Levanta ValueError em português."""
    forma = _simplificar(entrada.get("forma") or "pix")
    if forma not in FORMAS_PAGAMENTO:
        raise ValueError("A forma de pagamento precisa ser: " + ", ".join(FORMAS_PAGAMENTO) + ".")
    multa = entrada.get("multa_juros")
    return {
        "cobranca_id": _id(entrada.get("cobranca_id"), "cobrança"),
        "valor": str(_valor(entrada.get("valor"), LIMITE_PAGAMENTO)),
        "multa_juros": str(_valor(multa, LIMITE_PAGAMENTO, "valor dos encargos") if multa not in (None, "", 0, "0") else Decimal("0.00")),
        "data_pagamento": _data(entrada.get("data_pagamento"), hoje, "data do pagamento").isoformat(),
        "forma": forma,
        "observacoes": _texto(entrada.get("observacoes"), TAMANHO_OBSERVACAO, "observações"),
    }


def normalizar_despesa(entrada: dict, hoje: date) -> dict:
    categoria = _simplificar(entrada.get("categoria") or "outros").replace(" ", "_")
    if categoria not in CATEGORIAS_DESPESA:
        raise ValueError("A categoria precisa ser: " + ", ".join(CATEGORIAS_DESPESA) + ".")
    observacoes = _texto(entrada.get("observacoes") or entrada.get("descricao"), TAMANHO_OBSERVACAO, "descrição")
    if not observacoes:
        raise ValueError("Descreva a despesa.")
    return {
        "moto_id": _id(entrada.get("moto_id"), "veículo"),
        "descricao_veiculo": _texto(entrada.get("descricao_veiculo"), TAMANHO_DESCRICAO_VEICULO, "veículo"),
        "valor": str(_valor(entrada.get("valor"), LIMITE_DESPESA)),
        "data": _data(entrada.get("data"), hoje, "data da despesa").isoformat(),
        "categoria": categoria,
        "repassar_locatario": bool(entrada.get("repassar_locatario")),
        "observacoes": observacoes,
    }


def chave_operacao_padrao(tipo: str, origem: str, dados: dict) -> str:
    """Chave de idempotência quando o chat não manda uma: a mesma proposta (mesmos campos) gera sempre a mesma chave."""
    corpo = json.dumps({"t": tipo, "o": origem, "d": dados}, sort_keys=True, ensure_ascii=False)
    return "auto-" + hashlib.sha256(corpo.encode()).hexdigest()[:40]


# ---------------------------------------------------------------- resumo e avisos --

def resumo(tipo: str, dados: dict, cliente: str | None = None, placa: str | None = None) -> str:
    """Texto curto para a lista de pendências."""
    valor = formatar_moeda(Decimal(dados["valor"]))
    if tipo == "pagamento":
        data = formatar_data(date.fromisoformat(dados["data_pagamento"]))
        quem = f" de {cliente}" if cliente else ""
        onde = f" ({placa})" if placa else ""
        return f"Pagamento{quem}{onde}: {valor} em {data} por {_ROTULO_FORMA.get(dados['forma'], dados['forma'])}"
    data = formatar_data(date.fromisoformat(dados["data"]))
    veiculo = placa or dados.get("descricao_veiculo")
    return f"Despesa{f' ({veiculo})' if veiculo else ''}: {valor} em {data}, {dados['categoria'].replace('_', ' ')}"


def _aviso(codigo: str, texto: str) -> dict:
    return {"codigo": codigo, "texto": texto}


def avisos_pagamento(dados: dict, cobranca: dict | None, iguais: int = 0, hoje: date | None = None) -> list[dict]:
    """Divergências da proposta com a cobrança. `cobranca` = {"status", "saldo"} ou None; `iguais` = pagamentos já gravados na
    mesma cobrança com o mesmo valor e a mesma data."""
    avisos = []
    if cobranca is None:
        return [_aviso("cobranca_nao_identificada", "A cobrança não foi identificada: escolha qual cobrança este pagamento quita.")]
    valor = Decimal(dados["valor"])
    saldo = Decimal(str(cobranca["saldo"]))
    if cobranca["status"] == "paga":
        avisos.append(_aviso("cobranca_paga", "Esta cobrança já está paga."))
    elif cobranca["status"] == "cancelada":
        avisos.append(_aviso("cobranca_cancelada", "Esta cobrança foi cancelada."))
    elif valor > saldo:
        avisos.append(_aviso("valor_acima_do_saldo", f"O valor passa do saldo da cobrança ({formatar_moeda(saldo)})."))
    elif valor < saldo:
        avisos.append(_aviso("valor_abaixo_do_saldo", f"Pagamento parcial: o saldo da cobrança é {formatar_moeda(saldo)}."))
    if iguais:
        avisos.append(_aviso("possivel_duplicada", "Já existe um pagamento igual (mesma cobrança, valor e data)."))
    if hoje and date.fromisoformat(dados["data_pagamento"]) > hoje:
        avisos.append(_aviso("data_no_futuro", "A data do pagamento é amanhã ou depois."))
    return avisos


def avisos_despesa(dados: dict, veiculo: dict | None, iguais: int = 0) -> list[dict]:
    avisos = []
    if dados.get("moto_id") and veiculo is None:
        avisos.append(_aviso("veiculo_nao_identificado", "O veículo informado não foi encontrado."))
    elif not dados.get("moto_id") and not dados.get("descricao_veiculo"):
        avisos.append(_aviso("sem_veiculo", "A despesa não está ligada a nenhum veículo."))
    if iguais:
        avisos.append(_aviso("possivel_duplicada", "Já existe uma despesa igual (mesmo veículo, valor e data)."))
    return avisos


def pode_aprovar(avisos: list[dict]) -> bool:
    return not any(a["codigo"] in AVISOS_BLOQUEANTES for a in avisos)


# ---------------------------------------------------------------- identificar cliente e veículo --

def _partes_da_busca(busca: str) -> tuple[list[str], str, list[str]]:
    texto = str(busca or "")
    placas = [m.group(1).upper() + m.group(2).upper() for m in _PLACA.finditer(texto)]
    sem_placa = _PLACA.sub(" ", texto)
    digitos = re.findall(r"\d[\d.\-*]*\d|\d", sem_placa)
    cpf = max((re.sub(r"\D", "", d) for d in digitos), key=len, default="")
    nome = [t for t in _simplificar(re.sub(r"[\d*.\-]+", " ", sem_placa)).split() if len(t) >= 2]
    return placas, cpf if len(cpf) >= 4 else "", nome


def pontuar_busca(busca: str, candidato: dict) -> int:
    """Pontos que o `candidato` ({"nome", "cpf", "placas"}) ganha pela busca do chat: placa exata 50, CPF parcial (4 dígitos ou
    mais contidos no CPF) 40, e 10 por palavra do nome que começa uma palavra do nome do cliente."""
    placas, cpf, palavras = _partes_da_busca(busca)
    pontos = 0
    if placas and any(p in {str(x).replace("-", "").upper() for x in candidato.get("placas") or []} for p in placas):
        pontos += 50
    if cpf and cpf in re.sub(r"\D", "", str(candidato.get("cpf") or "")):
        pontos += 40
    nomes = _simplificar(candidato.get("nome")).split()
    pontos += 10 * sum(1 for p in palavras if any(n.startswith(p) for n in nomes))
    return pontos


MINIMO_PARA_ESCOLHER = 20
MARGEM_PARA_ESCOLHER = 10


def escolher_unico(busca: str, candidatos: list[dict]) -> tuple[dict | None, str]:
    """O candidato que a busca aponta com segurança, ou (None, motivo). Só escolhe com pontuação mínima e vantagem clara sobre o
    segundo; com dúvida devolve None e o chat pergunta ao dono (ou a pendência vai sem cobrança, com aviso)."""
    pontuados = sorted(((pontuar_busca(busca, c), i, c) for i, c in enumerate(candidatos)), key=lambda x: (-x[0], x[1]))
    if not pontuados or pontuados[0][0] < MINIMO_PARA_ESCOLHER:
        return None, "Nenhum cliente combina com a busca."
    if len(pontuados) > 1 and pontuados[0][0] - pontuados[1][0] < MARGEM_PARA_ESCOLHER:
        return None, "Mais de um cliente combina com a busca: informe o CPF parcial ou a placa."
    return pontuados[0][2], ""


# ---------------------------------------------------------------- gravar direto ou devolver a dúvida --

class Decisao(dict):
    """{"gravar": bool, "motivo": str, "mensagem": str}: o que a ferramenta faz com a proposta."""


def decidir_gravacao_direta(tipo: str, dados: dict, avisos: list[dict]) -> Decisao:
    """Grava direto só a proposta **limpa** (nenhum aviso) e abaixo do teto. Com aviso, não grava e devolve o que está em dúvida,
    para o Claude perguntar ao usuário; acima do teto, não grava e orienta a registrar pelo app."""
    teto = TETO_PAGAMENTO_DIRETO if tipo == "pagamento" else TETO_DESPESA_DIRETA
    if Decimal(dados["valor"]) > teto:
        return Decisao(gravar=False, motivo="acima_do_teto",
                       mensagem=f"O valor passa de {formatar_moeda(teto)}, o máximo que o chat grava sozinho. Registre pelo app.")
    if avisos:
        return Decisao(gravar=False, motivo="duvida", mensagem=" ".join(a["texto"] for a in avisos))
    return Decisao(gravar=True, motivo="", mensagem="")


# ---------------------------------------------------------------- cadastro de cliente e de veículo --

PREFIXO_CPF_PROVISORIO = "[CPF PROVISÓRIO]"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def cpf_final(cpf: str) -> str:
    """Os 4 últimos dígitos (é só o que o chat vê do CPF)."""
    return apenas_digitos(cpf)[-4:]


def proximo_cpf_provisorio(existentes: list[str]) -> str:
    """Próximo CPF provisório: 11 dígitos 0000000000N (N = 1, 2, 3...) com dígito verificador inválido e ainda não usado."""
    usados = {apenas_digitos(c) for c in existentes}
    numero = 1
    while True:
        candidato = str(numero).zfill(11)
        if candidato not in usados and not validar_cpf(candidato):
            return candidato
        numero += 1


def normalizar_cliente(entrada: dict) -> dict:
    """Cadastro de cliente pelo chat. Sem CPF válido só entra com `cpf_provisorio` verdadeiro (o CPF real é completado depois).
    Levanta ValueError em português. O CPF provisório em si é gerado depois, na hora de gravar."""
    nome = " ".join(str(entrada.get("nome") or "").split())
    if len(nome) < 3 or len(nome.split()) < 2:
        raise ValueError("Informe o nome completo do cliente (nome e sobrenome).")
    if len(nome) > 160:
        raise ValueError("O nome passa de 160 caracteres.")
    provisorio = bool(entrada.get("cpf_provisorio"))
    cpf = apenas_digitos(entrada.get("cpf"))
    if not provisorio and not validar_cpf(cpf):
        raise ValueError("Informe um CPF válido; sem CPF, marque cpf_provisorio e complete depois.")
    if provisorio and cpf:
        raise ValueError("Com cpf_provisorio não se informa CPF.")
    dados = {"nome": nome, "cpf": None if provisorio else cpf, "cpf_provisorio": provisorio}
    for campo, rotulo in (("telefone", "telefone"), ("whatsapp", "WhatsApp")):
        bruto = apenas_digitos(entrada.get(campo))
        if bruto and not validar_telefone(bruto):
            raise ValueError(f"Informe o {rotulo} com DDD e número válidos.")
        dados[campo] = formatar_telefone(bruto) if bruto else None
    email = str(entrada.get("email") or "").strip()
    if email and not _EMAIL.match(email):
        raise ValueError("Informe um e-mail válido.")
    dados["email"] = email or None
    for campo, limite in (("endereco", 300), ("observacoes", TAMANHO_OBSERVACAO)):
        texto = " ".join(str(entrada.get(campo) or "").split())
        if len(texto) > limite:
            raise ValueError(f"O campo {campo} passa de {limite} caracteres.")
        dados[campo] = texto or None
    dados["confirmar_homonimo"] = bool(entrada.get("confirmar_homonimo"))
    return dados


def normalizar_veiculo(entrada: dict) -> dict:
    placa = normalizar_placa(entrada.get("placa"))
    if not validar_placa(placa):
        raise ValueError("Placa: use ABC1234 ou ABC1D23.")
    marca = " ".join(str(entrada.get("marca") or "").split())
    modelo = " ".join(str(entrada.get("modelo") or "").split())
    if not marca or not modelo:
        raise ValueError("Informe a marca e o modelo do veículo.")
    tipo = _simplificar(entrada.get("tipo") or "moto")
    if tipo not in ("moto", "carro"):
        raise ValueError("O tipo precisa ser moto ou carro.")
    try:
        km = int(str(entrada.get("km_atual") or 0).replace(".", ""))
        anos = [int(entrada[c]) if entrada.get(c) not in (None, "") else None for c in ("ano_fabricacao", "ano_modelo")]
    except (TypeError, ValueError):
        raise ValueError("Quilometragem e anos precisam ser números inteiros.") from None
    if km < 0 or km > 2_000_000:
        raise ValueError("A quilometragem precisa estar entre 0 e 2.000.000.")
    if any(a is not None and not 1950 <= a <= hoje_br().year + 1 for a in anos):
        raise ValueError("Informe anos entre 1950 e o ano que vem.")
    cor = " ".join(str(entrada.get("cor") or "").split())[:40] or None
    obs = " ".join(str(entrada.get("observacoes") or "").split())
    if len(obs) > TAMANHO_OBSERVACAO:
        raise ValueError(f"O campo observações passa de {TAMANHO_OBSERVACAO} caracteres.")
    return {"placa": placa, "marca": marca[:60], "modelo": modelo[:80], "tipo": tipo, "km_atual": km,
            "ano_fabricacao": anos[0], "ano_modelo": anos[1], "cor": cor, "observacoes": obs or None}
