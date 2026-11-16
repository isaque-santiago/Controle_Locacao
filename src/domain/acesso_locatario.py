"""E-mail e senha padrão do locatário (Fase 7; padronização de 16/11/2026) e regras das senhas.

E-mail: nome.sobrenome@locadora.com (homônimos: nome.sobrenome2@...). Senha inicial: primeiro nome +
últimos 6 dígitos do CPF. O usuário é criado pela Edge Function supabase/functions/criar-locatario, que
repete estas regras em TypeScript (mantenha as duas iguais; os mesmos exemplos estão nos testes).
O domínio locadora.com é só um rótulo: nenhum e-mail é enviado (o e-mail já nasce confirmado).
"""

import unicodedata

from src.domain.validadores import validar_cpf

DOMINIO_ACESSO = "locadora.com"
TAMANHO_MINIMO_SENHA = 8
DIGITOS_CPF_NA_SENHA = 6


def _digitos(texto: str) -> str:
    return "".join(c for c in str(texto or "") if c.isdigit())


def _simplificar(texto: str) -> str:
    """Minúsculas, sem acento e só letras/números (\"João\" -> \"joao\")."""
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.lower() if c.isalnum())


def _primeiro_e_ultimo(nome: str) -> tuple[str, str]:
    partes = [p for p in (_simplificar(x) for x in str(nome or "").split()) if p]
    if not partes:
        raise ValueError("Informe o nome do cliente.")
    return partes[0], (partes[-1] if len(partes) > 1 else "")


def usuario_base(nome: str) -> str:
    """Parte do e-mail antes do @: primeiro nome + ponto + último sobrenome (\"Maria da Silva\" -> \"maria.silva\")."""
    primeiro, ultimo = _primeiro_e_ultimo(nome)
    return f"{primeiro}.{ultimo}" if ultimo else primeiro


def email_padrao(nome: str, ocupados: set[str] | frozenset[str] = frozenset()) -> str:
    """E-mail de acesso <nome.sobrenome>@locadora.com; se já existir, acrescenta 2, 3, ... (homônimos).

    `ocupados`: e-mails já em uso por OUTROS usuários (minúsculos)."""
    base = usuario_base(nome)
    em_uso = {str(e).lower() for e in ocupados}
    numero = 1
    while True:
        candidato = f"{base}{'' if numero == 1 else numero}@{DOMINIO_ACESSO}"
        if candidato not in em_uso:
            return candidato
        numero += 1


def senha_padrao(nome: str, cpf: str) -> str:
    """Senha inicial: primeiro nome (minúsculo, sem acento) + últimos 6 dígitos do CPF, sem separador (\"joao123456\").

    O sistema não guarda a data de nascimento, então o CPF (obrigatório e único) a substitui."""
    digitos = _digitos(cpf)
    if not validar_cpf(digitos):
        raise ValueError("CPF inválido.")
    primeiro, _ = _primeiro_e_ultimo(nome)
    return primeiro + digitos[-DIGITOS_CPF_NA_SENHA:]


def identificador_para_email(texto: str) -> str:
    """Converte o que foi digitado no login em e-mail de autenticação.

    O locatário pode digitar só `nome.sobrenome` (o app completa com @locadora.com);
    com @, é tratado como e-mail completo (o login do dono)."""
    texto = str(texto or "").strip()
    if texto and "@" not in texto:
        return f"{texto.lower()}@{DOMINIO_ACESSO}"
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
