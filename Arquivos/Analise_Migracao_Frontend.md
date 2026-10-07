# Análise e proposta: migração da camada de interface (Streamlit → FastAPI + HTMX)

> **Status: APROVADA pelo proprietário em 05/10/2026 (decisões na seção 10). Fase atual: 3 (demais páginas,
> uma por vez), INICIADA em 06/10/2026. Clientes CONCLUÍDA em 07/10/2026 (lista, cadastro, edição e quatro abas,
> incluindo Portal). Contratos CONCLUÍDA em 07/10/2026 (lista, ficha, assistente em 4 etapas e encerramento).
> Próxima página: Cobranças. Depois da Fase 3, resolver a falta de recarga automática do app web.**
> Decisões da Fase 1 (06/10/2026): sessão **na memória do servidor** (reiniciar ou fazer deploy desloga todos; rodar com
> **1 único worker**), sem "lembrar de mim", CSS do Tailwind compilado e **versionado** em `static/css/app.css`
> (Tailwind CLI standalone em `tools/`, fora do git), htmx em `static/js/htmx.min.js`. Detalhes no README.
> O layout do protótipo (`prototipo/`) foi aprovado. A mudança de escopo foi registrada no
> `Plano_Melhorias_UI_UX.md` (seção 10) e no `Projeto_Locação.md` (seção 15).
> **Hospedagem decidida** (VPS KingHost **compartilhada com o projeto cell-pag**, gerenciada pelo Coolify; domínio gratuito
> DuckDNS; deploy automático; seção 10.1). A contratação da VPS fica para mais perto do primeiro deploy e não bloqueia a Fase 1.
>
> **Ao iniciar uma sessão nova:** leia este arquivo e o `CLAUDE.md`, confira o `git log` para saber o que já
> foi feito e atualize a linha "Fase atual" acima ao concluir cada fase.

## 1. Contexto e motivação

O proprietário relata que a interface está "estranha" e que as tentativas de melhoria não surtem efeito. As
respostas dadas na discussão:

- O incômodo principal é de **layout e navegação**. O visual (cores, tipografia) é tranquilo de customizar e a
  lentidão é tolerável.
- A **responsividade** deve ser boa em desktop e em celular. O perfil de uso real não é conhecido com certeza
  (quem opera o sistema não é o proprietário).
- Preferência por **manter Python** para evitar reescrever muitos arquivos, mas aceita-se outra tecnologia se
  for **tudo planejado antes**.
- Não há tela de referência a imitar por ora.

## 2. Estado atual do sistema (verificado em 05/10/2026)

