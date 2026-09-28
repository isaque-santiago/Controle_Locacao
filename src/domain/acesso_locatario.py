"""Login do locatário por CPF + senha e regras das senhas (Fase 7).

O Supabase Auth só entende e-mail; o locatário digita o CPF e o app o converte
no e-mail interno <cpf>@portal.example.com. O domínio example.com é reservado
(ninguém o possui), então nenhum e-mail real é enviado a terceiros. O usuário e a
senha aleatória são criados pela Edge Function supabase/functions/criar-locatario,
que usa o mesmo domínio (mantenha os dois iguais).
"""

from src.domain.validadores import validar_cpf

DOMINIO_ACESSO = "portal.example.com"
TAMANHO_MINIMO_SENHA = 8


def _digitos(texto: str) -> str:
    return "".join(c for c in str(texto or "") if c.isdigit())


def email_de_acesso(cpf: str) -> str:
    """E-mail interno usado no Supabase Auth para o CPF informado."""
    digitos = _digitos(cpf)
    if not validar_cpf(digitos):
        raise ValueError("CPF inválido.")
    return f"{digitos}@{DOMINIO_ACESSO}"


def identificador_para_email(texto: str) -> str:
    """Converte o que foi digitado no login em e-mail de autenticação.

    Um CPF válido (com ou sem pontuação) vira o e-mail interno do locatário;
    qualquer outra coisa é tratada como e-mail (o login do dono)."""
    texto = str(texto or "").strip()
    if "@" not in texto and validar_cpf(_digitos(texto)):
        return email_de_acesso(texto)
    return texto


def eh_email_de_locatario(email: str) -> bool:
    return str(email or "").lower().endswith("@" + DOMINIO_ACESSO)


def validar_nova_senha(nova: str, confirmacao: str, cpf: str = "") -> str:
    """Confere a senha escolhida pelo locatário; devolve a senha ou levanta ValueError."""
    if nova != confirmacao:
        raise ValueError("As senhas não conferem.")
    if len(nova) < TAMANHO_MINIMO_SENHA:
        raise ValueError(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")
    if nova.isdigit():
        raise ValueError("A senha não pode ter só números. Misture letras e números.")
    digitos_cpf = _digitos(cpf)
    if digitos_cpf and digitos_cpf in _digitos(nova) and len(_digitos(nova)) >= 6:
        raise ValueError("A senha não pode conter o seu CPF.")
    return nova
