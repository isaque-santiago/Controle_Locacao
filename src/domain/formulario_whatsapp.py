"""Formulário dos controles do envio de WhatsApp em Configurações (seção 20 do plano). Funções puras.

O dono liga ou desliga o envio, escolhe entre o modo teste (tudo vai só para o número de teste) e o envio de verdade, e
define quantos avisos de cada assunto podem se repetir. Sair do modo teste exige confirmação, porque a partir daí as
mensagens vão aos clientes."""

from src.domain.entradas import inteiro_campo
from src.domain.formulario_moto import ErroDeCampos, _coletar, _texto
from src.domain.numero_whatsapp import formatar_numero, normalizar_numero

MAX_REPETICOES_MINIMO, MAX_REPETICOES_MAXIMO = 1, 100
_MARCADO = {"on", "1", "true", "sim"}


def _marcado(entrada: dict, campo: str) -> bool:
    return _texto(entrada, campo).lower() in _MARCADO


def valores_iniciais(config: dict) -> dict:
    return {
        "ativo": bool(config.get("whatsapp_ativo")),
        "modo": "real" if config.get("whatsapp_modo_teste") is False else "teste",
        "numero_teste": formatar_numero(config.get("whatsapp_numero_teste")),
        "max_repeticoes": str(config.get("whatsapp_max_repeticoes") or 10),
        "confirmo": False,
    }


def texto_da_entrada(entrada: dict) -> dict:
    return {
        "ativo": _marcado(entrada, "ativo"),
        "modo": "real" if _texto(entrada, "modo") == "real" else "teste",
        "numero_teste": _texto(entrada, "numero_teste"),
        "max_repeticoes": _texto(entrada, "max_repeticoes"),
        "confirmo": _marcado(entrada, "confirmo"),
    }


def _numero_de_teste(texto: str, obrigatorio: bool):
    if not texto:
        if obrigatorio:
            raise ValueError("Número de teste: informe o seu celular com DDD para receber as mensagens de teste.")
        return None
    numero = normalizar_numero(texto)
    if numero is None:
        raise ValueError("Número de teste: informe um celular com DDD, por exemplo (11) 98888-7777.")
    return numero


def ler_whatsapp(entrada: dict) -> dict:
    """Colunas de `configuracoes` prontas para gravar. Erros por campo em `ErroDeCampos`."""
    v = texto_da_entrada(entrada)
    erros: dict[str, str] = {}
    teste_ligado = v["ativo"] and v["modo"] == "teste"
    numero = _coletar(erros, "numero_teste", _numero_de_teste, v["numero_teste"], teste_ligado)
    maximo = _coletar(erros, "max_repeticoes", inteiro_campo, v["max_repeticoes"],
                      "Máximo de avisos por assunto", MAX_REPETICOES_MINIMO, MAX_REPETICOES_MAXIMO)
    if v["ativo"] and v["modo"] == "real" and not v["confirmo"]:
        erros["confirmo"] = "Confirme que entendeu: com o modo teste desligado, as mensagens vão para os clientes."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "whatsapp_ativo": v["ativo"],
        "whatsapp_modo_teste": v["modo"] != "real",
        "whatsapp_numero_teste": numero,
        "whatsapp_max_repeticoes": maximo,
    }


MOTIVO_MAXIMO = 200


def ler_bloqueio(entrada: dict) -> str:
    """Motivo para o cliente deixar de receber mensagens automáticas (fica registrado, com a data)."""
    motivo = _texto(entrada, "motivo")
    if len(motivo) < 3:
        raise ErroDeCampos({"motivo": "Motivo: explique por que este cliente não deve receber mensagens (mínimo 3 letras)."})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ErroDeCampos({"motivo": f"Motivo: use no máximo {MOTIVO_MAXIMO} caracteres."})
    return motivo
