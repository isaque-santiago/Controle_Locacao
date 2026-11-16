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
//   - o e-mail (nome.sobrenome@locadora.com) e a senha (primeiro nome + 6 últimos dígitos do
//     CPF) saem do cadastro do cliente, não do corpo da requisição; nada disso é registrado em log.
//
// Corpo (POST, JSON): { "acao": "criar" | "redefinir" | "remover", "cliente_id": "<uuid>" }
//                  ou { "acao": "padronizar_todos" } (redefine e-mail e senha de todos os acessos).
// Resposta: sempre JSON. { ok: true, email?, senha? } ou { ok: false, erro: "mensagem" };
// padronizar_todos devolve { ok: true, total, itens: [{ cliente_id, nome, email }], falhas: [...] } (sem senhas).
//
// Publicar (uma vez por projeto Supabase, dev e produção):
//   supabase functions deploy criar-locatario --project-ref <ref-do-projeto>

import { createClient } from "npm:@supabase/supabase-js@2";

// As regras de e-mail e senha abaixo devem ser iguais às de src/domain/acesso_locatario.py.
const DOMINIO_ACESSO = "locadora.com";
const DIGITOS_CPF_NA_SENHA = 6;
const ACOES = ["criar", "redefinir", "remover", "padronizar_todos"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const CABECALHOS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function responder(corpo: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(corpo), { status, headers: CABECALHOS });
}

