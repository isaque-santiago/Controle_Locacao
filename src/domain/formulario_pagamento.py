"""Leitura e validação do formulário de pagamento de cobrança.

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo, para a tela mostrar o erro ao lado do campo."""

from datetime import date
from decimal import Decimal

from src.domain.cobrancas_lista import FORMAS_ROTULO
from src.domain.entradas import decimal_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _texto
from src.domain.mensagens import moeda

FORMAS = tuple(FORMAS_ROTULO)


def aba_da_cobranca(situacao: str, vencimento, hoje: date) -> str:
    """Aba da lista onde a cobrança em aberto aparece (para voltar a ela depois do pagamento)."""
    if situacao == "atrasada":
        return "atrasadas"
    venc = vencimento if isinstance(vencimento, date) else date.fromisoformat(str(vencimento)[:10])
    return "hoje" if venc <= hoje else "proximos"


def pagamento_inicial(data: date, saldo, encargos) -> dict:
    """Texto inicial dos campos: principal = saldo e extras = encargos da data (como no Streamlit)."""
    return {
        "data_pagamento": data.isoformat(),
        "principal": texto_moeda(saldo),
        "extras": texto_moeda(encargos),
        "forma": FORMAS[0],
        "observacoes": "",
    }


def texto_do_pagamento(entrada: dict) -> dict:
    return {
        "data_pagamento": _texto(entrada, "data_pagamento"),
        "principal": _texto(entrada, "principal"),
        "extras": _texto(entrada, "extras"),
        "forma": _texto(entrada, "forma"),
        "observacoes": _texto(entrada, "observacoes"),
    }


def ler_pagamento(entrada: dict, saldo) -> dict:
    """Pagamento pronto para `cobrancas.registrar_pagamento`. O principal vai de 0,01 ao saldo da
    cobrança (menos que o saldo deixa o restante em aberto); multa e adicional não podem ser negativos."""
    erros: dict[str, str] = {}
    saldo = Decimal(str(saldo))
    data = _coletar(erros, "data_pagamento", _data_iso, _texto(entrada, "data_pagamento"), "Data do pagamento", True)
    principal = _coletar(erros, "principal", decimal_campo, entrada.get("principal"), "Principal recebido", positivo=True)
    if principal is not None and principal > saldo:
        erros["principal"] = f"Principal recebido: não pode ser maior que o saldo da cobrança ({moeda(saldo)})."
    extras = _coletar(erros, "extras", decimal_campo, entrada.get("extras"), "Multa e adicional recebidos")
    forma = _texto(entrada, "forma")
    if forma not in FORMAS:
        erros["forma"] = "Forma de pagamento: escolha uma das opções."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "data": date.fromisoformat(data),
        "principal": principal,
        "extras": extras,
        "forma": forma,
        "observacoes": _texto(entrada, "observacoes") or None,
        "quitada": principal >= saldo,
    }
