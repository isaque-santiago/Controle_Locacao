# Análise e proposta: migração da camada de interface (Streamlit → FastAPI + HTMX)

> **Status: APROVADA pelo proprietário em 05/10/2026 (decisões na seção 10). Implementação: ainda não
> iniciada. Fase atual: 0 (decisão e desenho).**
> O layout do protótipo (`prototipo/`) foi aprovado. A mudança de escopo foi registrada no
> `Plano_Melhorias_UI_UX.md` (seção 10) e no `Projeto_Locação.md` (seção 15).
> **Pendente antes da Fase 1:** hospedagem (decisão 3, seção 10).
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
3. Definir hospedagem, domínio e variáveis de ambiente.
   *Aceite:* o proprietário aprova o protótipo.

**Fase 1 — Fundação**
App FastAPI, templates base, login/logout/sessão (incluindo CPF no portal), proteção por papel, CSRF,
tratamento de erros (`src/domain/erros.py` reaproveitado) e biblioteca de componentes.
*Aceite:* login e logout funcionam, sessão expira em 30 min, F5 mantém a sessão, testes de auth passando.

**Fase 2 — Páginas piloto: Dashboard e Motos**
Valida os padrões de lista, filtro, paginação, ficha e formulário.
*Aceite:* sem overflow horizontal de 320 a 1440 px; alvos ≥ 44 px; teclado completo; paridade funcional.

**Fase 3 — Demais páginas, uma por vez**
Clientes → Contratos (assistente em 4 etapas) → Cobranças → Manutenção → Vistorias (com fotos) →
Documentos → Relatórios (exportação) → Configurações (backup) → Portal do Locatário.
O Streamlit continua funcionando em paralelo, no mesmo banco, até a última página migrar.

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
| Mudança de hospedagem (o código atual trata o proxy do Streamlit Cloud) | Decidir na Fase 0; escolher provedor com HTTPS e variáveis de ambiente |
| Esforço maior que o estimado | O piloto da Fase 2 serve de ponto de decisão: se o padrão não funcionar, parar com custo baixo |
| Trabalho do plano de UI/UX perdido | Tokens, fontes, Design_UI e testes de domínio são reaproveitados; só o que dependia do DOM do Streamlit é descartado |

## 10. Decisões (respondidas pelo proprietário em 05/10/2026)

| # | Decisão | Resposta |
|---|---|---|
| 1 | Mudança de escopo | **Substituir o Streamlit por inteiro.** Nenhuma tela fica no Streamlit ao final. |
| 2 | Etapa 9 do plano de UI/UX | **Opção (b):** não terminar a Etapa 9 no Streamlit. A homologação (10 fluxos, aparelhos reais, rodada autenticada) é refeita no app novo, na Fase 4, reaproveitando `Roteiro_Homologacao_Manual.md`, os fluxos e a matriz de larguras. |
| 3 | Hospedagem | **EM ABERTO.** O proprietário informou que o app roda localmente hoje. Falta definir onde o novo app roda e como os locatários acessam o Portal do Locatário (precisa ser alcançável por eles). Decidir na Fase 0, antes da Fase 1. |
| 4 | Perfil de uso | **Desktop e celular, ambos.** Mantém as três faixas do protótipo. |
| 5 | Portal do Locatário | **No mesmo app**, com login por CPF e papel separado. |
| 6 | Estilo | **Tailwind**, sobre os tokens existentes (`Design_UI.md`). Ver nota abaixo. |

Nota sobre o Tailwind: o protótipo foi escrito em CSS próprio, com tokens como variáveis CSS. Na
implementação, os tokens (cores, espaçamento, raio, fontes, modo escuro) viram a configuração do Tailwind,
sem mudar a identidade visual. A forma de gerar o CSS (CLI independente do Tailwind, sem Node, ou build com Node)
é uma decisão da Fase 0/1; preferir o CLI independente para manter a stack em Python.

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

Layout aprovado. Falta decidir a hospedagem (seção 10, decisão 3) para fechar a Fase 0; depois, Fase 1.
