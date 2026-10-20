# Backup do Supabase de produção

O plano gratuito do Supabase **não** faz backup restaurável pelo painel. Este guia monta uma cópia semanal automática,
criptografada, fora da VPS e fora do Supabase. Workflow: `.github/workflows/backup.yml`.

> **Estado:** workflow e guia prontos; os passos das seções 1 a 3 só o proprietário pode fazer e **ainda não foram
> executados**. Só considere o backup concluído depois do teste de restauração (seção 5).

## O que é salvo e o que não é

| Item | Salvo? | Observação |
|---|---|---|
| Schema `public` (15 tabelas, funções/RPCs, views, triggers, RLS) | Sim | `pg_dump --schema=public`, formato custom |
| Usuários do Auth (`auth.users`) | **Não** | Se o projeto for perdido, crie o usuário do dono de novo e ajuste o UUID em `is_dono()` (ver a atenção da migration `20260922000000` em `Deploy_VPS.md`) |
| Arquivos do Storage (fotos de vistoria, comprovantes, documentos) | **Não** | O `pg_dump` guarda só os caminhos. Fotos exigem cópia à parte (ver "Fotos" abaixo) |
| Segredos do Coolify/GitHub | Não | Guarde-os no gerenciador de senhas |

O app também tem o **backup manual** em Configurações (ZIP de 15 CSVs). Ele serve de reforço, mas não recria funções,
RLS nem triggers: para restaurar o banco use o dump.

## 1. Connection string do banco (IPv6 e pooler)

A conexão direta do Supabase (`db.<ref>.supabase.co:5432`) é só IPv6 e os runners do GitHub não têm IPv6. Use o **pooler**
em modo sessão:

1. No painel do Supabase de **produção**: **Connect → Connection string → Session pooler** (porta `5432`, host
   `aws-…pooler.supabase.com`, usuário `postgres.<ref>`).
2. Troque `[YOUR-PASSWORD]` pela senha do banco (se não a tem, **Project Settings → Database → Reset database password**;
   isso não afeta o app, que usa a anon key).
3. Esse valor completo é o segredo `SUPABASE_DB_URL`. Nunca use a `service_role` key aqui.

## 2. Senha de criptografia

Gere uma senha longa e aleatória (ex.: `openssl rand -base64 32`) e guarde-a **também** no gerenciador de senhas, fora do
GitHub. **Sem ela o backup não abre.** Ela é o segredo `BACKUP_PASSPHRASE`.

## 3. Google Drive (OAuth, uma vez)

Conta de serviço não funciona em Drive pessoal (não tem cota), então o rclone usa OAuth do seu usuário.

1. Em console.cloud.google.com crie um projeto, ative a **Google Drive API** e, em **APIs e serviços → Tela de consentimento
   OAuth**, configure o app como **Externo**. Publique-o em **"Em produção"**: em modo *Teste* o token expira em 7 dias e o
   backup para de funcionar. O escopo `drive.file` não é sensível, então não precisa de verificação do Google.
2. **Credenciais → Criar credenciais → ID do cliente OAuth → Aplicativo para computador.** Anote o *client id* e o *client
   secret*.
3. No seu computador, com o rclone instalado, rode:

```bash
rclone authorize "drive" "SEU_CLIENT_ID" "SEU_CLIENT_SECRET" --drive-scope drive.file
```

4. Entre no navegador com a conta do Drive. O terminal imprime um JSON `{"access_token": …, "refresh_token": …}`: esse JSON
   inteiro é o segredo `GDRIVE_TOKEN`.
5. O escopo `drive.file` só enxerga arquivos criados pelo próprio app. O workflow cria a pasta `backups-locacao` na raiz
   do Drive sozinho.

## 4. Segredos no GitHub

**Settings → Secrets and variables → Actions → New repository secret:**

| Segredo | Valor |
|---|---|
| `SUPABASE_DB_URL` | connection string do Session pooler (seção 1) |
| `BACKUP_PASSPHRASE` | senha da seção 2 |
| `GDRIVE_CLIENT_ID` | client id da seção 3 |
| `GDRIVE_CLIENT_SECRET` | client secret da seção 3 |
| `GDRIVE_TOKEN` | JSON impresso pelo `rclone authorize` |

Depois rode manualmente: **Actions → Backup do banco → Run workflow**. Confira no Drive o arquivo
`backups-locacao/locacao-AAAA-MM-DD.dump.gpg`. Em seguida o workflow roda sozinho aos domingos, 03:17 (Brasília). O GitHub
avisa por e-mail se uma execução falhar. Agendamentos de repositórios sem atividade por 60 dias são desativados: se isso
acontecer, reative em Actions.

Retenção: o workflow apaga do Drive os arquivos com mais de 90 dias. Uma vez por mês, baixe um e guarde em outro lugar.

## 5. Teste de restauração (obrigatório)

Backup que nunca foi restaurado não vale. Faça ao menos uma vez, **num banco descartável, nunca em produção**:

```bash
gpg --output locacao.dump --decrypt locacao-AAAA-MM-DD.dump.gpg       # pede a BACKUP_PASSPHRASE
docker run -d --name pg-teste -e POSTGRES_PASSWORD=teste -p 54329:5432 postgres:17
# o dump usa as roles anon/authenticated nas policies e GRANTs; crie-as no banco de teste:
docker exec pg-teste psql -U postgres -c "create role anon nologin; create role authenticated nologin; create role service_role nologin; create schema auth; create function auth.uid() returns uuid language sql as 'select null::uuid';"
pg_restore --no-owner --no-privileges -d "postgresql://postgres:teste@localhost:54329/postgres" locacao.dump
docker exec pg-teste psql -U postgres -c "select count(*) from public.motos; select count(*) from public.contratos;"
docker rm -f pg-teste
```

Compare as contagens com o app. Erros sobre extensões ou `auth.users` em chaves estrangeiras indicam que o banco de teste
precisa do schema `auth` completo: o caminho mais fiel é restaurar num **projeto Supabase novo e vazio** (o dump de `public`
entra por cima dos schemas padrão). Anote a data e o resultado do teste no fim deste arquivo.

## Restauração real (projeto perdido)

1. Crie um projeto Supabase novo, com cadastro público desativado, e um usuário para o dono.
2. Restaure o dump (comando da seção 5, apontando para a connection string do projeto novo).
3. Ajuste o UUID do dono em `is_dono()` para o do novo usuário (SQL único, sem alterar a migration versionada).
4. Atualize `SUPABASE_URL` e `SUPABASE_ANON_KEY` no Coolify e reinicie o app.
5. Fotos e documentos: ver abaixo.

## Fotos e documentos (Storage)

O dump não inclui os arquivos dos buckets `vistorias` e `documentos`. Opções, da mais simples à mais completa:

- Aceitar o risco enquanto o volume for pequeno e baixar os arquivos manualmente de tempos em tempos, pelo painel do
  Storage.
- Script com a API de Storage (exige a `service_role` key, que **nunca** vai para o app nem para o repositório). Só vale a
  pena se o volume de fotos crescer; decida com o proprietário antes de criar.

## Registro de testes de restauração

| Data | Quem | Resultado |
|---|---|---|
| — | — | Ainda não realizado |