function simplificar(texto: string): string {
  // Minúsculas, sem acento, só letras e números ("João" -> "joao").
  return texto.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function primeiroEUltimo(nome: string): [string, string] {
  const partes = (nome ?? "").split(/\s+/).map(simplificar).filter((p) => p.length > 0);
  if (partes.length === 0) throw new Error("nome vazio");
  return [partes[0], partes.length > 1 ? partes[partes.length - 1] : ""];
}

export function usuarioBase(nome: string): string {
  const [primeiro, ultimo] = primeiroEUltimo(nome);
  return ultimo ? `${primeiro}.${ultimo}` : primeiro;
}

// `ocupados`: e-mails (minúsculos) de OUTROS usuários. Homônimos ganham 2, 3, ...
export function emailPadrao(nome: string, ocupados: Set<string>): string {
  const base = usuarioBase(nome);
  for (let n = 1; ; n++) {
    const candidato = `${base}${n === 1 ? "" : n}@${DOMINIO_ACESSO}`;
    if (!ocupados.has(candidato)) return candidato;
  }
}

export function senhaPadrao(nome: string, cpf: string): string {
  return primeiroEUltimo(nome)[0] + cpf.slice(-DIGITOS_CPF_NA_SENHA);
}

type Usuario = { id: string; email?: string };

async function listarUsuarios(admin: { listUsers: (p: { page: number; perPage: number }) => Promise<any> }): Promise<Usuario[]> {
  const todos: Usuario[] = [];
  for (let pagina = 1; pagina <= 50; pagina++) {
    const { data } = await admin.listUsers({ page: pagina, perPage: 1000 });
    const usuarios: Usuario[] = data?.users ?? [];
    todos.push(...usuarios);
    if (usuarios.length < 1000) break;
  }
  return todos;
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
  const todos = acao === "padronizar_todos";
  if (!acao || !ACOES.includes(acao) || (!todos && (!clienteId || !UUID.test(clienteId)))) {
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

  // A partir daqui usa a service_role (só existe dentro do Supabase).
  const admin = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  }).auth.admin;

  if (todos) return await padronizarTodos(chamador, admin);

  const { data: cliente, error: erroCliente } = await chamador
    .from("clientes")
    .select("id, nome, cpf, auth_user_id")
    .eq("id", clienteId)
    .maybeSingle();
  if (erroCliente || !cliente) return responder({ ok: false, erro: "Cliente não encontrado." });
  if (!/^\d{11}$/.test(cliente.cpf ?? "")) {
    return responder({ ok: false, erro: "O CPF do cliente precisa ter 11 dígitos." });
  }
  try {
    usuarioBase(cliente.nome);
  } catch {
    return responder({ ok: false, erro: "O cliente precisa ter nome para gerar o acesso." });
  }

  if (acao === "remover") {
    if (!cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente não tem acesso." });
    const { error } = await admin.deleteUser(cliente.auth_user_id);
    // clientes.auth_user_id é "on delete set null": o vínculo some junto com o usuário.
    if (error) return responder({ ok: false, erro: "Não foi possível remover o acesso." });
    return responder({ ok: true });
  }

  const senha = senhaPadrao(cliente.nome, cliente.cpf);

  if (acao === "redefinir") {
    if (!cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente não tem acesso." });
    const usuarios = await listarUsuarios(admin);
    const resultado = await padronizarUsuario(admin, usuarios, cliente);
    if (!resultado) return responder({ ok: false, erro: "Não foi possível gerar a nova senha." });
    return responder({ ok: true, email: resultado, senha });
  }

  // acao === "criar"
  if (cliente.auth_user_id) return responder({ ok: false, erro: "Este cliente já tem acesso." });
  const usuarios = await listarUsuarios(admin);
  const email = emailPadrao(cliente.nome, emailsDe(usuarios));

  const criado = await admin.createUser({ email, password: senha, email_confirm: true });
  const usuarioId = criado.data?.user?.id;
  if (!usuarioId) return responder({ ok: false, erro: "Não foi possível criar o usuário." });

  const { error: erroVinculo } = await chamador.rpc("rpc_vincular_locatario", {
    payload: { cliente_id: clienteId, email },
  });
  if (erroVinculo) {
    await admin.deleteUser(usuarioId); // não deixa usuário sem vínculo
    return responder({ ok: false, erro: erroVinculo.message || "Não foi possível vincular o acesso." });
  }

  return responder({ ok: true, email, senha });
});

function emailsDe(usuarios: Usuario[], exceto?: string): Set<string> {
  return new Set(usuarios.filter((u) => u.id !== exceto && u.email).map((u) => u.email!.toLowerCase()));
}

// Põe o usuário do cliente no padrão: mantém o e-mail se já é @locadora.com; senão troca pelo nome.sobrenome.
// Devolve o e-mail final (e atualiza `usuarios`) ou null se o Auth recusou.
async function padronizarUsuario(
  admin: any,
  usuarios: Usuario[],
  cliente: { nome: string; cpf: string; auth_user_id: string },
): Promise<string | null> {
  const atual = usuarios.find((u) => u.id === cliente.auth_user_id);
  let email = (atual?.email ?? "").toLowerCase();
  if (!email.endsWith("@" + DOMINIO_ACESSO)) {
    email = emailPadrao(cliente.nome, emailsDe(usuarios, cliente.auth_user_id));
  }
  const { error } = await admin.updateUserById(cliente.auth_user_id, {
    email,
    password: senhaPadrao(cliente.nome, cliente.cpf),
    email_confirm: true,
  });
  if (error) return null;
  if (atual) atual.email = email;
  return email;
}

// Redefine e-mail e senha de todos os acessos existentes, na ordem do cadastro (homônimos: o mais antigo fica sem sufixo).
async function padronizarTodos(chamador: any, admin: any): Promise<Response> {
  const { data: clientes, error } = await chamador
    .from("clientes")
    .select("id, nome, cpf, auth_user_id")
    .not("auth_user_id", "is", null)
    .order("criado_em", { ascending: true })
    .order("id", { ascending: true });
  if (error) return responder({ ok: false, erro: "Não foi possível ler os clientes." });

  const usuarios = await listarUsuarios(admin);
  const itens: { cliente_id: string; nome: string; email: string }[] = [];
  const falhas: { cliente_id: string; nome: string; motivo: string }[] = [];
  for (const c of clientes ?? []) {
    if (!/^\d{11}$/.test(c.cpf ?? "")) {
      falhas.push({ cliente_id: c.id, nome: c.nome, motivo: "CPF sem 11 dígitos" });
      continue;
    }
    try {
      usuarioBase(c.nome);
    } catch {
      falhas.push({ cliente_id: c.id, nome: c.nome ?? "", motivo: "cliente sem nome" });
      continue;
    }
    const email = await padronizarUsuario(admin, usuarios, c);
    if (email) itens.push({ cliente_id: c.id, nome: c.nome, email });
    else falhas.push({ cliente_id: c.id, nome: c.nome, motivo: "o Auth recusou a alteração" });
  }
  return responder({ ok: true, total: itens.length, itens, falhas });
}
