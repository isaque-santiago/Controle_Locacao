"""Política de duração da sessão (decisão do dono em 16/11/2026): locatário e dono ficam conectados por muito tempo.

O locatário não quer entrar toda hora; o risco (celular perdido) é tratado por "Sair de todos os dispositivos".
Funções puras: o relógio entra como parâmetro."""

UM_DIA_SEGUNDOS = 86400

# Sem usar o app por 90 dias, entra de novo. Cada uso renova o prazo.
INATIVIDADE_MAXIMA_SEGUNDOS = 90 * UM_DIA_SEGUNDOS
# Mesmo com uso contínuo, depois de 1 ano pede o login de novo (limita o estrago de um cookie roubado).
VIDA_MAXIMA_SEGUNDOS = 365 * UM_DIA_SEGUNDOS
# O aviso "sua sessão vai expirar" da tela só faz sentido para prazos curtos (um temporizador de navegador não passa de ~24 dias).
LIMITE_DO_AVISO_SEGUNDOS = UM_DIA_SEGUNDOS


def sessao_vencida(
    criada_em: float,
    ultima_atividade: float,
    agora: float,
    limite_inatividade: float = INATIVIDADE_MAXIMA_SEGUNDOS,
    vida_maxima: float = VIDA_MAXIMA_SEGUNDOS,
) -> bool:
    """Vencida por inatividade ou por idade. `criada_em` 0 = desconhecida: só vale a inatividade."""
    if agora - ultima_atividade > limite_inatividade:
        return True
    return bool(criada_em) and agora - criada_em > vida_maxima


def limite_do_aviso(limite_inatividade: float) -> int:
    """Segundos para o aviso de expiração da tela; 0 desliga o aviso (prazo longo demais para um aviso)."""
    return int(limite_inatividade) if 0 < limite_inatividade <= LIMITE_DO_AVISO_SEGUNDOS else 0
