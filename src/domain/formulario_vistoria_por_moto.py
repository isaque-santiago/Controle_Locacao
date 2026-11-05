"""Formulário de vistoria com um bloco por moto vinculada (novo contrato e encerramento).

O bloco da moto principal usa os nomes de sempre (`km`, `nivel_combustivel`, `item_...`); o da n-ésima vinculada
usa os mesmos nomes com o prefixo `vinc<n>_` (`vinc1_km`...), mais o campo escondido `vinc<n>_moto` com o id da
moto, que confere se a lista de motos não mudou entre abrir e enviar o formulário. Funções puras: recebem o texto
enviado pelo navegador e devolvem os dados prontos para o serviço, ou levantam `ErroDeCampos`."""

from src.domain.formulario_contrato import ler_vistoria, texto_da_vistoria, vistoria_inicial
from src.domain.formulario_moto import ErroDeCampos

PREFIXO_VINCULADA = "vinc"


def prefixo(indice: int) -> str:
    """Prefixo dos campos da n-ésima moto vinculada (a primeira é 1)."""
    return f"{PREFIXO_VINCULADA}{indice}_"


def com_prefixo(dados: dict, pref: str) -> dict:
    return {pref + chave: valor for chave, valor in dados.items()}


def sem_prefixo(entrada: dict, pref: str) -> dict:
    return {chave[len(pref):]: valor for chave, valor in entrada.items() if chave.startswith(pref)}


def textos_iniciais(motos: list) -> dict:
    """Texto inicial dos blocos das vinculadas (km da moto, combustível vazio e checklist todo 'ok')."""
    texto: dict = {}
    for n, moto in enumerate(motos, start=1):
        texto.update(com_prefixo(vistoria_inicial(moto["km_atual"]), prefixo(n)))
    return texto


def texto_das_vinculadas(entrada: dict, motos: list) -> dict:
    """O que foi digitado nos blocos das vinculadas, para o formulário voltar com o texto (inclusive inválido)."""
    texto: dict = {}
    for n in range(1, len(motos) + 1):
        pref = prefixo(n)
        texto.update(com_prefixo(texto_da_vistoria(sem_prefixo(entrada, pref)), pref))
    return texto


def ler_vistorias_vinculadas(entrada: dict, motos: list) -> list:
    """Vistoria de cada moto vinculada, na ordem de `motos` (cada uma com `id` e `km_atual`), pronta para o
    serviço: o km não pode ser menor que o atual da moto. Todos os erros vêm juntos, com o nome do campo prefixado."""
    erros: dict = {}
    lidas = []
    for n, moto in enumerate(motos, start=1):
        pref = prefixo(n)
        if str(entrada.get(pref + "moto") or "") != str(moto["id"]):
            erros[pref + "km"] = "A lista de motos do contrato mudou. Volte uma etapa e reabra esta."
            continue
        try:
            vistoria = ler_vistoria(sem_prefixo(entrada, pref), moto["km_atual"])
        except ErroDeCampos as erro:
            erros.update(com_prefixo(erro.erros, pref))
            continue
        lidas.append({**vistoria, "moto_id": moto["id"]})
    if erros:
        raise ErroDeCampos(erros)
    return lidas
