# Revisão de segurança do app web (Fase 4, parte D) — 09/10/2026

Escopo: o app FastAPI + HTMX (`src/web/`) antes de ser exposto na internet (seção 9 do `Analise_Migracao_Frontend.md`).
Método: leitura do código de autenticação, sessão, cabeçalhos, uploads e erros; varredura automática de todas as rotas;
busca de segredos no histórico do git. **Não** foi feito teste de intrusão, varredura de dependências nem revisão da RLS do
Supabase (continua sendo a proteção final dos dados) nem do servidor/Coolify (Fase 5).

## Resultado

| Item | Situação |
|---|---|
| Login: limite de tentativas | OK. 10 falhas por e-mail (subiu de 5 em 13/10/2026, decisão do proprietário) e 20 por IP em 15 min, resposta 429 com `Retry-After`; a mensagem de erro é a mesma para usuário inexistente e senha errada. |
| Conector do claude.ai (etapa 1) | **Novo em 17/11/2026, desligado sem `CONECTOR_CHAVE`.** Rota pública `/mcp` com OAuth: só o callback fixo do claude.ai, PKCE S256, consentimento só de donos, tokens sem estado cifrados (Fernet), código e renovação de uso único (enquanto o processo vive), limite de tentativas por IP, checagem de `Origin`. Nesta etapa a única ferramenta é `ping`, de leitura: nada lê nem grava o banco. **Limitações até a etapa 2:** não revoga um token isolado (trocar a chave revoga todos); um deploy esquece os códigos já usados (vida de 2 min) e os tokens de renovação já girados. |
| Caixa de pendências (etapa 2 do conector) | **Novo em 24/11/2026.** O chat só propõe: pendência gravada por RPC; só donos aprovam. O usuário de serviço do conector (`servico_conector`) não lê tabela nenhuma, só executa as RPCs de proposta e consulta, e só usa as origens do chat. Idempotência por chave, trava de 200 pendências em aberto, valores máximos por proposta (R$ 20.000 pagamento, R$ 50.000 despesa), consulta de cobranças sem o CPF inteiro. A aprovação confere de novo os avisos bloqueantes e grava pelos gatilhos de `pagamentos`. Roteiro `verificar_pendencias.sql` cobre acesso, validação, avisos, aprovação e recusa. |
| Escrita direta do conector (etapa 3) | **Novo em 24/11/2026.** O chat grava sozinho cadastros e lançamentos limpos (decisão do dono: sem fila). Tetos de gravação direta: R$ 10.000 por pagamento e R$ 5.000 por despesa; qualquer aviso (cobrança não identificada, paga, valor parcial ou acima do saldo, duplicada, sem veículo) faz a ferramenta NÃO gravar e devolver o motivo. O usuário de serviço continua sem ler tabela: só executa estas RPCs, que validam tudo no banco. Apagar e editar continuam fora do conector; o dono pode **desfazer** um lançamento automático em 7 dias. Histórico completo em `pendencias_lancamento` (quem pediu, quando, trecho do chat). **Risco que continua:** texto malicioso colado no chat pode gerar um pagamento «limpo» falso; contido por tetos, desfazer, histórico e (etapa 5) alerta no Dashboard dos lançamentos do chat. Roteiro `verificar_escrita_direta.sql`. |
| Senha padrão do locatário | RISCO ACEITO pelo dono em 16/11/2026. A senha inicial (primeiro nome + 6 últimos dígitos do CPF) é previsível por quem conhece o nome, o CPF e o e-mail `nome.sobrenome@locadora.com`; foi aceita porque o locatário esquece senhas. Mitigações: o limite de tentativas do login, a troca de senha no portal (`Alterar minha senha`) e o acesso do locatário só ler o próprio contrato por RPC. |
| Cookies | OK. Sessão `httponly`, `samesite=lax`, `secure` em HTTPS, id novo a cada login (sem fixação de sessão). |
| CSRF | OK e agora **garantido por teste**: toda rota POST/PUT/PATCH/DELETE exige o token (formulário ou `X-CSRF-Token`); o login usa double submit com cookie. |
| Autorização | OK e **garantida por teste**: todas as rotas, exceto `/login` e `/saude`, exigem sessão; rotas do dono e do locatário não se misturam. |
| Cabeçalhos | OK. CSP sem script/estilo inline, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, HSTS em HTTPS, `Cache-Control: no-store` nas páginas. |
| Uploads | OK na validação (tamanho, extensão e assinatura do arquivo). **Corrigido:** o corpo da requisição era lido inteiro antes de validar; agora há limite de 1 MB para formulários e 105 MB para envio de arquivos (10 fotos de 10 MB), com resposta 413. |
| Sessão | **Revisto em 16/11/2026 (decisão do dono):** 90 dias de inatividade e 1 ano de vida máxima (antes 30 min e 12 h), para o locatário não entrar toda hora. O cookie `lembrar` leva o token de renovação cifrado (Fernet, `SESSAO_CHAVE`) para sobreviver a deploys. **Risco aceito:** celular perdido com sessão aberta. Mitigações: "Sair de todos os dispositivos" (revoga os tokens no Supabase), cookies `HttpOnly`/`Secure`/`SameSite=Lax`, chave só no servidor. Quem roubar o cookie `lembrar` e a chave precisa dos dois; sem a chave o cookie não abre. |
| Erros | OK. Páginas de erro com mensagem genérica, sem detalhe técnico; falhas do Supabase são classificadas. |
| Segredos | OK. Nenhum JWT, `sb_secret` ou chave no histórico; `service_role` só em comentários; `.streamlit/secrets.toml`, `.env` e `.sessoes_dev.json` ignorados; em produção as sessões não vão a disco. |

