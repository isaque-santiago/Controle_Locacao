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
)


def obter():
    return configuracoes.obter()


def atualizar(entrada):
    return configuracoes.atualizar(validar_configuracao(entrada))


def backup():
    saida = BytesIO()
    with ZipFile(saida, "w", ZIP_DEFLATED) as arquivo:
        manifesto = {}
        for nome in TABELAS:
            linhas = todos(nome, usar_cache=False)
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
            "Backup de dados em CSV UTF-8. Tabelas vazias têm arquivo vazio. Não inclui arquivos dos buckets, usuários ou senhas. Não é um snapshot transacional: evite alterações durante a geração. Guarde em local privado. Valores textuais são preservados literalmente para restauração; importe as colunas como texto.\n",
        )
    return saida.getvalue()
