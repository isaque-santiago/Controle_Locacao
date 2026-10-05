"""Chave de operação: o que torna um reenvio idêntico ao primeiro (Plano de melhorias, Etapa 7).

Cada envio de formulário leva um uuid (`chave_operacao`) que o banco grava com o registro e
recusa na segunda vez. A mesma chave vale enquanto o conteúdo enviado for o mesmo: repetir o
envio (duplo clique, nova tentativa depois de a rede cair) reaproveita a chave e o servidor
devolve o registro já gravado. Conteúdo diferente é outra operação e ganha uma chave nova,
assim uma chave "esquecida" de uma tentativa que falhou nunca engole um lançamento diferente.

Funções puras; a sessão (Streamlit) guarda o par `(impressão, chave)` em `src/ui/feedback.py`.
"""

import hashlib
import json
from uuid import uuid4


def impressao(conteudo) -> str:
    """Resumo estável do conteúdo de um envio (dicionários, listas, Decimal e datas)."""
    texto = json.dumps(conteudo, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def chave_para(atual, conteudo, nova_chave=lambda: str(uuid4())):
    """Devolve `(impressao, chave)`: a chave `atual` (par guardado ou None) se o conteúdo é o
    mesmo; senão, uma chave nova. `nova_chave` existe para os testes fixarem o uuid."""
    marca = impressao(conteudo)
    if atual and atual[0] == marca:
        return atual
    return marca, nova_chave()
