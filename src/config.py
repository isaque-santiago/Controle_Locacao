"""Leitura e validação das credenciais públicas do Supabase.

Em produção os valores vêm de variáveis de ambiente. Em desenvolvimento, na falta delas, lê-se
`.env` na raiz do projeto (ignorado pelo git; guarda só a URL e a anon key do projeto de dev).
"""

import os
from pathlib import Path

_SEGREDOS_DEV = Path(__file__).resolve().parent.parent / ".env"


def _segredo_do_arquivo(nome: str) -> str | None:
    """Valor de `nome` no `.env` de desenvolvimento (`CHAVE=valor`), ou None se não houver."""
    try:
        linhas = _SEGREDOS_DEV.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        linha = linha.removeprefix("export ").lstrip()
        chave, separador, valor = linha.partition("=")
        if not separador or chave.strip() != nome:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            return valor[1:-1]
        return valor.split(" #", 1)[0].strip()
    return None


def _ler(nome: str) -> str | None:
    return os.getenv(nome) or _segredo_do_arquivo(nome)


def get_supabase_url() -> str:
    valor = _ler("SUPABASE_URL")
    if not valor or "SEU-PROJETO" in valor:
        raise RuntimeError("SUPABASE_URL não foi configurada.")
    return valor.rstrip("/")


def get_supabase_anon_key() -> str:
    valor = _ler("SUPABASE_ANON_KEY")
    if not valor or valor == "sua-anon-key":
        raise RuntimeError("SUPABASE_ANON_KEY não foi configurada.")
    return valor


# Campos do LOCADOR no contrato em PDF; cada um vem da variável `LOCADOR_<CAMPO EM MAIÚSCULAS>`.
CAMPOS_LOCADOR = (
    "nome", "cnpj", "inscricao_estadual", "email", "telefones", "endereco",
    "representante_nome", "representante_qualificacao", "representante_rg", "representante_cpf",
    "cidade", "foro",
)


def get_locador() -> dict:
    """Dados da empresa LOCADORA para o contrato: variáveis `LOCADOR_*` (ou o `.env` de dev).

    Ficam fora do repositório (têm CNPJ e documentos pessoais do representante). Só entram os campos
    preenchidos; sem nenhum, devolve {} e o contrato sai com linhas em branco no lugar do locador.
    """
    dados = {campo: (_ler(f"LOCADOR_{campo.upper()}") or "").strip() for campo in CAMPOS_LOCADOR}
    return {campo: valor for campo, valor in dados.items() if valor}


def get_evolution() -> dict:
    """Dados da Evolution API para o envio de WhatsApp: `EVOLUTION_URL`, `EVOLUTION_APIKEY`, `EVOLUTION_INSTANCIA`
    e `EVOLUTION_VERSAO` (1 ou 2; padrão 2). Ficam só no ambiente (Coolify) ou no `.env` de dev."""
    dados = {
        "url": (_ler("EVOLUTION_URL") or "").strip().rstrip("/"),
        "apikey": (_ler("EVOLUTION_APIKEY") or "").strip(),
        "instancia": (_ler("EVOLUTION_INSTANCIA") or "").strip(),
        "versao": (_ler("EVOLUTION_VERSAO") or "2").strip(),
    }
    faltando = [nome for nome in ("url", "apikey", "instancia") if not dados[nome]]
    if faltando:
        raise RuntimeError("Evolution API não configurada: faltam " + ", ".join(f"EVOLUTION_{n.upper()}" for n in faltando) + ".")
    if dados["versao"] not in ("1", "2"):
        raise RuntimeError("EVOLUTION_VERSAO deve ser 1 ou 2.")
    dados["versao"] = int(dados["versao"])
    return dados


def get_servico_mensagens() -> tuple[str, str]:
    """E-mail e senha do usuário de serviço do envio de WhatsApp (`SERVICO_MENSAGENS_EMAIL` e `SERVICO_MENSAGENS_SENHA`)."""
    email = (_ler("SERVICO_MENSAGENS_EMAIL") or "").strip()
    senha = _ler("SERVICO_MENSAGENS_SENHA") or ""
    if not email or not senha:
        raise RuntimeError("Usuário de serviço não configurado: faltam SERVICO_MENSAGENS_EMAIL e SERVICO_MENSAGENS_SENHA.")
    return email, senha


def get_textos_whatsapp() -> dict:
    """O que entra nos textos de WhatsApp: `WHATSAPP_EMPRESA` (saudação), `WHATSAPP_CONTATO` (como falar com o dono),
    `WHATSAPP_PIX` (chave Pix estática, opcional) e `PORTAL_URL` (link do portal do locatário, opcional).

    Com o link do portal definido, os avisos de documento convidam o locatário a enviar o comprovante pelo portal
    (`comprovante_no_portal`), além de poder mandar ao dono."""
    empresa = (_ler("WHATSAPP_EMPRESA") or get_locador().get("nome") or "").strip()
    link_portal = (_ler("PORTAL_URL") or "").strip() or None
    return {
        "empresa": empresa or None,
        "contato": (_ler("WHATSAPP_CONTATO") or "").strip() or None,
        "pix": (_ler("WHATSAPP_PIX") or "").strip() or None,
        "link_portal": link_portal,
        "comprovante_no_portal": link_portal is not None,
    }
