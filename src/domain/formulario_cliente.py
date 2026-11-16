"""Leitura e validação campo a campo do formulário web de cliente."""

from datetime import date

from src.domain.entradas import formatar_telefone
from src.domain.formulario_moto import ErroDeCampos
from src.domain.valores import hoje_br
from src.domain.validadores import validar_cpf, validar_telefone


def _opcional(entrada: dict, campo: str) -> str | None:
    return " ".join(str(entrada.get(campo) or "").split()) or None


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
    nascimento = None
    if entrada.get("data_nascimento"):
        try:
            nascimento = date.fromisoformat(entrada["data_nascimento"])
            if not date(1900, 1, 1) <= nascimento <= hoje_br():
                raise ValueError
            nascimento = nascimento.isoformat()
        except ValueError:
            erros["data_nascimento"] = "Data de nascimento: informe uma data válida."
    cep = "".join(c for c in (entrada.get("cep") or "") if c.isdigit())
    if cep and len(cep) != 8:
        erros["cep"] = "CEP: informe os 8 dígitos."
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
        "nacionalidade": _opcional(entrada, "nacionalidade"), "naturalidade": _opcional(entrada, "naturalidade"),
        "estado_civil": _opcional(entrada, "estado_civil"), "profissao": _opcional(entrada, "profissao"),
        "data_nascimento": nascimento, "rg": _opcional(entrada, "rg"), "rg_orgao": _opcional(entrada, "rg_orgao"),
        "cep": f"{cep[:5]}-{cep[5:]}" if cep else None, "referencias": _opcional(entrada, "referencias"),
        "observacoes": (entrada.get("observacoes") or "").strip() or None,
    }
