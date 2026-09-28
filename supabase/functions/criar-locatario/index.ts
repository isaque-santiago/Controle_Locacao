// Edge Function: gerencia o acesso (login) de um locatário ao portal — Fase 7.
//
// Por que existe: criar/alterar/excluir usuários do Supabase Auth exige a chave
// service_role, que NUNCA pode ir para o app nem para o repositório. Esta função roda
// dentro do Supabase, onde a service_role é um segredo injetado automaticamente
// (SUPABASE_SERVICE_ROLE_KEY) e nunca sai de lá.
//
// Segurança:
//   - só o DONO pode chamar: a função repassa o JWT de quem chamou ao banco e confere
//     rpc_meu_papel() = 'dono' (mesma regra da RLS, sem duplicar o UUID aqui);
//   - o e-mail interno vem do CPF gravado no cadastro do cliente (não do corpo da
//     requisição) e a senha é gerada aqui, com gerador criptográfico;
//   - a senha é devolvida uma única vez e nunca é registrada em log.
//
// Corpo (POST, JSON): { "acao": "criar" | "redefinir" | "remover", "cliente_id": "<uuid>" }
// Resposta: sempre JSON. { ok: true, email?, senha? } ou { ok: false, erro: "mensagem" }.
//
// Publicar (uma vez por projeto Supabase, dev e produção):
//   supabase functions deploy criar-locatario --project-ref <ref-do-projeto>

import { createClient } from "npm:@supabase/supabase-js@2";

// Deve ser igual a DOMINIO_ACESSO em src/domain/acesso_locatario.py.
const DOMINIO_ACESSO = "portal.example.com";
// Sem 0/O, 1/l/I e afins (a senha é lida pelo dono e digitada pelo locatário).
const ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const TAMANHO_SENHA = 10;
const ACOES = ["criar", "redefinir", "remover"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const CABECALHOS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function responder(corpo: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(corpo), { status, headers: CABECALHOS });
}

export function gerarSenha(tamanho = TAMANHO_SENHA): string {
  // Amostragem por rejeição: sem viés de módulo na escolha dos caracteres.
  const limite = 256 - (256 % ALFABETO.length);
  let senha = "";
  while (senha.length < tamanho) {
    for (const byte of crypto.getRandomValues(new Uint8Array(tamanho * 2))) {
      if (byte < limite && senha.length < tamanho) senha += ALFABETO[byte % ALFABETO.length];
    }
  }
  return senha;
}

export function emailDeAcesso(cpf: string): string {
  return `${cpf}@${DOMINIO_ACESSO}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CABECALHOS });
  if (req.method !== "POST") return responder({ ok: false, erro: "Método não permitido." }, 405);

  const autorizacao = req.headers.get("Authorization") ?? "";
  if (!autorizacao.startsWith("Bearer ")) {
    return responder({ ok: false, erro: "Sessão ausente. Entre novamente." }, 401);
  }

  let corpo: { acao?: string; cliente_id?: string };
  try {
    corpo = await req.json();
  } catch {
    return responder({ ok: false, erro: "Requisição inválida." }, 400);
  }
  const { acao, cliente_id: clienteId } = corpo;
  if (!acao || !ACOES.includes(acao) || !clienteId || !UUID.test(clienteId)) {
    return responder({ ok: false, erro: "Requisição inválida." }, 400);
  }

  const url = Deno.env.get("SUPABASE_URL")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  // Cliente "como o chamador": a RLS/RPC do banco decide o que ele pode.
  const chamador = createClient(url, anonKey, {
    global: { headers: { Authorization: autorizacao } },
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const { data: papel, error: erroPapel } = await chamador.rpc("rpc_meu_papel");
  if (erroPapel || papel !== "dono") {
    return responder({ ok: false, erro: "Somente o proprietário pode gerenciar acessos." }, 403);
  }

  const { data: cliente, error: erroCliente } = await chamador
    .from("clientes")
    .select("id, cpf, auth_user_id")
    .eq("id", clienteId)
    .maybeSingle();
  if (erroCliente || !cliente) return responder({ ok: false, erro: "Cliente não encontrado." });
  if (!/^\d{11}$/.test(cliente.cpf ?? "")) {
    return responder({ ok: false, erro: "O CPF do cliente precisa ter 11 dígitos." });
  }

  // A partir daqui usa a service_role (só existe dentro do Supabase).
  const admin = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  }).auth.admin;

  if (acao === "remover") {
    if (!cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente não tem acesso." });
    const { error } = await admin.deleteUser(cliente.auth_user_id);
    // clientes.auth_user_id é "on delete set null": o vínculo some junto com o usuário.
    if (error) return responder({ ok: false, erro: "Não foi possível remover o acesso." });
    return responder({ ok: true });
  }

  const senha = gerarSenha();

  if (acao === "redefinir") {
    if (!cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente não tem acesso." });
    const { error } = await admin.updateUserById(cliente.auth_user_id, { password: senha });
    if (error) return responder({ ok: false, erro: "Não foi possível gerar a nova senha." });
    return responder({ ok: true, email: emailDeAcesso(cliente.cpf), senha });
  }

  // acao === "criar"
  if (cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente já tem acesso." });
  const email = emailDeAcesso(cliente.cpf);

  let usuarioId: string | null = null;
  let criadoAgora = false;
  const criado = await admin.createUser({ email, password: senha, email_confirm: true });
  if (criado.data?.user) {
    usuarioId = criado.data.user.id;
    criadoAgora = true;
  } else {
    // Usuário já existe no Auth (sobra de tentativa anterior): reaproveita e redefine a senha.
    for (let pagina = 1; pagina <= 20 && !usuarioId; pagina++) {
      const { data } = await admin.listUsers({ page: pagina, perPage: 1000 });
      const usuarios = data?.users ?? [];
      usuarioId = usuarios.find((u) => u.email?.toLowerCase() === email)?.id ?? null;
      if (usuarios.length < 1000) break;
    }
    if (!usuarioId) return responder({ ok: false, erro: "Não foi possível criar o usuário." });
    const { error } = await admin.updateUserById(usuarioId, { password: senha, email_confirm: true });
    if (error) return responder({ ok: false, erro: "Não foi possível criar o usuário." });
  }

  const { error: erroVinculo } = await chamador.rpc("rpc_vincular_locatario", {
    payload: { cliente_id: clienteId },
  });
  if (erroVinculo) {
    if (criadoAgora) await admin.deleteUser(usuarioId!); // não deixa usuário sem vínculo
    return responder({ ok: false, erro: erroVinculo.message || "Não foi possível vincular o acesso." });
  }

  return responder({ ok: true, email, senha });
});
