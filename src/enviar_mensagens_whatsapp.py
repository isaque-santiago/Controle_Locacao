"""Rodada do envio automático por WhatsApp, para a Tarefa Agendada do Coolify (seção 20 do plano).

    python -m src.enviar_mensagens_whatsapp

Entra com o usuário de serviço (`SERVICO_MENSAGENS_EMAIL` e `SERVICO_MENSAGENS_SENHA`), que só executa as RPCs
`rpc_whatsapp_*` (a `service_role` não é usada), e chama `src.services.whatsapp.executar`. Rode a cada 15 a 30 minutos:
é seguro repetir. Fica em `src/` porque a imagem de produção só leva `src/` e `static/`.

Saída: uma linha JSON com o resumo da rodada. Código de saída: 0 = rodada feita (mesmo com o envio desligado ou a
Evolution fora do ar, que voltam na próxima rodada); 2 = configuração faltando ou recusada (variável de ambiente,
usuário de serviço, chave da Evolution); 1 = erro inesperado.
"""

import json
import logging
import sys

from src import db
from src.config import get_evolution, get_servico_mensagens, get_textos_whatsapp
from src.domain.textos_whatsapp import OpcoesTexto
from src.services import whatsapp
from src.services.autenticacao import CredenciaisInvalidas, ServicoAutenticacao
from src.services.evolution import ClienteEvolution, EvolutionConfiguracaoInvalida

log = logging.getLogger("locacao.whatsapp")


def _cliente_evolution() -> ClienteEvolution:
    dados = get_evolution()
    return ClienteEvolution(dados["url"], dados["apikey"], dados["instancia"], dados["versao"],
                            timeout=whatsapp.TIMEOUT_CHAMADA_SEGUNDOS)


def principal() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        email, senha = get_servico_mensagens()
        opcoes = OpcoesTexto(**get_textos_whatsapp())
        tokens = ServicoAutenticacao().entrar(email, senha)
    except RuntimeError as erro:
        log.error("Configuração faltando: %s", erro)
        return 2
    except CredenciaisInvalidas:
        log.error("O Supabase recusou o usuário de serviço (SERVICO_MENSAGENS_EMAIL/SENHA).")
        return 2

    criado = []

    def evolution():
        cliente = _cliente_evolution()
        criado.append(cliente)
        return cliente

    try:
        with db.usar_cliente(db.criar_cliente_autenticado(tokens.access_token)):
            resumo = whatsapp.executar(evolution, opcoes)
    except RuntimeError as erro:
        log.error("Configuração faltando: %s", erro)
        return 2
    except EvolutionConfiguracaoInvalida as erro:
        log.error("%s", erro)
        return 2
    except Exception:
        log.exception("Erro inesperado na rodada do WhatsApp.")
        return 1
    finally:
        for cliente in criado:
            cliente.fechar()
    print(json.dumps(resumo, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