## Requisitos para o deploy (Fase 5)

1. **Cabeçalhos do proxy.** Atrás do Traefik do Coolify, o `uvicorn` precisa de `--proxy-headers` e de
   `--forwarded-allow-ips` com o endereço (ou a rede) do proxy. Sem isso o app não percebe o HTTPS (cookie sem `Secure`, sem
   HSTS) e vê todos os acessos como vindos do IP do proxy, e as 20 falhas por IP passam a valer para **todos juntos**.
   Só use `--forwarded-allow-ips='*'` se o contêiner não puder ser alcançado sem passar pelo proxy.
2. **1 worker** (as sessões e os limitadores ficam na memória do processo). `SESSAO_CHAVE` definida no Coolify (sem ela, deploy derruba o login).
3. Segredos como variáveis de ambiente do Coolify; `LOCACAO_AMBIENTE` **não** pode ser `dev` em produção (liga a rota
   `/componentes` e o espelho de sessões em arquivo).
4. Conferir no primeiro deploy: `curl -I` mostrando HSTS e CSP, e um login de teste com o cookie marcado `Secure`.

## Riscos aceitos e recomendações (não corrigidos)

- **Bloqueio por tentativas de login** pode ser usado contra o dono: quem souber o e-mail dele pode errar 5 vezes e travá-lo
  por 15 min. É a troca comum de proteção contra adivinhação; a alternativa é só limitar por IP. Decisão do proprietário: manter (13/10/2026).
- **Fotos de câmera — corrigido em 13/10/2026:** vistorias, comprovantes e fotos do portal passam por `src/domain/privacidade_imagem.py`
  antes do Storage: saem GPS, marca, modelo, números de série, miniatura, XMP e comentários; ficam só a data e a orientação. JPEG e PNG
  não são recodificados (os pixels seguem idênticos); arquivo corrompido é recusado. PDF segue sem alteração (metadados do PDF não são limpos).
- **Sessões na memória:** reiniciar o servidor desloga todos (decisão da Fase 1).
- **Cookie `sessao`** sem prefixo `__Host-`: ganho pequeno, fica como melhoria futura.
- **Dependências (CVE) e imagens — tratado em 26/10/2026:** `pip-audit` na CI (push, PR e toda segunda) e Dependabot (`.github/dependabot.yml`); a imagem base é reconstruída sem cache uma vez por mês, à mão no Coolify (rotina em `Arquivos/Deploy_VPS.md`, seção 8). A reconstrução ainda não é automática.
