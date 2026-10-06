"""Leitura e validação campo a campo do formulário web de cliente."""

from datetime import date

from src.domain.entradas import formatar_telefone
from src.domain.formulario_moto import ErroDeCampos
from src.domain.validadores import validar_cpf, validar_telefone


def ler_cliente(entrada: dict) -> dict:
    erros = {}
    nome = (entrada.get("nome") or "").strip()
    cpf = (entrada.get("cpf") or "").strip()
    telefone = (entrada.get("telefone") or "").strip()
    whatsapp = (entrada.get("whatsapp") or "").strip()
    if not nome:
        erros["nome"] = "Nome completo: informe o nome do cliente."
    if not validar_cpf(cpf):
        erros["cpf"] = "CPF: informe um CPF válido."
    for chave, valor, rotulo in (("telefone", telefone, "Telefone"), ("whatsapp", whatsapp, "WhatsApp")):
        if valor and not validar_telefone(valor):
            erros[chave] = f"{rotulo}: informe DDD e número válidos."
    validade = None
    if entrada.get("cnh_validade"):
        try:
            validade = date.fromisoformat(entrada["cnh_validade"]).isoformat()
        except ValueError:
            erros["cnh_validade"] = "Validade da CNH: informe uma data válida."
    status = entrada.get("status") or "ativo"
    if status not in ("ativo", "bloqueado", "inativo"):
        erros["status"] = "Status inválido."
    if erros:
        raise ErroDeCampos(erros)
    return {
        "nome": nome, "cpf": cpf, "telefone": formatar_telefone(telefone) or None,
        "whatsapp": formatar_telefone(whatsapp) or None, "email": (entrada.get("email") or "").strip() or None,
        "endereco": (entrada.get("endereco") or "").strip() or None,
        "cnh_numero": (entrada.get("cnh_numero") or "").strip() or None,
        "cnh_categoria": (entrada.get("cnh_categoria") or "").strip().upper() or None,
        "cnh_validade": validade, "status": status,
        "observacoes": (entrada.get("observacoes") or "").strip() or None,
    }
