# Guia de implantação na VPS (Fase 5)

Controle_Locacao como segundo aplicativo do **Coolify** na VPS KingHost (a mesma do cell-pag). O Traefik do Coolify faz o
proxy e o HTTPS; banco, Auth e Storage continuam no Supabase. Decisões: `Analise_Migracao_Frontend.md` seção 10.1.
Requisitos de segurança: `Revisao_Seguranca.md`, seção "Requisitos para o deploy".

> **Estado (20/10/2026):** o app está no ar em `https://lamotos.duckdns.org`. O proprietário confirmou as seções 1 a 7 (DNS,
> firewall e atualizações automáticas, Coolify, `FORWARDED_ALLOW_IPS` restrito ao Traefik, CI/CD, migrations e verificação
> pós-deploy) e criou o monitor UptimeRobot da seção 8. Pendente: backup do Supabase (Fase 6).

## 0. O que o repositório já traz

| Item | Onde | Observação |
|---|---|---|
| Imagem | `Dockerfile` | `python:3.12-slim`, usuário `locacao` (uid 10001), `HEALTHCHECK` em `/saude`, só `src/` e `static/` |
| Dependências | `requirements.txt` | Só produção. Testes: `requirements-dev.txt` (não entra na imagem) |
| Comando | `CMD` do Dockerfile | `uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"` |
| Ambiente | `LOCACAO_AMBIENTE=producao` na imagem | Nunca `dev` (liga `/componentes` e o espelho de sessões em arquivo) |
| CI/CD | job `deploy` em `.github/workflows/ci.yml` | Só no push para a `main`, depois do `pytest` verde (Python 3.12 e 3.14) |

## 1. DNS (DuckDNS)

1. Em duckdns.org, crie o subdomínio `SEU-SUBDOMINIO` (fica `SEU-SUBDOMINIO.duckdns.org`).
2. Aponte para o **IP público da VPS** (campo *current ip*).
3. Confira: `nslookup SEU-SUBDOMINIO.duckdns.org` deve devolver o IP da VPS.

## 2. Firewall e sistema operacional (na VPS, por SSH)

```bash
sudo ufw status verbose
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable        # confirme que a sessão SSH atual continua aberta antes de sair dela
```

- Só 22 (SSH com chave, sem senha), 80 e 443 abertas. Não abra a 8000: o app só deve ser alcançado pelo Traefik.
- Atualizações automáticas de segurança (Ubuntu):

```bash
sudo apt update && sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
systemctl status unattended-upgrades --no-pager
```

- Rotina periódica (não há verificação automática de CVE nem de imagens): `pip list --outdated` no repositório e rebuild
  mensal da imagem para pegar correções da base `python:3.12-slim`.

## 3. Medição de memória ANTES do primeiro build

A VPS tem ~3,8 GiB e já hospeda o cell-pag e a Evolution API. O `pip install` do build roda na própria VPS.

```bash
free -h
docker stats --no-stream
```

Anote os valores (referência de 05/10/2026: 2,4 GiB disponíveis; swap de 1 GiB quase intocado). Se o disponível estiver
abaixo de ~1 GiB, **não** faça o build agora.

## 4. Criar o aplicativo no Coolify

