# Revisão de segurança do app web (Fase 4, parte D) — 09/10/2026

Escopo: o app FastAPI + HTMX (`src/web/`) antes de ser exposto na internet (seção 9 do `Analise_Migracao_Frontend.md`).
Método: leitura do código de autenticação, sessão, cabeçalhos, uploads e erros; varredura automática de todas as rotas;
busca de segredos no histórico do git. **Não** foi feito teste de intrusão, varredura de dependências nem revisão da RLS do
Supabase (continua sendo a proteção final dos dados) nem do servidor/Coolify (Fase 5).

## Resultado

| Item | Situação |
|---|---|
| Login: limite de tentativas | OK. 5 falhas por e-mail/CPF e 20 por IP em 15 min, resposta 429 com `Retry-After`; a mensagem de erro é a mesma para usuário inexistente e senha errada. |
| Cookies | OK. Sessão `httponly`, `samesite=lax`, `secure` em HTTPS, id novo a cada login (sem fixação de sessão). |
| CSRF | OK e agora **garantido por teste**: toda rota POST/PUT/PATCH/DELETE exige o token (formulário ou `X-CSRF-Token`); o login usa double submit com cookie. |
| Autorização | OK e **garantida por teste**: todas as rotas, exceto `/login` e `/saude`, exigem sessão; rotas do dono e do locatário não se misturam. |
| Cabeçalhos | OK. CSP sem script/estilo inline, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, HSTS em HTTPS, `Cache-Control: no-store` nas páginas. |
| Uploads | OK na validação (tamanho, extensão e assinatura do arquivo). **Corrigido:** o corpo da requisição era lido inteiro antes de validar; agora há limite de 1 MB para formulários e 105 MB para envio de arquivos (10 fotos de 10 MB), com resposta 413. |
| Sessão | **Corrigido:** só havia o prazo de inatividade (30 min); agora existe também a vida máxima de 12 h, mesmo com uso contínuo. |
| Erros | OK. Páginas de erro com mensagem genérica, sem detalhe técnico; falhas do Supabase são classificadas. |
| Segredos | OK. Nenhum JWT, `sb_secret` ou chave no histórico; `service_role` só em comentários; `.streamlit/secrets.toml`, `.env` e `.sessoes_dev.json` ignorados; em produção as sessões não vão a disco. |

## Requisitos para o deploy (Fase 5)

1. **Cabeçalhos do proxy.** Atrás do Traefik do Coolify, o `uvicorn` precisa de `--proxy-headers` e de
   `--forwarded-allow-ips` com o endereço (ou a rede) do proxy. Sem isso o app não percebe o HTTPS (cookie sem `Secure`, sem
   HSTS) e vê todos os acessos como vindos do IP do proxy, e as 20 falhas por IP passam a valer para **todos juntos**.
   Só use `--forwarded-allow-ips='*'` se o contêiner não puder ser alcançado sem passar pelo proxy.
2. **1 worker** (as sessões e os limitadores ficam na memória do processo).
3. Segredos como variáveis de ambiente do Coolify; `LOCACAO_AMBIENTE` **não** pode ser `dev` em produção (liga a rota
   `/componentes` e o espelho de sessões em arquivo).
4. Conferir no primeiro deploy: `curl -I` mostrando HSTS e CSP, e um login de teste com o cookie marcado `Secure`.

## Riscos aceitos e recomendações (não corrigidos)

- **Bloqueio por tentativas de login** pode ser usado contra o dono: quem souber o e-mail dele pode errar 5 vezes e travá-lo
  por 15 min. É a troca comum de proteção contra adivinhação; a alternativa é só limitar por IP. Decisão do proprietário.
- **Fotos de câmera:** os arquivos vão ao Storage como foram enviados, com os metadados EXIF (inclusive localização, se o
  celular gravar). Remover o EXIF é recomendável para as fotos do portal do locatário; depende do teste com aparelhos reais.
- **Sessões na memória:** reiniciar o servidor desloga todos (decisão da Fase 1).
- **Cookie `sessao`** sem prefixo `__Host-`: ganho pequeno, fica como melhoria futura.
- Não há verificação de dependências (CVE) nem atualização automática de imagens; incluir na rotina da VPS.
