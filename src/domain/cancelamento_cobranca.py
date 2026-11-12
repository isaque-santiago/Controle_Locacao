"""Cancelamento de cobrança pelo dono (pendência da Fase 7). Funções puras.

Regra confirmada com o dono (12/11/2026): só a cobrança em aberto (aberta ou atrasada) e SEM nenhum pagamento registrado pode ser
cancelada, e o motivo é obrigatório. Com pagamento, o dono precisa estornar antes (o banco recusa do mesmo jeito: `rpc_cancelar_cobranca`)."""

from decimal import Decimal

from src.domain.formulario_moto import ErroDeCampos, _texto

MOTIVO_MINIMO, MOTIVO_MAXIMO = 3, 200
SITUACOES_ABERTAS = ("aberta", "atrasada")


def pode_cancelar(cobranca: dict) -> bool:
    """Em aberto e sem pagamento nenhum. `valor_pago` vem de `vw_cobrancas`; sem ele, considera-se que nada foi pago."""
    return cobranca.get("situacao") in SITUACOES_ABERTAS and Decimal(str(cobranca.get("valor_pago") or 0)) == 0


def motivo_da_recusa(cobranca: dict) -> str:
    """Por que esta cobrança não pode ser cancelada (para a tela explicar em vez de só esconder o botão)."""
    if cobranca.get("situacao") == "cancelada":
        return "Esta cobrança já está cancelada."
    if cobranca.get("situacao") == "paga":
        return "Cobrança paga não pode ser cancelada."
    if Decimal(str(cobranca.get("valor_pago") or 0)) > 0:
        return "Esta cobrança já tem pagamento registrado e não pode ser cancelada."
    return ""


def ler_cancelamento(entrada: dict) -> str:
    """Motivo do cancelamento (3 a 200 caracteres), guardado junto com a cobrança."""
    motivo = _texto(entrada, "motivo")
    if len(motivo) < MOTIVO_MINIMO:
        raise ErroDeCampos({"motivo": f"Motivo: explique por que a cobrança é cancelada (mínimo {MOTIVO_MINIMO} letras)."})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ErroDeCampos({"motivo": f"Motivo: use no máximo {MOTIVO_MAXIMO} caracteres."})
    return motivo
