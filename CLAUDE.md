# Regras de trabalho

- Interface, nomes de tabelas/colunas, mensagens e comentários em português (pt-BR).
- Siga o Arquivos/Projeto_Locação.md fase por fase. Não avance de fase sem cumprir os critérios de aceite.
- Ao alterar um arquivo, entregue o arquivo COMPLETO (não trechos soltos).
- Regras de negócio ficam em src/domain (funções puras) com testes em tests/.
- Páginas não acessam o banco direto: página -> service -> repository/RPC.
- Operações em mais de uma tabela devem ser RPC PL/pgSQL (transação única).
- Dinheiro sempre com Decimal / numeric(12,2); nunca float.
- Datas no fuso America/Sao_Paulo; formatos dd/mm/aaaa e R$ 1.234,56.
- Nunca commitar segredos. Nunca usar a service_role key no app.
- Ao terminar cada fase: rodar pytest, atualizar o README e fazer commit com mensagem descritiva.
- Se uma regra do plano for ambígua, pergunte antes de decidir.

# Como a IA acessa o app em execução (ambiente de preview)

O app exige login e a IA nunca digita e-mail, senha ou chaves. Para ver e testar o app
rodando, use SEMPRE o projeto Supabase de **desenvolvimento** (dados fictícios), nunca o de produção.

1. **Banco de dev:** projeto Supabase separado, com cadastro público desativado, um único
   usuário de teste e as migrations + `supabase/seed.sql` + `supabase/seed_exemplos.sql`.
   Na RLS (`is_dono()`, migration `20260922000000_restringe_rls_ao_dono.sql`) o UUID do
   dono é o do usuário de teste **desse** projeto. Não altere o UUID na migration versionada
   (é o de produção): gere um SQL único em pasta temporária, com o UUID de dev trocado, e
   o usuário o cole no SQL Editor.
2. **Segredos:** o usuário aponta `.streamlit/secrets.toml` (ignorado pelo git) para a URL e a
   anon key do projeto de dev. A IA não lê, não imprime e não commita esse arquivo. Antes de
   trocar, o usuário guarda o de produção fora do repositório (ex.: `~/backup-secrets-locacao/`).
   Nunca crie backups de segredos dentro do repositório: só `.streamlit/secrets.toml` está no
   `.gitignore`.
3. **Subir o app:** `preview_start` com a configuração `controle-locacao` de
   `.claude/launch.json` (usa `.venv\Scripts\streamlit.exe`, `autoPort: true`). Se não existir
   `.venv`: `python -m venv .venv` e `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
   O Streamlit ignora a porta atribuída pelo preview e sobe na primeira livre (ex.: 8503). Leia a
   porta real em `preview_logs` e use `navigate` para `http://localhost:<porta>`.
   Não derrube servidores de outras conversas nem processos que não foram iniciados por você.
4. **Login:** o usuário faz o login na aba do navegador embutido. Se precisar dos dados da conta
   de preview, peça ao usuário; a IA não digita credenciais. A sessão expira após 30 min
   de inatividade: peça novo login.
5. **Depois de logado:** verifique pelo `read_page`/`get_page_text`, `read_console_messages`
   e `preview_logs` (nível erro). Dados criados ou alterados nesse ambiente são fictícios.
6. **Ao encerrar:** não troque o `.streamlit/secrets.toml` de volta para produção por conta
   própria; apenas avise ao usuário qual ambiente ficou configurado.
