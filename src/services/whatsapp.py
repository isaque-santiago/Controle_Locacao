"""Envio automático de mensagens por WhatsApp (seção 20 do plano): decide o que enviar, enfileira e envia.

Uma execução (`executar`) faz, nesta ordem:
1. lê tudo numa chamada (`rpc_whatsapp_dados`); com o envio desligado em Configurações, para aqui;
2. aplica as regras de `src/domain` e enfileira as mensagens devidas, já agrupadas por cliente. Isso acontece a
   qualquer hora: o que cair fora da janela (8h às 19h, segunda a sábado, sem feriado) fica marcado para o próximo
   horário válido;
3. dentro da janela, envia as pendentes pela Evolution, com pausa aleatória entre elas, conferindo antes se o
   número tem WhatsApp.

No modo teste nada vai ao cliente: tudo sai para o número de teste, com um aviso no início, e o envio é gravado com
o id `teste:...` (para o histórico de teste poder ser desfeito ao ligar o envio de verdade).
Rodar duas vezes seguidas não duplica nada (chave única no banco e reserva das pendentes).
"""

import logging
import random
import time
from datetime import datetime

from src.domain.avisos_whatsapp import avisos_devidos
from src.domain.dados_whatsapp import clientes_da_leitura, config_do_envio, entradas_das_regras
from src.domain.janela_envio import FUSO, dentro_da_janela, proximo_horario_valido
from src.domain.textos_whatsapp import OpcoesTexto, montar_payload
from src.repositories import mensagens_whatsapp as repo
from src.services.evolution import (
    ErroEnvio, EvolutionConfiguracaoInvalida, EvolutionIndisponivel, mascarar_numero,
)

log = logging.getLogger("locacao.whatsapp")

LOTE = 8                          # mensagens reservadas por execução (cabe na reserva de 10 min com as pausas)
PAUSA_MINIMA, PAUSA_MAXIMA = 20, 60   # segundos entre uma mensagem e outra


def enfileirar_devidos(agora: datetime, opcoes: OpcoesTexto, dados: dict | None = None) -> dict:
    """Enfileira as mensagens devidas. Devolve o resumo da RPC (`enfileiradas`, `sem_numero`, `duplicadas`, `bloqueadas`)."""
    momento = proximo_horario_valido(agora)
    bruto = dados if dados is not None else repo.dados(momento.date())
    config = config_do_envio(bruto)
    avisos = avisos_devidos(momento.date(), cfg=config["avisos"], **entradas_das_regras(bruto))
    mensagens = montar_payload(clientes_da_leitura(bruto), avisos, momento, opcoes)
    if not mensagens:
        return {"enfileiradas": 0, "sem_numero": 0, "duplicadas": 0, "bloqueadas": 0}
    return repo.enfileirar(mensagens)


def _numero_e_texto(msg: dict, config: dict):
    """No modo teste, o número de teste e o texto com o aviso; fora dele, o do cliente."""
    if not config["modo_teste"]:
        return msg["numero"], msg["texto"], msg["id"]
    aviso = f"[TESTE] Esta mensagem iria para {mascarar_numero(msg['numero'])}.\n\n"
    return config["numero_teste"], aviso + msg["texto"], f"teste:{msg['id']}"


def enviar_pendentes(evolution, config: dict, dormir=time.sleep, sorteio=random.uniform) -> dict:
    """Envia as pendentes devidas. Devolve contagens: enviadas, ignoradas, falhas."""
    resumo = {"enviadas": 0, "ignoradas": 0, "falhas": 0, "parou_por": None}
    if config["modo_teste"] and not config["numero_teste"]:
        resumo["parou_por"] = "modo_teste_sem_numero"
        return resumo
    try:
        conectada = evolution.estado() == "open"
    except EvolutionIndisponivel:
        resumo["parou_por"] = "evolution_indisponivel"
        return resumo
    if not conectada:
        resumo["parou_por"] = "instancia_desconectada"
        return resumo

    pendentes = repo.reservar(LOTE)
    for i, msg in enumerate(pendentes):
        if i:
            dormir(sorteio(PAUSA_MINIMA, PAUSA_MAXIMA))
        numero, texto, id_registro = _numero_e_texto(msg, config)
        try:
            if not evolution.numero_tem_whatsapp(numero):
                repo.registrar_resultado(msg["id"], "ignorada", "O número não tem WhatsApp.")
                resumo["ignoradas"] += 1
                continue
            id_evolution = evolution.enviar_texto(numero, texto)
        except EvolutionConfiguracaoInvalida:
            raise
        except EvolutionIndisponivel as erro:
            repo.registrar_resultado(msg["id"], "falhou", mascarar_numero(str(erro)))
            resumo["falhas"] += 1
            resumo["parou_por"] = "evolution_indisponivel"
            break
        except ErroEnvio as erro:
            repo.registrar_resultado(msg["id"], "falhou", mascarar_numero(str(erro)))
            resumo["falhas"] += 1
            continue
        id_gravado = id_registro if config["modo_teste"] else (id_evolution or None)
        repo.registrar_resultado(msg["id"], "enviada", None, id_gravado)
        resumo["enviadas"] += 1
    return resumo


def executar(evolution, opcoes: OpcoesTexto, agora: datetime | None = None, dormir=time.sleep, sorteio=random.uniform) -> dict:
    """Uma rodada completa (o script agendado chama isto a cada 15 a 30 minutos)."""
    agora = (agora or datetime.now(FUSO)).astimezone(FUSO)
    momento = proximo_horario_valido(agora)
    bruto = repo.dados(momento.date())
    config = config_do_envio(bruto)
    if not config["ativo"]:
        return {"ativo": False}

    resumo = {"ativo": True, "modo_teste": config["modo_teste"],
              "fila": enfileirar_devidos(agora, opcoes, dados=bruto)}
    if dentro_da_janela(agora):
        resumo["envio"] = enviar_pendentes(evolution, config, dormir, sorteio)
    else:
        resumo["envio"] = {"parou_por": "fora_da_janela"}
    log.info("rodada do WhatsApp: %s", resumo)
    return resumo
