"""Orquestra o portal do locatário: papel do usuário, troca de óleo e vínculo de acesso."""

from decimal import Decimal
from pathlib import PurePath

from postgrest.exceptions import APIError

from src.domain.arquivos import validar_arquivo
from src.domain.troca_oleo import avaliar_troca_oleo, validar_km_informado
from src.repositories import portal_locatario

_CODIGO_REGRA_DE_NEGOCIO = "P0001"  # raise exception ... nas RPCs
_EXTENSOES_PERMITIDAS = (".jpg", ".jpeg", ".png")
_TIPOS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _como_regra_de_negocio(erro: APIError) -> ValueError:
    """As RPCs explicam o problema em pt-BR; o app mostra a mensagem como está."""
    return ValueError(erro.message)


def dados_portal() -> dict:
    """Contratos ativos do locatário (moto, plano de óleo, últimas trocas) e a multa fixa."""
    return portal_locatario.dados_portal()


def registrar_troca_oleo(
    cliente_id: str, contrato: dict, km_texto: str, foto: tuple, nota: tuple, multa_valor
) -> dict:
    """Valida, envia a foto do painel e a nota fiscal e registra a troca via RPC.

    `contrato` é um item de dados_portal()["contratos"]; `foto` e `nota` são
    (nome, conteúdo em bytes). Confere tudo antes do upload para não deixar
    arquivos órfãos por erro que já dava para prever."""
    km = validar_km_informado(km_texto)
    avaliar_troca_oleo(
        km,
        contrato["km_atual"],
        contrato.get("ultima_km"),
        contrato.get("intervalo_km"),
        Decimal(str(multa_valor)),
    )
    for nome, conteudo in (foto, nota):
        validar_arquivo(nome, conteudo, _EXTENSOES_PERMITIDAS)

    try:
        caminhos = [
            portal_locatario.enviar_arquivo(
                cliente_id, nome, conteudo, _TIPOS[PurePath(nome).suffix.lower()]
            )
            for nome, conteudo in (foto, nota)
        ]
        return portal_locatario.registrar_troca(
            {
                "contrato_id": contrato["contrato_id"],
                "km": km,
                "foto_painel_path": caminhos[0],
                "nota_fiscal_path": caminhos[1],
            }
        )
    except APIError as erro:
        if erro.code == _CODIGO_REGRA_DE_NEGOCIO:
            raise _como_regra_de_negocio(erro) from erro
        raise


# ---- Somente o dono ----------------------------------------------------------


def _acesso(acao: str, cliente_id: str) -> dict:
    resposta = portal_locatario.gerenciar_acesso(acao, cliente_id)
    if not isinstance(resposta, dict) or not resposta.get("ok"):
        mensagem = resposta.get("erro") if isinstance(resposta, dict) else None
        raise ValueError(mensagem or "Não foi possível concluir. Tente novamente.")
    return resposta


def criar_acesso(cliente_id: str) -> dict:
    """Cria o login do locatário (CPF + senha aleatória) e o vincula ao cliente.

    Devolve {"email", "senha"}: a senha só existe nesta resposta (não fica gravada)."""
    resposta = _acesso("criar", cliente_id)
    return {"email": resposta["email"], "senha": resposta["senha"]}


def redefinir_senha(cliente_id: str) -> dict:
    """Gera outra senha aleatória para o locatário. Devolve {"email", "senha"}."""
    resposta = _acesso("redefinir", cliente_id)
    return {"email": resposta["email"], "senha": resposta["senha"]}


def remover_acesso(cliente_id: str) -> None:
    """Exclui o login do locatário (o vínculo com o cliente some junto)."""
    _acesso("remover", cliente_id)


def listar_trocas(cliente_id: str):
    return portal_locatario.listar_trocas(cliente_id)


def url_arquivo(arquivo_path: str, expira_em: int = 300) -> str:
    """URL assinada de curta duração — o bucket trocas_oleo é privado."""
    return portal_locatario.url_assinada(arquivo_path, expira_em)
