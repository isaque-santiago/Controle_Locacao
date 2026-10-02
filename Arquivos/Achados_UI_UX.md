# Registro de achados de UI/UX

> Etapa 0 do `Plano_Melhorias_UI_UX.md` (item 7). Este é o registro **curado**: a suíte
> `e2e/` gera o bruto em `e2e/resultados/achados.md` (ignorado pelo git) e os achados
> que serão tratados são copiados para cá, com a etapa que os resolve.

## Como registrar

1. Rode a suíte na matriz completa (ver `e2e/README.md`) para cada estado de dados.
2. Abra `e2e/resultados/achados.md`. Cada linha traz página, tipo, elemento, medidas e
   onde reproduzir (perfil · largura · tema · estado de dados · fluxo).
3. Copie para a tabela abaixo o que for real (descarte falsos positivos anotando o motivo).

Severidades: **P0** bloqueador (overflow, ação perdida, diálogo sem saída) ·
**P1** alta (alvo < 44 px, elemento fora da janela) · **P2** robustez (erro de console) ·
**INFO** cenário não executável (controle não encontrado).

## Achados

| ID | Sev. | Página | Achado | Reprodução | Etapa | Situação |
|---|---|---|---|---|---|---|
| A-001 | P1 | Login | Botão de menu principal do Streamlit (`stMainMenuButton`) com 28×28 px | Chromium desktop, qualquer largura, dados normal | 1 | Aberto |
| A-002 | P1 | Login | Botão de abrir a barra lateral (`stExpandSidebarButton`) com 28×28 px | Chromium desktop, 320–768 px | 1 | Aberto |
| A-003 | P1 | Login | Botão "mostrar senha" com 32×16 px | Chromium desktop, 320 e 1440 px | 1 | Aberto |
| A-004 | P0 | Relatórios · aba Inadimplência | `stMain` rola na horizontal (402 px de conteúdo em 390 px) | Chromium desktop, 390 px, claro, dados normal | 4 (tabela) / 6 | Aberto |
| A-005 | P1 | Todas as páginas | Ações por linha, abas, links do menu e botões de diálogo com altura < 44 px (cerca de 370 ocorrências no total; detalhe em `achados.json`) | Chromium desktop, 390 px, claro, dados normal | 1 | Aberto |
| A-006 | P2 | Todas as páginas autenticadas | `console.error` de recurso com 404 a cada página (origem a identificar) | Chromium desktop, 390 px | 8 | Aberto |
| A-007 | INFO | Cobranças | Fluxo 5: botão de pagamento não localizado pelo rótulo `pagamento\|pagar\|✓`; ajustar o seletor do cenário | Chromium desktop, 390 px, dados normal | 0 | Aberto |
| A-008 | INFO | Configurações | `httpx.ReadTimeout` do Supabase exibido como exceção na página em uma execução (não reproduzido nas outras); tratar em Feedback e recuperação | Chromium desktop, 390 px, dados extremo | 7 | Tratado na Etapa 7 (`classificar_erro` → indisponibilidade + `Tentar novamente`); reverificar com o app autenticado |
| A-009 | P0 | Relatórios · aba Inadimplência | `stMain`/`stMainBlockContainer` rolam na horizontal (overflow confirmado de forma independente em 3 execuções distintas) | 4 perfis (Chromium desktop, Chromium móvel, Firefox, WebKit), 320 e 390 px, claro e escuro, dados normal e extremo | 4 (tabela) / 6 | **Confirmado** |
| A-010 | P1 | Todas as páginas | Ações por linha, abas, links do menu e botões de diálogo com altura < 44 px — sistemático, mesma causa em praticamente todo controle do app (14.162 ocorrências na matriz completa; ver "Sobre a matriz completa" abaixo) | Todos os perfis, todas as larguras, dados extremo | 1 | Aberto |
| A-011 | INFO | Cobranças | Fluxo 5: botão de pagamento não localizado em quase toda combinação de perfil/largura/tema — o seletor do cenário (`pagamento\|pagar\|✓`) precisa ser trocado pelo rótulo real do botão da lista | Todos os perfis, dados normal e extremo | 0 (ajuste do cenário e2e) | Aberto |
| A-012 | A reverificar | Dashboard, Motos, Clientes, Contratos, Documentos, Relatórios, Vistorias, Manutenção, Cobranças, Configurações | ~30 ocorrências de exceção exibida na página, timeout de navegação e "diálogo não abriu", espalhadas por vários perfis/larguras isolados (não repetidas entre execuções independentes) | Vários perfis, dados extremo, execução da matriz completa (quase 2h contínuas) | — | **Não confirmado** |
| A-013 | P0 (a reverificar) | Motos | Sessão perdida (`sessao-perdida`) após navegação por URL | WebKit, 1024 px, claro, dados extremo | 1 | A reverificar |

