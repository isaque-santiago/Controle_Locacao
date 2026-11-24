"""Ferramentas do conector do claude.ai que falam com o banco (seção 24.7b do plano).

O app entra no Supabase como o **usuário de serviço do conector**, que só executa as RPCs `rpc_conector_*` (a `service_role` nunca é
usada): mesmo que algo aqui falhasse, o banco não deixaria o chat ler tabelas, editar ou apagar. Cada ferramenta normaliza os
argumentos com as regras de `src/domain/pendencias.py`, chama a RPC e devolve um texto para o Claude: gravou, ou **NÃO gravou** e o
motivo, para ele perguntar ao usuário na conversa e tentar de novo. Erros inesperados nunca vão em detalhe para o chat."""

import logging
from threading import Lock
from time import time

from postgrest.exceptions import APIError

from src import db
from src.domain.formatadores import formatar_data, formatar_data_hora, formatar_moeda
from src.domain.pendencias import (
    chave_operacao_padrao,
    normalizar_cliente,
    normalizar_despesa,
    normalizar_pagamento,
    normalizar_veiculo,
)
from src.domain.valores import hoje_br
from src.repositories import conector as repositorio
from src.services.autenticacao import CredenciaisInvalidas, ServicoAutenticacao

log = logging.getLogger("locacao.conector")

_CODIGO_REGRA_DE_NEGOCIO = "P0001"  # `raise exception` das RPCs: a mensagem já está em português e pode ir para o chat
_MARGEM_RENOVAR_SEGUNDOS = 120
MENSAGEM_FALHA = "Não foi possível falar com o sistema agora. Nada foi gravado; tente de novo em instantes."
_ROTULO_ESTADO = {"aprovada": "gravado", "desfeita": "desfeito pelo dono", "pendente": "aguardando o dono", "recusada": "recusado pelo dono"}


def _resposta(texto: str, erro: bool = False) -> dict:
    return {"texto": texto, "erro": erro}


def texto_da_gravacao(r: dict) -> dict:
    """Resultado de uma RPC de gravação em texto para o chat. Quando NÃO gravou, é erro: o Claude deve perguntar ao usuário."""
    if r.get("gravado"):
        return _resposta(("Já estava gravado: " if r.get("repetida") else "Gravado: ") + f"{r.get('resumo')}.")
    motivo = r.get("motivo") or r.get("status") or "nao_gravado"
    return _resposta(f"NÃO GRAVADO ({motivo}): {r.get('mensagem')} Pergunte ao usuário o que falta e tente de novo.", erro=True)


def texto_das_cobrancas(linhas: list[dict]) -> dict:
    if not linhas:
        return _resposta("Nenhuma cobrança em aberto combina com a busca.")
    itens = [
        f"- cobranca_id={c['cobranca_id']} | {c['cliente_nome']} (CPF final {c['cpf_final']}) | placa {c['placa']} | "
        f"vencimento {formatar_data(c['vencimento'])} | valor {formatar_moeda(c['valor'])} | saldo {formatar_moeda(c['saldo'])}"
        for c in linhas
    ]
    clientes = {(c["cliente_nome"], c["cpf_final"]) for c in linhas}
    aviso = "\nHá mais de um cliente na lista: pergunte ao usuário qual é antes de registrar." if len(clientes) > 1 else ""
    return _resposta(f"{len(linhas)} cobrança(s) em aberto:\n" + "\n".join(itens) + aviso)


def texto_dos_veiculos(linhas: list[dict]) -> dict:
    if not linhas:
        return _resposta("Nenhum veículo combina com a busca.")
    return _resposta("\n".join(f"- moto_id={v['moto_id']} | {v['placa']} | {v['descricao']} | {v['status']}" for v in linhas))


def texto_dos_lancamentos(linhas: list[dict]) -> dict:
    if not linhas:
        return _resposta("O chat ainda não gravou nada.")
    return _resposta("\n".join(
        f"- {formatar_data_hora(x['criado_em'])} | {x['resumo']} | {_ROTULO_ESTADO.get(x['status'], x['status'])}"
        + (" | automático" if x.get("decisao_automatica") else "") for x in linhas))


