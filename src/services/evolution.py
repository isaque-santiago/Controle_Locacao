"""Cliente da Evolution API (envio de WhatsApp). Só fala HTTP; as regras ficam em `src/domain` e a orquestração
em `src/services/whatsapp.py`.

Endpoints usados (conferir contra a versão da instância, no Swagger dela, em `/docs`):
- `GET  /instance/connectionState/{instancia}`: a instância está conectada (`open`)?
- `POST /chat/whatsappNumbers/{instancia}`: o número tem WhatsApp?
- `POST /message/sendText/{instancia}`: envia o texto. Evolution v2 recebe `number` e `text`; a v1 recebe
  `number` e `textMessage.text`. A escolha é `EVOLUTION_VERSAO`.

Os erros dizem se vale tentar de novo: `EvolutionIndisponivel` (rede, 5xx, 408, 429 e instância desconectada) volta para a fila;
`EvolutionConfiguracaoInvalida` (chave recusada) para tudo; `ErroEnvio` é problema daquela mensagem. Nenhuma mensagem de
erro leva o texto enviado, a chave ou o número inteiro.
"""

import re

import httpx

_ATRASO_DIGITACAO_MS = 1200


class ErroEvolution(Exception):
    pass


class EvolutionIndisponivel(ErroEvolution):
    """Rede, 5xx ou instância desconectada: tentar de novo mais tarde."""


class EvolutionConfiguracaoInvalida(ErroEvolution):
    """Chave recusada ou instância inexistente: o envio inteiro deve parar."""


class ErroEnvio(ErroEvolution):
    """A Evolution recusou esta mensagem."""


def mascarar_numero(texto: str) -> str:
    """5511988887777 -> 55119****7777, para logs e mensagens de erro."""
    return re.sub(r"\b(\d{4,5})\d{4,5}(\d{4})\b", r"\1****\2", str(texto))


class ClienteEvolution:
    def __init__(self, url: str, apikey: str, instancia: str, versao: int = 2, *, transporte=None, timeout: float = 30.0):
        self._instancia = instancia
        self._versao = versao
        self._http = httpx.Client(
            base_url=url, headers={"apikey": apikey}, timeout=timeout, transport=transporte)

    def fechar(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ http --

    def _chamar(self, metodo: str, caminho: str, **kwargs):
        try:
            resposta = self._http.request(metodo, caminho, **kwargs)
        except httpx.RequestError as erro:
            raise EvolutionIndisponivel(f"Sem resposta da Evolution ({type(erro).__name__}).") from erro
        if resposta.status_code in (401, 403):
            raise EvolutionConfiguracaoInvalida("A Evolution recusou a chave (EVOLUTION_APIKEY).")
        if resposta.status_code in (408, 429):  # lenta ou pedindo para ir mais devagar: tentar de novo mais tarde
            raise EvolutionIndisponivel(f"A Evolution pediu para tentar depois ({resposta.status_code}).")
        if resposta.status_code >= 500:
            raise EvolutionIndisponivel(f"A Evolution respondeu {resposta.status_code}.")
        if resposta.status_code == 404 and "/instance/" in caminho:
            raise EvolutionConfiguracaoInvalida("A instância da Evolution não existe (EVOLUTION_INSTANCIA).")
        if resposta.status_code >= 400:
            raise ErroEnvio(f"A Evolution recusou o pedido ({resposta.status_code}).")
        try:
            return resposta.json()
        except ValueError as erro:
            raise EvolutionIndisponivel("Resposta da Evolution fora do formato esperado.") from erro

    # ----------------------------------------------------------------- ações --

    def estado(self) -> str:
        """`open` quando a instância está conectada ao WhatsApp."""
        dados = self._chamar("GET", f"/instance/connectionState/{self._instancia}")
        interno = dados.get("instance", dados) if isinstance(dados, dict) else {}
        return str(interno.get("state") or "desconhecido")

    def numero_tem_whatsapp(self, numero: str) -> bool:
        dados = self._chamar("POST", f"/chat/whatsappNumbers/{self._instancia}", json={"numbers": [numero]})
        if not isinstance(dados, list) or not dados:
            return False
        return bool(dados[0].get("exists"))

    def enviar_texto(self, numero: str, texto: str) -> str:
        """Envia e devolve o id da mensagem na Evolution (vazio se ela não informar)."""
        if self._versao == 1:
            corpo = {"number": numero, "options": {"delay": _ATRASO_DIGITACAO_MS, "presence": "composing"},
                     "textMessage": {"text": texto}}
        else:
            corpo = {"number": numero, "text": texto, "delay": _ATRASO_DIGITACAO_MS}
        dados = self._chamar("POST", f"/message/sendText/{self._instancia}", json=corpo)
        chave = dados.get("key") if isinstance(dados, dict) else None
        return str((chave or {}).get("id") or "")
