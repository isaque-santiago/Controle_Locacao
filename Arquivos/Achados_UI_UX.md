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

> A-001 a A-003 vieram da execução só do login. A-004 a A-007 vêm da primeira execução
> autenticada (390 px, claro, Chromium desktop). Os avisos de "diálogo sem rolagem" em
> Documentos, Manutenção e Vistorias foram falso positivo (a rolagem fica no contêiner que
> envolve o diálogo) e a medição foi corrigida. A matriz completa (5 larguras, 2 temas,
> 4 perfis, dados vazio/extremo) ainda não foi executada.