class ServicoConector:
    """Executa as ferramentas do chat. Mantém o login do usuário de serviço e o renova antes de vencer."""

    def __init__(self, email: str, senha: str, autenticacao=None, relogio=time, hoje=hoje_br):
        self._email, self._senha = email, senha
        self._autenticacao = autenticacao or ServicoAutenticacao()
        self._relogio, self._hoje = relogio, hoje
        self._trava = Lock()
        self._expira_em = 0.0
        self._cliente = None

    def _cliente_do_banco(self):
        with self._trava:
            if self._cliente is None or self._expira_em - self._relogio() <= _MARGEM_RENOVAR_SEGUNDOS:
                tokens = self._autenticacao.entrar(self._email, self._senha)
                self._cliente = db.criar_cliente_autenticado(tokens.access_token)
                self._expira_em = tokens.expira_em
            return self._cliente

    def executar(self, nome: str, argumentos: dict) -> dict:
        """{"texto", "erro"}. Nunca levanta: o que der errado vira uma resposta que o chat consegue entender."""
        try:
            with db.usar_cliente(self._cliente_do_banco()):
                resposta = self._despachar(nome, argumentos)
            log.info("Conector: ferramenta %s %s", nome, "com erro" if resposta["erro"] else "ok")
            return resposta
        except ValueError as erro:  # validação dos argumentos, em português
            return _resposta(str(erro), erro=True)
        except APIError as erro:
            if erro.code == _CODIGO_REGRA_DE_NEGOCIO:
                return _resposta(erro.message, erro=True)
            log.exception("Conector: falha do banco na ferramenta %s", nome)
            return _resposta(MENSAGEM_FALHA, erro=True)
        except CredenciaisInvalidas:
            log.error("Conector: o Supabase recusou o usuário de serviço (SERVICO_CONECTOR_EMAIL/SENHA).")
            return _resposta("O conector não conseguiu entrar no banco de dados. Avise o responsável pelo sistema.", erro=True)
        except Exception:
            log.exception("Conector: erro inesperado na ferramenta %s", nome)
            return _resposta(MENSAGEM_FALHA, erro=True)

    def _despachar(self, nome: str, a: dict) -> dict:
        if nome == "consultar_cobrancas_abertas":
            return texto_das_cobrancas(repositorio.cobrancas_abertas(a["busca"]))
        if nome == "buscar_veiculos":
            return texto_dos_veiculos(repositorio.veiculos(a["busca"]))
        if nome == "listar_ultimos_lancamentos":
            limite = a.get("limite")
            return texto_dos_lancamentos(repositorio.ultimos_lancamentos(10 if limite in (None, "") else int(limite)))
        if nome == "registrar_pagamento":
            return self._gravar(repositorio.registrar_pagamento, "pagamento", "chat_financeiro", normalizar_pagamento(a, self._hoje()), a)
        if nome == "registrar_despesa":
            return self._gravar(repositorio.registrar_despesa, "despesa", "chat_financeiro", normalizar_despesa(a, self._hoje()), a)
        if nome == "cadastrar_cliente":
            return self._gravar(repositorio.cadastrar_cliente, "cliente", "chat_contratos", normalizar_cliente(a), a)
        if nome == "cadastrar_veiculo":
            return self._gravar(repositorio.cadastrar_veiculo, "veiculo", "chat_contratos", normalizar_veiculo(a), a)
        raise ValueError("Ferramenta desconhecida.")

    @staticmethod
    def _gravar(rpc, tipo: str, origem: str, dados: dict, argumentos: dict) -> dict:
        """Sem `chave_operacao` do chat, a chave sai dos dados: a mesma proposta repetida não grava duas vezes."""
        chave = str(argumentos.get("chave_operacao") or "").strip() or chave_operacao_padrao(tipo, origem, dados)
        payload = {"origem": origem, "chave_operacao": chave, "trecho_origem": argumentos.get("trecho_origem"), "dados": dados}
        return texto_da_gravacao(rpc(payload))


def servico_do_ambiente() -> "ServicoConector | None":
    """O serviço ligado ao banco, ou None se faltar o usuário de serviço (aí só o `ping` funciona)."""
    from src.config import get_servico_conector

    try:
        email, senha = get_servico_conector()
    except RuntimeError:
        log.warning("Conector sem usuário de serviço: só o ping responde.")
        return None
    return ServicoConector(email, senha)
