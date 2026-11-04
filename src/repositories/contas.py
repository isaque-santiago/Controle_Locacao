"""Contas (pessoas ou espécie) por onde o dinheiro entra e sai."""

from src.repositories.consultas import todos


def listar_ativas() -> list:
    return [c for c in todos("contas", ordem="nome") if c["ativa"]]