- Branch `main`, árvore limpa. A **Etapa 9** (homologação) do plano de UI/UX foi mesclada (PR #61).
- Stack: Python, Streamlit 1.64, Supabase (Postgres + Auth + Storage, RLS restrita ao dono, RPCs PL/pgSQL),
  Plotly, pytest, Playwright (E2E), CI no GitHub Actions.
- Telas: Login, Dashboard, Motos, Clientes, Contratos, Cobranças, Manutenção, Documentos, Vistorias,
  Relatórios, Configurações e Portal do Locatário (11 arquivos em `pages/`, todos apenas chamam `src/ui/*`).
- Tamanho (linhas de Python): `src/ui` ≈ 7.300 (22 arquivos), `src/domain` 21 arquivos, `src/services` 13,
  `src/repositories` 19, 44 arquivos de teste em `tests/` (46 deles tocam UI ou Streamlit de alguma forma),
  suíte E2E em `e2e/`.
- CSS: `src/ui/estilos.css` tem 1.044 linhas, das quais **215 referenciam internos do Streamlit**
  (`data-testid`, `stMain`, `nth-child`, classes `.st-*`). Mais `estilos_escuro.css` (123 linhas).
- O plano de UI/UX tem 9 etapas. Pendências abertas da Etapa 9: gravar os 10 fluxos no banco de dev,
  testar em aparelhos reais (Android e, se houver, iPhone/iPad) e a rodada autenticada
  (`Roteiro_Homologacao_Manual.md`). Pendência técnica herdada: **CLS ≈ 0,4 no desktop e ≈ 0,95 no
  celular**, causada pela reconstrução do DOM do Streamlit.

## 3. Diagnóstico: por que o Streamlit limita este projeto

Evidências no próprio repositório:

1. **O CSS luta contra o framework.** 215 linhas de CSS dependem do DOM interno do Streamlit, que muda entre
   versões. Seletores como `nth-child` foram um dos alvos do plano de UI/UX justamente por serem frágeis.
2. **Alguns controles são intocáveis.** A barra de ferramentas do `st.data_editor` (22 × 22 px) não pôde ser
   corrigida e ficou como pendência; botões nativos de menu e sidebar precisaram de sobrescritas para chegar a
   44 px.
3. **Navegação fixa.** O menu é a sidebar do Streamlit (`st.navigation`). Não há como ter barra inferior no
   celular, breadcrumbs, abas persistentes por rota, nem URL por registro (ex.: `/motos/123`). O `app.py`
   precisa de contornos (menu oculto antes do login, registro de todas as páginas, `shell_pronto`).
4. **Modelo de reexecução.** Cada interação reexecuta o script e reconstrói o DOM, origem da CLS alta e de
   "piscadas" que o próprio código documenta ter tentado mitigar.
5. **Sessão por cookie via componente.** `src/db.py` e `src/auth.py` usam `streamlit-cookies-controller`
   (cada `.set()` monta um iframe e provoca um rerun extra). Os comentários descrevem várias armadilhas:
   `st.rerun` descarta o componente antes do navegador gravar o cookie; o F5 devolve ao login; token de
   atualização de uso único precisa ser sincronizado. Num servidor web comum, isso é um cookie `httpOnly`
   emitido pelo servidor.
6. **Tema escuro por remapeamento de cores inline** (`estilos_escuro.css` remapeia `color: rgb(...)`
   normalizado pelo navegador) em vez de variáveis CSS usadas em todo o markup.

Conclusão: ajustes de tema ajudam até certo ponto, mas layout, navegação e responsividade reais exigem
controlar o HTML. Isso não é falha de implementação; é limite do paradigma.

## 4. Acoplamento: o que prende o sistema ao Streamlit

A arquitetura em camadas (página → serviço → repositório/RPC) está bem separada, o que torna a migração
viável. Mapeamento do que importa `streamlit` **fora** de `src/ui` e `pages/`:

| Arquivo | Uso de Streamlit | Impacto na migração |
|---|---|---|
| `src/domain/*` (21 arquivos) | Nenhum | Reaproveitado sem alteração |
| `src/auth.py` | `session_state`, sidebar, login, toggle de tema | Reescrito (sessão no servidor) |
| `src/db.py` | `session_state` para o cliente Supabase, cookies, `st.context` | Reescrito (cliente por requisição + cookie `httpOnly`) |
| `src/config.py` | segredos (`st.secrets`) | Trocar por variáveis de ambiente |
| `src/repositories/consultas.py` | `@st.cache_data` e `session_state["usuario"]` | Trocar o cache por um cache próprio com chave por usuário |
| `src/services/cobrancas.py` | `session_state` (controle de geração) | Ajuste pequeno |
| `src/services/portal_locatario.py` | importa `streamlit` | Ajuste pequeno |
| demais `services/` e `repositories/` | Nenhum | Reaproveitados |

Ou seja: **o domínio e quase toda a camada de dados são reaproveitáveis**; o trabalho real está em `src/ui`
(≈ 7.300 linhas), em `auth.py`/`db.py` e no CSS.

## 5. Alternativas avaliadas

| Opção | Controle de layout | Reaproveita Python | Esforço | Observação |
|---|---|---|---|---|
| **A. FastAPI + Jinja2 + HTMX + CSS próprio** | Total | Sim, direto | Médio | **Recomendada** |
| B. React/Next.js + Supabase JS | Total, mais interativo | Não (portar regras para TS ou mover para RPC) | Alto | Só se for necessário PWA ou interatividade pesada |
| C. NiceGUI / Reflex / Flet | Alto, ainda dentro de um framework opinativo | Sim | Médio | Troca um framework opinativo por outro |
| D. Continuar no Streamlit (componentes customizados) | Parcial | Sim | Baixo | Os limites das seções 3 e 4 permanecem |

## 6. Recomendação: opção A

**FastAPI + Jinja2 + HTMX + CSS próprio** (Tailwind é opcional), mantendo Python.

Motivos:

- Resolve o incômodo declarado (layout e navegação) na origem: o HTML é nosso.
- Mantém Python, `Decimal`, o `pytest`, as RPCs e a RLS.
- HTMX atualiza só o trecho da página que muda (listas, filtros, paginação, diálogos), sem JavaScript
  próprio em volume e sem reconstruir a página inteira, o que elimina a CLS estrutural.
- Mantém a arquitetura página → serviço → repositório (a "página" passa a ser uma rota + template).
- Manutenção viável por uma pessoa: sem etapa de build de JavaScript.

### Arquitetura-alvo (resumo)

```
Navegador ──HTMX/HTML──▶ FastAPI (rotas + templates Jinja2)
                              │  (rota = "página": monta o contexto e renderiza)
                              ▼
                      src/services   ──▶  src/domain (regras puras, inalteradas)
                              ▼
                      src/repositories ──▶ Supabase (RLS + RPCs)
```

Decisões de arquitetura a registrar quando a migração for aprovada:

- **Autenticação:** login no Supabase Auth feito no servidor; sessão em cookie `httpOnly`, `Secure`,
  `SameSite=Lax`; expiração por inatividade de 30 min mantida; refresh token tratado no servidor.
- **Cliente Supabase por requisição**, autenticado com o token do usuário (para a RLS valer) e com a **anon key**.
  Nunca usar a `service_role` no app (regra do `CLAUDE.md`).
- **CSRF:** token em formulários (cookie `SameSite=Lax` sozinho não basta para POST de formulário).
- **Papéis:** dono e locatário continuam separados; o locatário só acessa o portal. O controle de acesso do
  servidor é um complemento; quem protege os dados continua sendo a RLS/RPC.
- **Gráficos:** Plotly gera o HTML/JSON da figura no servidor; o navegador carrega a biblioteca JS.
- **Tabelas e formulários:** componentes Jinja2 reutilizáveis (macros) para cartão, tabela responsiva
  (vira cartões no celular), formulário, diálogo, abas, avisos, paginação.
- **Layout:** sidebar fixa e colapsável no desktop; barra de navegação inferior no celular; cabeçalho de
  página padronizado; URL por página e por registro.

## 7. Plano proposto por fases

Cada fase só termina com `pytest` verde, README atualizado e commit descritivo (regras do `CLAUDE.md`).

**Fase 0 — Decisão e desenho (sem código de produção)**
1. Decidir (seção 9) e registrar a mudança no `Projeto_Locação.md` e no `Plano_Melhorias_UI_UX.md`.
2. Produzir um **protótipo estático em HTML** do shell: sidebar no desktop, barra inferior no celular,
   cabeçalho, padrão de lista/detalhe e de formulário, em claro e escuro, nas larguras 320 a 1440.
3. Contratar a VPS e configurar o domínio gratuito; definir variáveis de ambiente (seção 10.1). Só o primeiro deploy depende disso.
   *Aceite:* o proprietário aprova o protótipo.

**Fase 1 — Fundação**
App FastAPI, templates base, login/logout/sessão (incluindo CPF no portal), proteção por papel, CSRF,
tratamento de erros (`src/domain/erros.py` reaproveitado) e biblioteca de componentes.
*Aceite:* login e logout funcionam, sessão expira em 30 min, F5 mantém a sessão, testes de auth passando.

**Fase 2 — Páginas piloto: Dashboard e Motos**
Valida os padrões de lista, filtro, paginação, ficha e formulário.
*Aceite:* sem overflow horizontal de 320 a 1440 px; alvos ≥ 44 px; teclado completo; paridade funcional.

**Conclusão (06/10/2026):** Dashboard e Motos foram validados no banco de desenvolvimento, lado a lado com o
Streamlit. Os dois mostraram 31 motos (19 alugadas, 4 disponíveis, 4 em manutenção e 4 inativas), 49 itens no
cartão Hoje (48 atrasados e 1 vencendo no dia), os mesmos indicadores e alertas, e as mesmas 10 linhas na
primeira página da lista. Cadastro e validação por campo, edição, atualização normal e histórica de km,
inativação/reativação e regularização de documento foram conferidos de ponta a ponta. A ficha, suas seis abas,
o diálogo em 390 px, a navegação por teclado, o fechamento com Esc e a devolução de foco também foram
verificados. A suíte terminou com 830 testes passando.

**Fase 3 — Demais páginas, uma por vez**
Clientes → Contratos (assistente em 4 etapas) → Cobranças → Manutenção → Vistorias (com fotos) →
Documentos → Relatórios (exportação) → Configurações (backup) → Portal do Locatário.
O Streamlit continua funcionando em paralelo, no mesmo banco, até a última página migrar.

**Andamento: Clientes concluída (07/10/2026).** O app novo possui lista com filtro por status, busca por
nome/CPF, paginação e resposta parcial HTMX; ficha com abas Resumo (com cartão de contrato ativo), Contratos,
Pagamentos (paginados de 10 em 10, URL `?aba=pagamentos&pagina=N`) e Portal; cadastro e edição em diálogo, com
validação por campo, CSRF, mensagens e dados preservados após erro. A rota usa as fronteiras `dados_clientes.py` e
`acoes_clientes.py`, sem acesso direto ao banco, e tem testes web com serviços falsos (846 testes na suíte).

Conferência lado a lado em 06/10/2026 no banco de desenvolvimento: 30 clientes (24 ativos, 4 bloqueados e 2
inativos), busca por CPF, paginação, dados pessoais, contrato, valores financeiros, cadastro e edição bateram com o
Streamlit; diálogo em 320 px, Esc e foco ok. Em 07/10/2026, no app novo: cartão de contrato ativo conferido; aba
Portal exercitada de ponta a ponta no cliente fictício (criar acesso, fechar o aviso, gerar nova senha, remover
acesso); paginação testada num cliente com 183 cobranças (avanço, Voltar do navegador, última página, teclado);
sem rolagem horizontal e sem alvo menor que 44 px em 320, 390 e 1440 px; setas percorrem as abas. Decisão do
proprietário: aceite **sem** repetir a comparação lado a lado dos itens novos (Resumo, Portal, Pagamentos
paginados).

Correções feitas no fechamento: o repositório do portal lia o JWT do dono da sessão do Streamlit (nulo no app
novo) e agora usa o do cabeçalho do cliente por requisição; o foco voltava ao topo após a paginação por
`outerHTML` e agora volta ao botão equivalente. **Não verificado:** fotos das trocas de óleo (o banco de dev não
tem trocas; só testes automatizados), leitor de tela e aparelhos reais (ficam para a Fase 4).

**Andamento: Contratos concluída (07/10/2026).** Entregue em três partes, cada uma com testes e commit:
(A) lista e ficha somente leitura; (B) assistente de novo contrato em quatro etapas; (C) encerramento em diálogo.

- **Lista e ficha:** abre nos contratos ativos; chips de situação com contagem, busca por cliente ou placa, paginação
  e resposta parcial HTMX. Ficha com faixa de dados (valor, caução, km inicial, prazo, próxima cobrança) e abas
  Cobranças (com "pago em"), Vistorias (entrega e devolução) e Manutenções (só as da vigência). O cartão de contrato
  ativo da ficha do cliente abre esta ficha.
- **Assistente:** Cliente → Moto → Condições → Confirmar, uma URL por etapa, sem depender de JavaScript. Decisão de
  implementação: o rascunho fica **na sessão do servidor** (`sessao.rascunho_contrato`), inclusive texto inválido,
  para voltar e revisar sem perder o progresso; some ao concluir, cancelar ou iniciar outro contrato. Regras mantidas
  do Streamlit: só cliente ativo aluga, só moto disponível aparece, prazo indeterminado é o padrão, o km da vistoria
  não pode ser menor que o da moto e vira o km inicial, a criação usa a RPC única. A vistoria de entrega não tem fotos
  (como no Streamlit; elas entram na página Vistorias).
- **Encerramento:** diálogo com data, vistoria de devolução, danos descontados da caução (descrição obrigatória) e
  prévia de impacto recalculada pelo servidor; o aviso final diz quanto devolver e o excedente cobrado.
- **Conferência no banco de desenvolvimento (07/10/2026):** contrato de teste criado pelo assistente (Carlos Eduardo
  Lima, moto E2E-0A04): 5 parcelas semanais geradas, vistoria de entrega registrada, moto passou a Alugada; encerrado
  pelo diálogo: parcelas futuras canceladas, a do dia mantida, vistoria de devolução registrada, moto Disponível de
  novo. Validação por campo, prévia ao vivo (danos acima da caução geram aviso de cobrança de dano), foco no campo com
  erro e Esc conferidos. Sem rolagem horizontal e sem alvo menor que 44 px em 320 px (lista, ficha, etapas 1 a 4 e
  diálogo) e em 1440 px (etapa 3 com resumo ao lado).
- **Correções do caminho:** tipo da cobrança com acento (Locação, Caução); links "Alterar cliente/moto" de 19 px
  viraram botões de 44 px; foco no primeiro campo inválido em páginas recarregadas; macro `caixa` com erro; token do
  dono no repositório do portal (Clientes).
- **Não verificado:** comparação lado a lado com o Streamlit (não feita nesta página), contrato com caução recebida
  encerrado de verdade (só a prévia foi vista, no contrato do João da Silva; o cálculo tem testes), leitor de
  tela e aparelhos reais (Fase 4). Enter num campo de texto da etapa 4 cria o contrato, como nos formulários do
  Streamlit.

**Próxima: Cobranças**, seguida de Manutenção, Vistorias (com fotos), Documentos, Relatórios, Configurações e
Portal do Locatário.

**Fase 4 — E2E, homologação e desligamento**
Adaptar a suíte Playwright (`e2e/`), rodar axe, teclado, zoom/reflow e regressão visual, concluir os 10 fluxos de
homologação e os aparelhos reais. **Esta fase absorve a Etapa 9 do plano de UI/UX** (decisão 2, opção b). Só então remover o Streamlit, `tema.py`, `acessibilidade.py`, o CSS
dependente do DOM do Streamlit e as dependências.

## 8. Reaproveitamento, descarte e impacto nos documentos

| Item | Destino |
|---|---|
| `src/domain/*`, `src/repositories/*`, `src/services/*` (salvo ajustes da seção 4) | Reaproveitados |
| `supabase/` (migrations, RPCs, seeds) | Inalterados |
| Tokens de cor, fontes locais (`static/fontes`, `fontes.css`), identidade visual, `Design_UI.md` | Reaproveitados como base do novo CSS |
| Testes de `tests/` sobre domínio e serviços | Reaproveitados |
| Testes de `tests/` sobre UI (`*_ui.py`) | Reescritos para as novas rotas/templates |
| `src/ui/*` (≈ 7.300 linhas), `pages/`, `app.py`, `auth.py`, `db.py` | Reescritos |
| Suíte `e2e/` | Seletores e fluxos adaptados |
| `estilos.css` (215 linhas dependentes do Streamlit), `tema.py`, `acessibilidade.py` | Descartados |

**Conflitos com o plano vigente** (`Plano_Melhorias_UI_UX.md`, seção 10 "Fora do escopo"):

- "Reescrita do sistema em outro framework frontend": esta proposta é exatamente isso.
- "Mudança da arquitetura página → serviço → repositório": mantida em essência, mas "página" deixa de ser um
  script Streamlit e vira rota + template. Convém registrar isso explicitamente.

Resolução: os dois itens foram marcados como substituídos no `Plano_Melhorias_UI_UX.md` (decisão 1). A Etapa 9
foi absorvida pela Fase 4 da migração (decisão 2).

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Dois sistemas em paralelo por um período | Migrar página a página, com lista de "dono" de cada tela; congelar alterações de UI no Streamlit durante a Fase 3 |
| Regressão funcional em fluxos transacionais (contrato, entrega/devolução) | Esses fluxos já são RPCs com testes; manter a lógica nas RPCs e testar cada rota contra o banco de desenvolvimento |
| Falha de segurança na sessão própria (cookies, CSRF) | Usar cookie `httpOnly`/`Secure`/`SameSite`, CSRF, revisão de segurança antes de desligar o Streamlit |
| App passa a ficar exposto na internet (painel do dono e portal do locatário no mesmo servidor) | HTTPS obrigatório, cookies `Secure`/`httpOnly`, limite de tentativas de login, atualizações do servidor e backups (seção 10.1) |
| Esforço maior que o estimado | O piloto da Fase 2 serve de ponto de decisão: se o padrão não funcionar, parar com custo baixo |
| Trabalho do plano de UI/UX perdido | Tokens, fontes, Design_UI e testes de domínio são reaproveitados; só o que dependia do DOM do Streamlit é descartado |

## 10. Decisões (respondidas pelo proprietário em 05/10/2026)

| # | Decisão | Resposta |
|---|---|---|
| 1 | Mudança de escopo | **Substituir o Streamlit por inteiro.** Nenhuma tela fica no Streamlit ao final. |
| 2 | Etapa 9 do plano de UI/UX | **Opção (b):** não terminar a Etapa 9 no Streamlit. A homologação (10 fluxos, aparelhos reais, rodada autenticada) é refeita no app novo, na Fase 4, reaproveitando `Roteiro_Homologacao_Manual.md`, os fluxos e a matriz de larguras. |
| 3 | Hospedagem | **VPS com acesso público** (KingHost, plano pequeno e barato), porque os locatários acessam o portal pelo celular (hoje o app só roda localmente). Domínio gratuito, deploy automático e administração: ver 10.1. |
| 4 | Perfil de uso | **Desktop e celular, ambos.** Mantém as três faixas do protótipo. |
| 5 | Portal do Locatário | **No mesmo app**, com login por CPF e papel separado. |
| 6 | Estilo | **Tailwind**, sobre os tokens existentes (`Design_UI.md`). Ver nota abaixo. |

Nota sobre o Tailwind: o protótipo foi escrito em CSS próprio, com tokens como variáveis CSS. Na
implementação, os tokens (cores, espaçamento, raio, fontes, modo escuro) viram a configuração do Tailwind,
sem mudar a identidade visual. A forma de gerar o CSS (CLI independente do Tailwind, sem Node, ou build com Node)
é uma decisão da Fase 0/1; preferir o CLI independente para manter a stack em Python.

### 10.1 Hospedagem em VPS: proposta e pontos em aberto

**Decidido:** o app roda em uma VPS acessível pela internet, com HTTPS, para o painel do dono e para o portal
dos locatários (celular). O Supabase continua sendo o banco, a autenticação e o armazenamento.

**Atualização (05/10/2026): VPS compartilhada com o cell-pag.** O projeto cell-pag (Django, `C:\cell-pag`) já tem guia de
hospedagem na VPS da KingHost (`docs/deploy/DEPLOY-VPS.md` daquele repositório): **Coolify** gerenciando os contêineres, na
mesma máquina da Evolution API, com Postgres próprio na VPS. O Controle_Locacao entra na **mesma VPS e no mesmo Coolify**
como um segundo aplicativo. Consequência: o **Caddy deixa de fazer parte do plano**, porque o Coolify já ocupa as portas
80/443 com o proxy dele (Traefik), que também emite e renova o HTTPS (Let's Encrypt) automaticamente.

**Arquitetura (recomendação, ainda não confirmada na prática):**

```
Internet ──HTTPS──▶ Traefik (proxy do Coolify, certificado automático Let's Encrypt)
                       ├──▶ cell-pag (Django/gunicorn)  ──▶ Postgres na VPS
                       ├──▶ Evolution API
                       └──▶ Controle_Locacao (uvicorn/FastAPI, contêiner) ──▶ Supabase (nuvem)
```

- **Sistema:** Ubuntu LTS, firewall liberando só 22 (SSH com chave, sem senha), 80 e 443.
- **Proxy e HTTPS:** do Coolify (Traefik). O subdomínio DuckDNS é apontado para o IP da VPS e cadastrado em **Domains**
  no aplicativo do Coolify.
- **App em contêiner Docker** (`Dockerfile` do Controle_Locacao, feito na fase de deploy, no mesmo molde do cell-pag:
  imagem `python:3.12-slim`, usuário sem privilégios, reinício automático, rota `/saude` como healthcheck).
- **Segredos** (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, chave de assinatura da sessão) em variáveis de ambiente do Coolify,
  marcadas como *Runtime only*, nunca no repositório nem na imagem. A `service_role` continua proibida no app.
- **Deploy:** o Coolify faz o deploy a cada push na `main` (webhook do GitHub). O `pytest` roda no GitHub Actions; o deploy
  só deve sair com a CI verde (configurar o Coolify para aguardar o check ou disparar o deploy pelo workflow após o `pytest`).
  Isso substitui o pipeline de SSH da versão anterior deste documento.
- **Isolamento entre os projetos:** um aplicativo por projeto, cada um com suas variáveis; não compartilhar segredos nem
  banco. O Controle_Locacao não usa o Postgres da VPS (usa o Supabase).
- **Backups:** os dados do Locação ficam no Supabase; manter o backup do Supabase conforme a Fase 6 do plano. A VPS passa a
  ser ponto único de falha dos dois projetos: o backup do Postgres do cell-pag deve ter destino fora da VPS (o próprio guia
  dele já alerta sobre isso).
- **Monitoramento mínimo:** rota `/saude`, reinício automático e aviso se o site cair.
- **Fuso:** o servidor está em UTC. Tarefas agendadas do Locação (se houver) devem converter de America/Sao_Paulo.

**Risco: memória da VPS compartilhada.** No plano de 4 GB rodam juntos o Coolify/Traefik, o Postgres e o Django do cell-pag,
a Evolution API (que pode trazer Redis/Postgres próprios) e o FastAPI do Locação. É viável com 1 a 2 workers por aplicativo,
mas fica apertado em tese.

**Medição real na VPS (05/10/2026, `free -h` e `docker stats`):** dos 3,8 GiB, 1,4 GiB em uso e **2,4 GiB disponíveis**
(cerca de 37% de uso; swap de 1 GiB quase intocado, 79 MiB). Os contêineres somam cerca de 850 MiB: Coolify 388 MiB,
restante da infraestrutura do Coolify pouco mais de 130 MiB, Evolution API 139 MiB, e dois contêineres que parecem ser o
app e o Postgres do cell-pag (147 MiB e 36 MiB; identificação por inferência, a confirmar). Estimativa do FastAPI do
Locação com 1 a 2 workers: 100 a 150 MiB. **Conclusão: o plano de 4 GB basta; o plano de 8 GB só se justifica se o uso
passar de cerca de 70%.** Cuidados: (1) o Coolify constrói a imagem na própria VPS e o `pip install` consome memória;
acompanhar o primeiro build com `free -h` (cabe nos 2,4 GiB livres e no swap); (2) o contêiner `coolify` apareceu com
104% de CPU em um servidor de 2 vCPU; provavelmente pico passageiro, mas conferir com `docker stats --no-stream` em repouso.

**Segurança por exposição pública** (virão como requisitos da Fase 1):

- limite de tentativas de login por IP/usuário, e mensagens de erro que não revelam se o e-mail/CPF existe;
- cookies `httpOnly`, `Secure`, `SameSite=Lax`, e CSRF em todo formulário;
- cabeçalhos de segurança (HSTS, CSP, `X-Frame-Options`) definidos na aplicação (middleware do FastAPI), de forma que
  não dependam do proxy;
- o painel do dono e o portal do locatário continuam separados por papel; a RLS segue como proteção final dos dados;
- atualizações automáticas de segurança do sistema operacional.

**Respostas do proprietário (05/10/2026):**

1. **Provedor:** KingHost (empresa brasileira), VPS pequena e barata. Região Brasil.
2. **Domínio:** gratuito, "da duck.com". **Atenção:** o `duck.com` é um serviço de e-mail do DuckDuckGo e não oferece
   domínios. O serviço gratuito com esse nome é o **DuckDNS** (subdomínios `nome.duckdns.org`), que apontam para o IP
   da VPS e funcionam com o certificado HTTPS automático do Traefik/Coolify (o `duckdns.org` consta na lista pública de sufixos,
   então não sofre limite compartilhado do Let's Encrypt). **Confirmado pelo proprietário (05/10/2026): será o DuckDNS.**
   Limitação: o endereço fica no formato `nome.duckdns.org`; para um endereço próprio (`.com.br`) seria preciso
   registrar um domínio pago, o que pode ser feito depois sem alterar o app.
3. **Administração do servidor:** Alisson (acesso SSH, atualizações e renovações).
4. **Deploy:** **automático**, por GitHub Actions a cada merge na `main` com o `pytest` aprovado.
5. **Orçamento:** consulta ao site da KingHost (`king.host/servidor-vps`, 05/10/2026): o plano mais barato é o
   **VPS 4GB, R$ 32,90/mês** (2 vCPU, 4 GB de RAM, 70 GB de SSD, acesso root, IP dedicado, tráfego ilimitado); o seguinte
   é o VPS 8GB por R$ 63,90/mês. O site cita cobrança anual e bienal parceláveis em até 12x, sem detalhar se o preço
   anunciado vale para o mensal; **conferir no ato da contratação**, assim como o sistema operacional disponível
   (o plano pressupõe Ubuntu LTS). O plano de 4 GB basta para este app sozinho, mas **com a VPS dividida com o cell-pag e a
   Evolution API a memória é o ponto de atenção** (ver a medição acima, que mostrou folga de 2,4 GiB); como a VPS já
   está contratada para o cell-pag, o custo adicional do Locação é zero, a menos que o uso passe de 70% e seja preciso
   subir para o plano de 8 GB. Custo do domínio: zero.
6. **Quando contratar:** o proprietário decidiu deixar a contratação para depois ("é só uma decisão"). Como a Fase 1 e
   a maior parte da migração rodam localmente, a VPS só é necessária para o primeiro deploy e para homologar o portal
   dos locatários no celular real (Fase 4). Contratar até o fim da Fase 3.

**Requisitos decorrentes para a Fase 1 em diante:**

- `Dockerfile` e `.dockerignore` do Controle_Locacao (no molde do cell-pag), com usuário sem privilégios e `/saude` como
  healthcheck; app cadastrado no Coolify como aplicativo separado, com o subdomínio DuckDNS em **Domains**.
- Deploy a cada push na `main` com a CI (`pytest`) aprovada; reversão simples para a imagem anterior em caso de falha
  (o Coolify permite *rollback*). Se for usado o disparo por workflow, o token de API do Coolify fica nos segredos do
  repositório, nunca no código.
- Compatibilidade com os recursos compartilhados da VPS (preferir 1 a 2 workers uvicorn, sem serviços pesados) e
  medição de memória antes do primeiro deploy.

## 11. Protótipo do layout (Fase 0, item 2): produzido

O protótipo estático está em `prototipo/` (`index.html` + `estilos.css`, sem backend, reaproveitando os tokens
do `Design_UI.md` e as fontes de `static/fontes`). Para ver: iniciar a configuração `prototipo-layout` do
`.claude/launch.json` e abrir `http://localhost:8600/prototipo/index.html`.

Três faixas de layout:

| Largura | Navegação |
|---|---|
| ≥ 1100 px | Barra lateral completa (grupos Operação, Cadastros, Frota, Gestão), com indicador amarelo na página ativa |
| 720 a 1099 px | Trilho de ícones de 72 px (rótulo como dica e nome acessível) |
| < 720 px | Topo enxuto + barra inferior com 4 destinos frequentes (Início, Contratos, Cobranças, Motos) e "Mais" abrindo uma folha |

Telas: Dashboard, lista de Motos (tabela no desktop, cartões no celular), Ficha da moto (abas, estado vazio,
diálogo que vira tela cheia no celular) e Novo contrato (assistente no passo 3, com resumo ao lado ou abaixo).
As demais rotas mostram uma tela explicando que seguem os mesmos padrões. Há modo claro, escuro e automático.

Verificado no navegador a 390, 820 e 1440 px: sem rolagem horizontal e com alvos de toque ≥ 44 px nas telas
testadas. **Não foi** testado em aparelhos reais nem com leitor de tela.

## 12. Próximo passo sugerido

Layout aprovado e hospedagem decidida (10.1). A Fase 0 está concluída; próximo passo: Fase 1.
