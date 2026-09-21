"""Leituras de relatórios sujeitas ao RLS da sessão."""

from src.repositories.consultas import todos


def dados():
    return {
        t: todos(t)
        for t in (
            "motos",
            "contratos",
            "cobrancas",
            "pagamentos",
            "manutencoes",
            "documentos_moto",
            "historico_km",
        )
    }