1. **Projects → (projeto) → + New → Application → Public/Private Repository (GitHub)**; escolha o repositório e a branch `main`.
2. **Build Pack: Dockerfile**; Dockerfile location `/Dockerfile`.
3. **Ports Exposes: `8000`**. Não configure *Ports Mappings* (nada publicado no host: só o Traefik alcança o contêiner).
4. **Domains:** `https://SEU-SUBDOMINIO.duckdns.org` (o Traefik emite o certificado Let's Encrypt).
5. **Auto Deploy: desligado** e **sem webhook do GitHub**. O único gatilho é o job `deploy` da CI (seção 6); com os dois
   ligados haveria deploy sem esperar o `pytest`.
6. **Health Check:** o do Dockerfile (`/saude`) basta; se o Coolify pedir, use caminho `/saude`, porta `8000`.
7. **Restart:** `unless-stopped` (padrão do Coolify). Em *Resource limits* sugere-se **memória 384 MB** para o app não
   afetar o cell-pag.

### Variáveis de ambiente (aba Environment Variables)

Marque **todas** como *Runtime only* (não entram no build) e não marque *Is Build Variable*.

| Variável | Valor | Obrigatória |
|---|---|---|
| `SUPABASE_URL` | URL do projeto Supabase **de produção** | Sim |
| `SUPABASE_ANON_KEY` | chave anon (`sb_publishable_…` ou JWT anon) de produção | Sim |
| `FORWARDED_ALLOW_IPS` | IP do Traefik (ver "Restringir o proxy confiável"). Sem ela, a imagem usa `10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` (provisório) | Sim, após o 1º deploy |

Regras: **nunca** `service_role`; **nunca** definir `LOCACAO_AMBIENTE=dev` nem `LOCACAO_SESSOES_ARQUIVO`; nada de `.env` na
VPS. O app não exige outras variáveis.

### Restringir o proxy confiável ao IP do Traefik (obrigatório após o primeiro deploy)

Decisão do proprietário (14/10/2026): o app só confia nos cabeçalhos `X-Forwarded-*` vindos do Traefik. O IP dele só existe
na VPS, por isso não vai no repositório: a imagem sobe com a faixa privada do Docker como valor **provisório** e você o
troca por um IP fixo assim que o Traefik estiver de pé (provisório = outro contêiner da mesma rede poderia forjar IP e HTTPS).

1. Na VPS, descubra o IP do Traefik na rede que ele compartilha com o app:

```bash
docker inspect coolify-proxy --format '{{range $n,$c := .NetworkSettings.Networks}}{{$n}} {{$c.IPAddress}}{{"
"}}{{end}}'
docker network inspect coolify --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"
"}}{{end}}'
```

2. No Coolify, aplicativo → Environment Variables: `FORWARDED_ALLOW_IPS` = esse IP **sem máscara** (ex.: `10.0.1.2`),
   *Runtime only*. Salve e faça **Restart** (não precisa de build).
3. Confirme pela seção 7, itens 2, 4 e 8 (HSTS presente, cookie `Secure`, IP real do cliente nos logs).
4. Se o contêiner do proxy for recriado (atualização do Coolify, reinício da VPS), o IP pode mudar. Sintoma: sem HSTS, cookie
   sem `Secure` e todos os acessos com o mesmo IP nos logs. Correção: repetir os passos 1 e 2. Para tolerar essa troca sem
   abrir para a internet, use a sub-rede da rede `coolify` (`docker network inspect coolify --format '{{(index .IPAM.Config 0).Subnet}}'`),
   que é mais ampla (inclui os outros contêineres da rede) mas ainda exclui a internet.

## 5. Primeiro build

1. Em outro terminal da VPS: `watch -n 5 free -h`.
2. No Coolify, **Deploy**. Acompanhe os logs; o status deve ficar *Running (healthy)*.
3. Depois: `free -h` e `docker stats --no-stream`. Estimativa do app: 100 a 150 MiB. Compare com a seção 3 e anote no
   plano (10.1). Se o uso total passar de ~70%, avaliar o plano de 8 GB.
4. Conferir em repouso o contêiner `coolify` (pico de CPU visto em 05/10/2026).

## 6. CI/CD: deploy só com o pytest verde

O job `deploy` (em `.github/workflows/ci.yml`) roda **só no push para a `main`** e **só se `testes-python` passar** (3.12 e
3.14). Ele chama a API do Coolify.

### No Coolify

1. **Keys & Tokens → API tokens →** crie um token com permissão de **deploy** (e leitura) e copie-o (aparece uma vez).
2. Se a API estiver desligada: **Settings → Advanced → API Access → habilitar**.
3. Copie o **UUID** do aplicativo (URL da página do aplicativo ou aba *General*).

### No GitHub

1. **Settings → Environments → New environment** chamado `producao` (opcional: *Required reviewers* para exigir aprovação
   antes de cada deploy).
2. **Settings → Secrets and variables → Actions → New repository secret** (ou segredos do environment):
   - `COOLIFY_URL`: endereço do painel, sem barra final (ex.: `https://coolify.exemplo.com`);
   - `COOLIFY_TOKEN`: o token de API;
   - `COOLIFY_APP_UUID`: o UUID do aplicativo.
3. **Settings → Branches →** regra na `main` exigindo o check `testes-python` antes de mesclar (opcional, reforça o fluxo).

### Fluxo e reversão

- Merge na `main` → CI roda → `testes-python` verde → job `deploy` pede o deploy → Coolify faz o build e troca o contêiner
  apenas se o healthcheck passar. O job só confirma que o **pedido foi aceito**; o resultado do build fica em *Deployments*.
- Se o `pytest` falhar, o job `deploy` é pulado e a versão anterior continua no ar.
- **Reverter:** Coolify → aplicativo → **Deployments** → escolha o deploy anterior bom → **Rollback/Redeploy**. Depois corrija
  na `main` (um novo push dispara novo deploy, então reverta o commit com problema com `git revert` para a próxima
  publicação não trazer o defeito de volta).
- Deploy manual de emergência: **Redeploy** no Coolify (não passa pela CI).

### Migrations do banco e deploy (regra do proprietário, 16/10/2026)

O deploy e o rollback do Coolify trocam só o contêiner; **o banco do Supabase não volta junto**. Por isso:

1. **Aplique a migration em produção ANTES de mesclar** o PR que a usa (SQL Editor do projeto de produção ou CLI).
2. Toda migration deve ser **compatível com a versão anterior do app** (adicionar coluna/função/tabela, nunca renomear ou
   remover algo que o app em produção ainda use). Mudança incompatível é feita em duas etapas: primeiro uma versão do app
   que aceita os dois formatos, depois a migration que remove o antigo.
3. Se um deploy precisar de rollback, o app anterior continua funcionando com o banco já migrado (garantido pelo item 2).
4. Registre no PR qual migration foi aplicada em produção e quando.

> **Atenção:** a migration `20260922000000_restringe_rls_ao_dono.sql` fixa o UUID do dono de **produção**
> (`is_dono()`). Nunca a aplique em um projeto cujo usuário tenha outro UUID, ou o RLS bloqueia todos os dados.

## 7. Verificação pós-deploy (com o proprietário)

1. **Saúde:** `curl -s https://SEU-SUBDOMINIO.duckdns.org/saude` → `{"status":"ok"}`.
2. **Cabeçalhos:** `curl -I https://SEU-SUBDOMINIO.duckdns.org/saude` deve mostrar `strict-transport-security: max-age=31536000`
   e `content-security-policy: default-src 'self'; …`, além de `x-frame-options: DENY` e `x-content-type-options: nosniff`.
3. **HTTP → HTTPS:** `curl -I http://SEU-SUBDOMINIO.duckdns.org/` redireciona para `https://`.
4. **Login do dono:** entre pelo navegador; em DevTools → Application → Cookies, o cookie `sessao` deve estar `Secure`,
   `HttpOnly`, `SameSite=Lax`.
5. **Portal do locatário no celular:** abra o link de acesso de um locatário de teste no celular (dados móveis, fora do Wi-Fi
   do escritório) e percorra o portal.
6. **Rotas de desenvolvimento desligadas:** `https://SEU-SUBDOMINIO.duckdns.org/componentes` deve dar **404**; no contêiner
   (`docker exec <contêiner> ls -a /app`) não deve existir `.sessoes_dev.json`.
7. **Reinício derruba a sessão (esperado):** reinicie o aplicativo no Coolify; a página seguinte deve pedir login de novo.
8. **IP real no limitador:** nos logs (`Logs` do aplicativo) as requisições devem mostrar o IP do cliente, não o do
   Traefik. Se aparecer sempre o mesmo IP privado, ajuste `FORWARDED_ALLOW_IPS` (seção 4).
9. **Memória:** repita `free -h` e `docker stats --no-stream` e anote.

## 8. Monitoramento e backups

- Rota `/saude` com monitor externo gratuito (UptimeRobot ou similar) avisando por e-mail se o site cair.
- Dados no Supabase: dump semanal criptografado no Google Drive (`.github/workflows/backup.yml`; passo a passo, teste de
  restauração e limites em `Arquivos/Backup_Supabase.md`). A VPS é ponto único de falha dos dois projetos; o backup do
  Postgres do cell-pag deve ter destino fora da VPS.
- Fuso do servidor: UTC; o app trabalha em America/Sao_Paulo.

## 9. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Build morre sem mensagem | Falta de memória no `pip install`: liberar RAM/swap ou fazer o build fora do horário de uso |
| Certificado não emitido | DNS ainda não aponta para a VPS, ou portas 80/443 fechadas |
| `502`/`Bad Gateway` | Porta exposta diferente de `8000`, ou contêiner *unhealthy* (veja os logs: faltam `SUPABASE_URL`/`SUPABASE_ANON_KEY`?) |
| Cookie sem `Secure`, sem HSTS | `FORWARDED_ALLOW_IPS` não inclui o IP do Traefik |
| Job `deploy` falha com 401/403 | Token inválido, sem permissão de deploy, ou API desligada no Coolify |
| Job `deploy` pulado | `pytest` falhou, ou o evento não foi push na `main` |
