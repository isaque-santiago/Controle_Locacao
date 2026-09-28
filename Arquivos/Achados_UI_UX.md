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

> A-001 a A-003 vieram da primeira execução (só a tela de login, Chromium desktop, 320 e
> 1440 px, claro e escuro). As demais telas exigem login e serão registradas na primeira
> execução autenticada.
