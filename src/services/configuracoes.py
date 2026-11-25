"""Configurações e backup manual das tabelas acessíveis ao usuário."""

import csv
import json
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from src.domain.configuracoes import validar_configuracao
from src.repositories import configuracoes
from src.repositories.consultas import todos

TABELAS = (
    "configuracoes",
    "motos",
    "clientes",
    "contratos",
    "cobrancas",
    "pagamentos",
    "historico_km",
    "itens_manutencao",
    "moto_plano_manutencao",
    "manutencoes",
    "manutencao_itens",
    "documentos_moto",
    "vistorias",
    "vistoria_fotos",
    "trocas_oleo",
    # Acrescentadas em 17/11/2026: sem elas o backup não servia para conferir despesas, multas, dívidas e sócio.
    "contas",
    "fornecedores",
    "despesas",
    "multas_transito",
    "dividas",
    "dividas_vencimentos",
    "pagamentos_divida",
    "movimentos_socio",
    "contrato_motos",
    "documento_comprovantes",
    "importacoes_lote",
    "whatsapp_grupos",
    "pedidos_senha_portal",
    "portal_eventos",
    # Acrescentadas em 25/11/2026: o que o chat gravou (histórico e auditoria) e o rascunho do histórico dos chats a conferir.
    "pendencias_lancamento",
    "historico_chat_lotes",
    "historico_chat_registros",
)
# Fora do backup, de propósito: `administradores` e `servico_mensagens` (nem o dono lê: só a própria linha) e a fila
# `mensagens_whatsapp` / `mensagens_whatsapp_itens` (o envio a recria a partir das cobranças).

# Tabelas sem coluna `id`: a ordem da leitura paginada usa a chave primária.
ORDEM_DA_TABELA = {"contrato_motos": ("contrato_id", "moto_id")}


def obter():
    return configuracoes.obter()


def atualizar(entrada):
    return configuracoes.atualizar(validar_configuracao(entrada))


def backup():
    saida = BytesIO()
    with ZipFile(saida, "w", ZIP_DEFLATED) as arquivo:
        manifesto = {}
        for nome in TABELAS:
            linhas = todos(nome, ordem=ORDEM_DA_TABELA.get(nome, "id"), usar_cache=False)
            texto = StringIO(newline="")
            if linhas:
                escritor = csv.DictWriter(texto, fieldnames=list(linhas[0]))
                escritor.writeheader()
                for linha in linhas:
                    escritor.writerow(
                        {
                            k: (
                                json.dumps(v, ensure_ascii=False)
                                if isinstance(v, (dict, list))
                                else v
                            )
                            for k, v in linha.items()
                        }
                    )
            arquivo.writestr(nome + ".csv", texto.getvalue().encode("utf-8-sig"))
            manifesto[nome] = len(linhas)
        arquivo.writestr("manifesto.json", json.dumps(manifesto, indent=2))
        arquivo.writestr(
            "LEIA-ME.txt",
            "Backup de dados em CSV UTF-8. Tabelas vazias têm arquivo vazio. Não inclui arquivos dos buckets, usuários, senhas nem a fila de mensagens do WhatsApp. Não é um snapshot transacional: evite alterações durante a geração. Guarde em local privado. Valores textuais são preservados literalmente para restauração; importe as colunas como texto.\n",
        )
    return saida.getvalue()
