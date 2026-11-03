"""Entrada, renovação e papel do usuário no app web (sem Streamlit).

O servidor guarda os tokens do Supabase Auth (ver src/web/sessao.py); este serviço só
conversa com o Supabase. A RLS segue como proteção final dos dados: o papel aqui serve
para decidir qual área o usuário vê.
"""

from dataclasses import dataclass
from time import time

import httpx
from supabase_auth.errors import AuthApiError

from src import db
from src.config import get_supabase_anon_key, get_supabase_url
from src.domain.acesso_locatario import identificador_para_email
from src.repositories import portal_locatario

PAPEL_DONO = "dono"
PAPEL_LOCATARIO = "locatario"

# O Supabase responde 400 (invalid_credentials, e-mail não confirmado) a credenciais
# recusadas; os demais códigos são falha do serviço, não do usuário.
_STATUS_CREDENCIAL_RECUSADA = {400, 401, 422}
_VALIDADE_PADRAO_TOKEN = 3600
_TEMPO_ALTERAR_SENHA_SEGUNDOS = 15


class SenhaNaoAlterada(ValueError):
    """O Supabase recusou a nova senha; a mensagem já está em português e pode ir para a tela."""


class CredenciaisInvalidas(Exception):
    """E-mail, CPF ou senha recusados (a mensagem não diz qual deles)."""


class SessaoSupabaseInvalida(Exception):
    """O refresh token não vale mais; é preciso entrar de novo."""


@dataclass(frozen=True)
class TokensUsuario:
    usuario_id: str
    email: str
    access_token: str
    refresh_token: str
    expira_em: float  # instante (epoch, segundos) em que o access token vence


def _tokens_da_resposta(resposta) -> TokensUsuario:
    sessao, usuario = resposta.session, resposta.user
    if not sessao or not usuario:
        raise CredenciaisInvalidas()
    expira_em = getattr(sessao, "expires_at", None) or time() + _VALIDADE_PADRAO_TOKEN
    return TokensUsuario(
        usuario_id=str(usuario.id),
        email=str(usuario.email or ""),
        access_token=sessao.access_token,
        refresh_token=sessao.refresh_token,
        expira_em=float(expira_em),
    )


class ServicoAutenticacao:
    """Fachada do Supabase Auth para o app web; trocável nos testes."""

    def entrar(self, identificador: str, senha: str) -> TokensUsuario:
        """Autentica por e-mail (dono) ou CPF (locatário) e senha."""
        try:
            resposta = db.criar_cliente_anonimo().auth.sign_in_with_password(
                {"email": identificador_para_email(identificador), "password": senha}
            )
        except AuthApiError as erro:
            if erro.status in _STATUS_CREDENCIAL_RECUSADA:
                raise CredenciaisInvalidas() from erro
            raise
        return _tokens_da_resposta(resposta)

    def renovar(self, refresh_token: str) -> TokensUsuario:
        """Troca o refresh token (de uso único) por tokens novos."""
        try:
            resposta = db.criar_cliente_anonimo().auth.refresh_session(refresh_token)
        except AuthApiError as erro:
            if erro.status in _STATUS_CREDENCIAL_RECUSADA:
                raise SessaoSupabaseInvalida() from erro
            raise
        if not resposta.session or not resposta.user:
            raise SessaoSupabaseInvalida()
        return _tokens_da_resposta(resposta)

    def cliente(self, access_token: str):
        """Cliente Supabase autenticado com o token do usuário."""
        return db.criar_cliente_autenticado(access_token)

    def papel(self, cliente) -> str | None:
        """'dono', 'locatario' ou None (sem permissão), segundo o banco."""
        with db.usar_cliente(cliente):
            return portal_locatario.meu_papel()

    def alterar_senha(self, access_token: str, nova: str) -> None:
        """Troca a senha do usuário dono do token (PUT /auth/v1/user, com a anon key e o JWT dele).

        O cliente por requisição não guarda uma sessão do GoTrue, então `auth.update_user` não serve aqui.
        A senha nunca vai para log. A sessão atual continua valendo depois da troca."""
        try:
            resposta = httpx.put(
                f"{get_supabase_url()}/auth/v1/user",
                headers={"apikey": get_supabase_anon_key(), "Authorization": f"Bearer {access_token}"},
                json={"password": nova},
                timeout=_TEMPO_ALTERAR_SENHA_SEGUNDOS,
            )
        except httpx.HTTPError as erro:
            raise SenhaNaoAlterada("Não foi possível falar com o servidor agora. Tente de novo em instantes.") from erro
        if resposta.status_code == 422:
            codigo = ""
            try:
                codigo = str(resposta.json().get("error_code") or "")
            except ValueError:
                pass
            if codigo == "same_password":
                raise SenhaNaoAlterada("Escolha uma senha diferente da atual.")
            raise SenhaNaoAlterada("Essa senha não foi aceita. Escolha outra, com letras e números.")
        if resposta.status_code in (401, 403):
            raise SessaoSupabaseInvalida()
        if resposta.status_code >= 400:
            raise SenhaNaoAlterada("Não foi possível alterar a senha agora. Tente de novo em instantes.")

    def sair(self, access_token: str) -> None:
        """Revoga esta sessão no Supabase (escopo local, com o JWT do próprio usuário).

        Falhas aqui não impedem o logout local, que já invalidou o cookie."""
        try:
            db.criar_cliente_anonimo().auth.admin.sign_out(access_token, "local")
        except Exception:
            pass
