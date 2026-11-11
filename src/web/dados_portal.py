"""Fronteira de leitura do Portal do Locatário. Os testes das rotas trocam estes serviços por dados fictícios.

O locatário não tem acesso direto às tabelas: tudo vem da RPC `rpc_portal_locatario`, que o identifica pelo login e só
devolve o(s) contrato(s) ativo(s) dele."""

import logging
from datetime import date
from decimal import Decimal

from src.domain.comprovante_documento import STATUS_ROTULO, STATUS_TOM, nome_do_documento, pode_enviar
from src.domain.documentos_lista import SITUACAO_ROTULO, TOM_SITUACAO as TOM_SITUACAO_DOCUMENTO
from src.domain.manutencao_regras import calcular_proxima_manutencao, calcular_situacao
from src.domain.valores import hoje_br
from src.services import portal_locatario

ROTULO_SITUACAO = {
    "em_dia": "Óleo em dia",
    "proxima": "Troca de óleo próxima",
    "vencida": "Troca de óleo vencida",
}
TOM_SITUACAO = {"em_dia": "ok", "proxima": "atencao", "vencida": "perigo"}

log = logging.getLogger(__name__)


def _resumo(contrato, dados, hoje):
    ultima_data = contrato.get("ultima_data")
    previsto = calcular_proxima_manutencao(
        contrato.get("ultima_km"),
        contrato.get("intervalo_km"),
        date.fromisoformat(str(ultima_data)[:10]) if ultima_data else None,
        contrato.get("intervalo_dias"),
    )
    situacao = calcular_situacao(
        contrato["km_atual"], previsto["proxima_km"], hoje, previsto["proxima_data"], dados["alerta_km"], dados["alerta_dias"]
    )
    proxima_km = previsto["proxima_km"]
    multa = Decimal(str(dados["multa_valor"]))
    return {
        **contrato,
        "situacao": situacao, "rotulo_situacao": ROTULO_SITUACAO[situacao], "tom": TOM_SITUACAO[situacao],
        "proxima_km": proxima_km,
        "faltam_km": proxima_km - contrato["km_atual"] if proxima_km is not None and proxima_km >= contrato["km_atual"] else None,
        "plano_configurado": not (contrato.get("intervalo_km") is None and contrato.get("ultima_km") is None),
        "multa": multa, "avisa_multa": multa > 0 and proxima_km is not None,
        "trocas": contrato.get("trocas") or [],
    }


def _documento(d):
    """Documento pendente da moto com os rótulos da tela e se o locatário pode enviar o comprovante agora."""
    return {
        **d,
        "nome": nome_do_documento(d["tipo"], d.get("descricao"), d.get("ano_referencia")),
        "rotulo_situacao": SITUACAO_ROTULO.get(d["situacao"], d["situacao"]), "tom": TOM_SITUACAO_DOCUMENTO.get(d["situacao"], "neutro"),
        "pode_enviar": pode_enviar(d),
        "rotulo_envio": STATUS_ROTULO.get(d.get("envio_status")), "tom_envio": STATUS_TOM.get(d.get("envio_status"), "neutro"),
    }


def _documentos():
    """Documentos pendentes das motos do locatário. Se a leitura falhar (ex.: migration ainda não aplicada), o portal segue sem eles."""
    try:
        return [_documento(d) for d in portal_locatario.documentos_do_locatario()], False
    except Exception:
        log.exception("Não foi possível ler os documentos do locatário.")
        return [], True


def carregar(hoje=None):
    """Nome, multa fixa e contratos ativos do locatário, cada um com a situação do óleo e o plano."""
    dados = portal_locatario.dados_portal()
    hoje = hoje or hoje_br()
    documentos, erro_documentos = _documentos()
    return {
        "cliente_id": dados["cliente_id"], "nome": dados["nome"], "primeiro_nome": dados["nome"].split()[0],
        "contratos": [_resumo(c, dados, hoje) for c in dados["contratos"]],
        "documentos": documentos, "erro_documentos": erro_documentos,
    }


def documento_do_locatario(documento_id):
    """O documento pendente do próprio locatário (None se o id não for dele) junto com os dados do portal."""
    dados = carregar()
    return dados, next((d for d in dados["documentos"] if d["documento_id"] == documento_id), None)


def contrato_do_locatario(contrato_id):
    """O contrato ativo do próprio locatário (None se o id não for dele) junto com os dados do portal."""
    dados = carregar()
    contrato = next((c for c in dados["contratos"] if c["contrato_id"] == contrato_id), None)
    return dados, contrato
