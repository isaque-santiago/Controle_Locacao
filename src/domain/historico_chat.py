"""Histórico dos chats («Locadora - Acompanhamento Financeiro» e «Contratos Locadora») entregue pelo conector (seção 24 do plano).

O Claude de cada chat extrai o histórico e o entrega em lotes pequenos para uma **caixa de rascunho**: nada entra no financeiro. O
banco compara cada registro com o que já existe (já existe, novo ou diverge) e o dono confere antes de qualquer carga. Estas regras
puras normalizam e validam o lote, montam o resumo de cada registro e calculam a **cobertura por período** (quais dias do chat já foram
entregues e onde há buracos), porque um chat longo pode não ter sido lido inteiro. O banco repete as conferências estruturais."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal

from src.domain.entradas import apenas_digitos, normalizar_placa
from src.domain.formatadores import formatar_data, formatar_moeda
from src.domain.valores import decimal_br
from src.domain.validadores import validar_placa

FONTES = ("chat_financeiro", "chat_contratos")
TIPOS = ("pagamento", "despesa", "multa", "divida", "movimento_socio", "cliente", "veiculo", "contrato", "outro")
SITUACOES = ("nova", "ja_existe", "diverge", "sem_comparacao", "descartada", "aplicada")
ROTULO_SITUACAO = {"nova": "nova (não existe no sistema)", "ja_existe": "já existe", "diverge": "diverge do sistema",
                   "sem_comparacao": "sem comparação automática", "descartada": "descartada", "aplicada": "aplicada"}

MAXIMO_REGISTROS_POR_LOTE = 50
MAXIMO_JANELA_DIAS = 1100  # um lote cobre no máximo ~3 anos de chat
TAMANHO_DADOS = 2000
TAMANHO_TRECHO = 600
TAMANHO_ROTULO = 60
TAMANHO_OBSERVACAO = 500
TAMANHO_RESUMO = 200
MAXIMO_ERROS_MOSTRADOS = 5
_CHAVES_DE_DINHEIRO = ("valor", "valor_periodo", "saldo", "valor_total", "entrada", "valor_parcela", "caucao", "multa", "juros")
# Para o pagamento composto (semana + caução + multa num só valor): um registro por parte, cada um com a sua finalidade.
FINALIDADES = {"locacao": "locacao", "semana": "locacao", "parcela": "locacao", "caucao": "caucao", "multa": "multa", "dano": "dano", "outros": "outros"}


def _simplificar(texto) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _data(bruto, campo: str, hoje: date, obrigatoria: bool = False) -> date | None:
    if bruto in (None, ""):
        if obrigatoria:
            raise ValueError(f"Informe {campo}.")
        return None
    texto = str(bruto).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            dia = datetime.strptime(texto, formato).date()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"{campo}: use o formato aaaa-mm-dd ou dd/mm/aaaa.")
    if dia > hoje + timedelta(days=1):
        raise ValueError(f"{campo} não pode estar no futuro.")
    if dia.year < 2000:
        raise ValueError(f"{campo}: ano inválido.")
    return dia


def _chave_do_campo(nome) -> str:
    return re.sub(r"[^a-z0-9_]", "", _simplificar(nome).replace(" ", "_"))[:40]


def normalizar_dados(bruto) -> dict:
    """Campos livres do registro (só valores simples). Dinheiro vira '275.00', placa vira ABC1D23, CPF fica só com os dígitos."""
    if not isinstance(bruto, dict) or not bruto:
        raise ValueError("os dados precisam ser um objeto com pelo menos um campo")
    dados = {}
    for nome, valor in bruto.items():
        chave = _chave_do_campo(nome)
        if not chave:
            raise ValueError("há um campo sem nome")
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            continue
        if chave == "faltando" and isinstance(valor, list):  # lista curta de campos que o chat não achou
            valor = ", ".join(str(v) for v in valor if str(v).strip())
        if isinstance(valor, (dict, list)):
            raise ValueError(f"o campo {chave} precisa ser um valor simples (texto, número ou verdadeiro/falso)")
        if chave in ("data_estimada", "inferido") and not isinstance(valor, bool) and _simplificar(valor) in ("sim", "true", "1", "verdadeiro"):
            valor = True
        if chave == "data_estimada" and valor is not True:
            continue  # só interessa quando é verdadeiro
        if chave == "finalidade":
            canonica = FINALIDADES.get(_simplificar(valor))
            if canonica is None:
                raise ValueError("a finalidade precisa ser: semana, caucao, multa, dano ou outros")
            dados[chave] = canonica
            continue
        if chave == "ocorrencia":
            try:
                dados[chave] = max(1, int(valor))
            except (TypeError, ValueError):
                raise ValueError("a ocorrência precisa ser um número inteiro (2 para o segundo registro igual no mesmo dia)") from None
            continue
        if isinstance(valor, bool):
            dados[chave] = valor
        elif chave in _CHAVES_DE_DINHEIRO:
            try:
                dados[chave] = str(decimal_br(Decimal(str(valor)) if isinstance(valor, (int, float)) else valor))
            except ValueError:
                raise ValueError(f"o campo {chave} precisa ser um valor em reais, sem negativos") from None
        elif chave == "placa":
            placa = normalizar_placa(valor)
            if not validar_placa(placa):
                raise ValueError(f"placa inválida ({str(valor)[:12]}): use ABC1234 ou ABC1D23")
            dados[chave] = placa
        elif chave == "cpf":
            digitos = apenas_digitos(valor)
            if len(digitos) != 11:
                raise ValueError("o CPF precisa ter 11 dígitos (se não souber, deixe o campo de fora)")
            dados[chave] = digitos
        elif isinstance(valor, (int, float)):
            dados[chave] = valor
        else:
            texto = " ".join(str(valor).split())
            dados[chave] = texto[:200]
    if not dados:
        raise ValueError("os dados ficaram vazios")
    if len(str(dados)) > TAMANHO_DADOS:
        raise ValueError(f"os dados passam de {TAMANHO_DADOS} caracteres: divida em campos menores")
    return dados


def resumo_do_registro(tipo: str, dados: dict, data: date | None) -> str:
    """Texto curto para o chat e o dono reconhecerem o registro (sem CPF inteiro)."""
    def moeda(chave):
        return formatar_moeda(Decimal(dados[chave])) if chave in dados else None

    quando = formatar_data(data) if data else None
    pessoa = dados.get("cliente") or dados.get("nome") or dados.get("placa")
    partes: list = []
    if tipo == "pagamento":
        partes = [f"Pagamento de {pessoa}" if pessoa else "Pagamento", moeda("valor"), f"em {quando}" if quando else None]
    elif tipo == "despesa":
        partes = [f"Despesa{' (' + dados['placa'] + ')' if 'placa' in dados else ''}", moeda("valor"), f"em {quando}" if quando else None,
                  dados.get("descricao")]
    elif tipo == "multa":
        partes = [f"Multa {dados.get('placa', '')} AIT {dados.get('ait', '?')}".strip(), moeda("valor"), f"em {quando}" if quando else None]
    elif tipo == "cliente":
        partes = [f"Cliente {dados.get('nome', '?')}", f"(CPF final {dados['cpf'][-4:]})" if "cpf" in dados else None]
    elif tipo == "veiculo":
        partes = [f"Veículo {dados.get('placa', '?')}", dados.get("marca"), dados.get("modelo")]
    elif tipo == "contrato":
        partes = [f"Contrato {dados.get('cliente') or dados.get('nome') or '?'} / {dados.get('placa', '?')}", moeda("valor_periodo"),
                  dados.get("periodicidade"), f"desde {quando}" if quando else None]
    if not any(partes):
        partes = [tipo.replace("_", " ").capitalize()] + [f"{k}={v}" for k, v in list(dados.items())[:4] if k != "cpf"]
    texto = " ".join(str(p) for p in partes if p)
    marcas = [m for ok, m in ((dados.get("data_estimada") is True, "data estimada"), (bool(dados.get("inferido")), "inferido"),
                              (bool(dados.get("faltando")), f"falta: {dados.get('faltando')}")) if ok]
    return (texto[:TAMANHO_RESUMO - 40] + (" [" + "; ".join(marcas) + "]" if marcas else "")) if marcas else texto[:TAMANHO_RESUMO]


def normalizar_registro(entrada, fonte: str, hoje: date) -> dict:
    """Um registro do lote pronto para a RPC. Levanta ValueError (sem o número do registro; quem chama o acrescenta)."""
    if not isinstance(entrada, dict):
        raise ValueError("cada registro precisa ser um objeto")
    tipo = _chave_do_campo(entrada.get("tipo"))
    if tipo not in TIPOS:
        raise ValueError("o tipo precisa ser: " + ", ".join(TIPOS))
    data = _data(entrada.get("data"), "a data do registro", hoje)
    dados = normalizar_dados(entrada.get("dados"))
    trecho = " ".join(str(entrada.get("trecho") or "").split())
    if not trecho:
        raise ValueError("faltou o trecho do chat que originou o registro (campo trecho)")
    return {"tipo": tipo, "data": data.isoformat() if data else None, "dados": dados, "trecho": trecho[:TAMANHO_TRECHO],
            "resumo": resumo_do_registro(tipo, dados, data)}


def normalizar_lote(entrada: dict, hoje: date) -> dict:
    """Lote inteiro: ou todos os registros valem, ou nenhum é enviado (a mensagem lista os primeiros erros com o número de cada um)."""
    fonte = _chave_do_campo(entrada.get("fonte"))
    if fonte not in FONTES:
        raise ValueError("a fonte precisa ser: " + ", ".join(FONTES))
    rotulo = " ".join(str(entrada.get("rotulo") or "").split())
    if not rotulo or len(rotulo) > TAMANHO_ROTULO:
        raise ValueError(f"o rótulo do lote é obrigatório e tem até {TAMANHO_ROTULO} caracteres")
    inicio = _data(entrada.get("periodo_inicio"), "o início do período", hoje, obrigatoria=True)
    fim = _data(entrada.get("periodo_fim"), "o fim do período", hoje, obrigatoria=True)
    if fim < inicio:
        raise ValueError("o fim do período não pode ser antes do início")
    if (fim - inicio).days > MAXIMO_JANELA_DIAS:
        raise ValueError(f"o período passa de {MAXIMO_JANELA_DIAS} dias: divida o chat em lotes menores")
    registros = entrada.get("registros")
    if not isinstance(registros, list) or not registros:
        raise ValueError("envie ao menos um registro")
    if len(registros) > MAXIMO_REGISTROS_POR_LOTE:
        raise ValueError(f"envie no máximo {MAXIMO_REGISTROS_POR_LOTE} registros por vez")
    observacao = " ".join(str(entrada.get("observacao") or "").split())
    if len(observacao) > TAMANHO_OBSERVACAO:
        raise ValueError(f"a observação passa de {TAMANHO_OBSERVACAO} caracteres")
    normalizados, erros = [], []
    for i, bruto in enumerate(registros, start=1):
        try:
            registro = normalizar_registro(bruto, fonte, hoje)
        except ValueError as erro:
            erros.append(f"registro {i}: {erro}")
            continue
        if registro["data"] and not inicio.isoformat() <= registro["data"] <= fim.isoformat():
            erros.append(f"registro {i}: a data {formatar_data(registro['data'])} está fora do período do lote")
            continue
        normalizados.append(registro)
    if erros:
        extra = f" (e mais {len(erros) - MAXIMO_ERROS_MOSTRADOS})" if len(erros) > MAXIMO_ERROS_MOSTRADOS else ""
        raise ValueError("Nenhum registro foi enviado. Corrija e envie o lote de novo: " + "; ".join(erros[:MAXIMO_ERROS_MOSTRADOS]) + extra + ".")
    return {"fonte": fonte, "rotulo": rotulo, "periodo_inicio": inicio.isoformat(), "periodo_fim": fim.isoformat(),
            "observacao": observacao or None, "registros": normalizados}


# ---------------------------------------------------------------- cobertura por período --

def _como_data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def periodos_cobertos(lotes: list[tuple]) -> list[tuple[date, date]]:
    """Junta os períodos dos lotes (inclusive os que se tocam ou se sobrepõem) em faixas contínuas, em ordem."""
    faixas: list[list[date]] = []
    for inicio, fim in sorted((_como_data(i), _como_data(f)) for i, f in lotes):
        if faixas and inicio <= faixas[-1][1] + timedelta(days=1):
            faixas[-1][1] = max(faixas[-1][1], fim)
        else:
            faixas.append([inicio, fim])
    return [(a, b) for a, b in faixas]


def lacunas(lotes: list[tuple]) -> list[tuple[date, date]]:
    """Buracos entre as faixas já entregues (dias que nenhum lote cobriu), do primeiro ao último dia entregue."""
    faixas = periodos_cobertos(lotes)
    return [(faixas[i][1] + timedelta(days=1), faixas[i + 1][0] - timedelta(days=1)) for i in range(len(faixas) - 1)]