## Resolução na Etapa 1 (29/09/2026)

Verificada com o app real (login, sem credenciais) e com dados fictícios em 5 larguras × 2 temas
(Motos, Clientes, Contratos, Cobranças, Manutenção, Documentos, Vistorias, Dashboard e diálogos):
zero alvo < 44 px e zero overflow nas áreas tratadas.

| ID | Situação | Como |
|---|---|---|
| A-001, A-002, A-003 | **Resolvido** | alvo mínimo nos controles nativos (menu, barra lateral, mostrar senha); login sem achados |
| A-005, A-010 | **Resolvido**, exceto o abaixo | ações por linha, abas, links do menu, botões de diálogo, selects, radio/checkbox, expander e ajuda `?` ≥ 44 px |
| A-007, A-011 | **Resolvido** (cenário e2e) | seletor de pagamento agora é `\bpagar\b`; rótulos de voltar/abrir atualizados |
| — | **Pendente (Etapa 4)** | barra de ferramentas do `st.data_editor` (Adicionar linha, colunas, CSV, busca) no diálogo de Manutenção: 22 × 22 px, controle nativo do Streamlit |
| A-004, A-009 | Aberto (Etapa 4/6) | overflow em Relatórios · Inadimplência (tabela) — não tratado nesta etapa |
| A-006, A-008, A-012, A-013 | Aberto | reverificar com o app autenticado (exigem login do usuário) |

> A-001 a A-003 vieram da execução só do login. A-004 a A-008 vêm de execuções autenticadas
> pontuais (390 px, claro, Chromium desktop, dados normal e extremo). Os avisos de "diálogo
> sem rolagem" em Documentos, Manutenção e Vistorias foram falso positivo (a rolagem fica no
> contêiner que envolve o diálogo) e a medição foi corrigida. Com dados extremos (30 motos,
> textos longos, 999.999 km) a lista de Motos não apresentou overflow nem sobreposição em
> 390 px. O estado `vazio` ainda não foi executado.

## Sobre a matriz completa (28–29/09/2026, dados extremo)

Rodada com os 4 perfis, 5 larguras e 2 temas (40 cenários autenticados + login), levou
quase 2h. Resultado bruto: 363 testes aprovados, 35 com erro; 14.699 achados (P0: 72,
P1: 14.162, P2: 427, INFO: 38).

**O arquivo detalhado dessa execução foi perdido**: uma verificação isolada rodada logo
depois sobrescreveu `e2e/resultados/achados.json`/`achados.md` antes de o achado curado ser
extraído. Preservado:

- as 730 capturas de tela em `e2e/capturas/extremo/` (todas as combinações);
- os totais por severidade acima;
- a lista de achados P0/INFO, copiada para a tabela acima e resumida em A-009 a A-013.

A-009 (overflow em Relatórios · Inadimplência) é o único P0 da matriz reproduzido de forma
independente em execuções separadas (antes e depois da matriz completa) — trate como real.
Os demais P0 "isolados" (A-012, A-013: exceções, timeouts, diálogo que não abriu, sessão
perdida) apareceram uma única vez cada, espalhados por perfis e larguras sem padrão, ao fim
de quase 2h de execução contínua com dezenas de contextos de navegador abertos — quando
verifiquei isoladamente o cenário com mais erros consecutivos (WebKit 1440 escuro, 9 erros),
ele passou limpo. É mais provável que sejam desgaste da execução longa (timeout do
Supabase, memória do navegador) do que bugs reais de UI, mas **não foram descartados**:
antes de fechar a Etapa 1, reverificar cada um isoladamente (rodando só aquele perfil e
largura) para confirmar ou descartar.
