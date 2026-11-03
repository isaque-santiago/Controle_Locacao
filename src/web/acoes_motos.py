"""Gravações das telas de Motos: a rota chama estas funções, que chamam os serviços.

Fronteira de escrita (como `dados_motos` é a de leitura): os testes das rotas trocam este módulo
por um falso, e nenhuma rota fala com o banco diretamente."""

from datetime import date

from src.services import documentos, motos


def criar_moto(dados: dict) -> dict:
    return motos.criar(dados)


def atualizar_moto(moto_id: str, dados: dict) -> dict:
    return motos.atualizar(moto_id, dados)


def registrar_km(moto_id: str, km: int, confirmar_km_menor: bool, chave_operacao: str | None) -> dict:
    return motos.atualizar_km(moto_id, km, confirmar_km_menor=confirmar_km_menor, chave_operacao=chave_operacao)


def alterar_situacao(moto_id: str, inativar: bool) -> dict:
    return motos.atualizar(moto_id, {"status": "inativa" if inativar else "disponivel"})


def obter_documento(documento_id: str) -> dict | None:
    return documentos.obter(documento_id)


def regularizar_documento(documento_id: str, data_regularizacao: date) -> dict:
    return documentos.regularizar(documento_id, data_regularizacao)
