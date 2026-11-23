# Plano de redesign visual

Registro da auditoria do frontend (23/11/2026) e do plano de melhoria visual. O objetivo é deixar o sistema com cara de produto moderno e dinâmico, sem copiar o estilo de nenhum site: as referências servem para entender princípios, não para imitar.

## 1. Princípios adotados

**Base visual**
- Hierarquia antes de decoração: em cada tela deve ficar claro, em poucos segundos, o que é mais importante (tamanho, peso e contraste).
- Espaçamento em escala fixa (4/8 px), sem valores soltos.
- Poucos níveis tipográficos; números tabulares nas colunas de dinheiro.
- Paleta enxuta: neutros, uma cor de marca e cores semânticas só para status.
- Superfícies em camadas (fundo, cartão, elevado), com borda sutil e sombra discreta.
- Raios de borda consistentes.

**Dinamismo**
- Microinterações em tudo que é clicável (hover, foco, ativo), com transições curtas.
- Feedback imediato (HTMX): indicador no botão, toasts, linhas que entram com suavidade.
- Estados bem desenhados: vazio, carregando (skeleton) e erro.
- Movimento com propósito, sempre respeitando `prefers-reduced-motion`.

**Acessibilidade** (parte de ser bonito): contraste mínimo 4.5:1, foco visível, alvos de toque de 40 px ou mais, status nunca só por cor.

## 2. Auditoria

Telas vistas no app rodando (dev), em desktop 1440 px (claro e escuro) e celular 375 px: Dashboard, Veículos, Contratos, Clientes, Cobranças, fichas de veículo, contrato e cliente, e o formulário "Novo veículo". O assistente de novo contrato não foi aberto, porque a rota de início pode criar rascunho.

**O que já está bom**
- Tokens completos em `src/web/estilos/app.css` (cores, espaçamento, raios, sombras, fontes).
- Modo escuro feito só redefinindo tokens, com troca manual e automática.
- Acessibilidade séria (foco, alvos de 44 px, `prefers-reduced-motion`).
- Responsivo maduro: tabelas viram cartões por container query, barra inferior no celular.
- Peças boas e isoladas: placa em etiqueta, traço amarelo nas seções da ficha, indicador amarelo da barra inferior, título do contrato.

**Problemas encontrados**
1. **Identidade quase ausente no modo claro:** tudo é cinza, branco e grafite; o amarelo da marca aparece só em detalhes. No escuro a identidade aparece mais.
2. **Hierarquia fraca:** KPIs sem destaque; no Dashboard três de quatro cartões têm degradê vermelho, então nenhum alerta se destaca. Números pouco maiores que o título.
3. **Defeitos concretos:** "Indeterminad/o" quebrando no cartão de Prazo do contrato; cartões de KPI com alturas desiguais; campos vazios ("—") ocupando espaço; coluna Km com "0" em todos os veículos.
4. **Listas monótonas:** "Abrir ficha" repetido em toda linha; em Cobranças, três botões com o mesmo peso ("Pagar" e "Cancelar" iguais).
5. **Barra superior do desktop** quase vazia (só o botão de tema).
6. **Formulários** sem agrupamento em seções, ao contrário da ficha do veículo.
7. **Animação de entrada** deixa o conteúdo desbotado por tempo demais (a confirmar no navegador do usuário).
8. **Feedback:** não há skeleton de carregamento nem toasts; estado vazio minimalista.
9. **Manutenção do CSS:** bloco do modo escuro duplicado (`[data-tema="escuro"]` e `prefers-color-scheme`) e muitas regras de tabela específicas por tela.
10. **Celular:** KPIs empilhados em uma coluna, botões de largura total na ficha empurrando o conteúdo útil para baixo.

## 3. Decisões do dono

- Botão primário no modo claro: **manter grafite**, com o amarelo só como detalhe (mais sóbrio).
- Tema padrão: **automático** (segue o sistema operacional).
- Coluna Km: **esconder quando todos os veículos estiverem com 0**.
- Pedidos adicionais: **mais dinamicidade** (animações e interatividade) e visual **moderno**.

## 4. O que "moderno" significa aqui

- Profundidade em camadas: sombras suaves em duas camadas, bordas de 1 px sutis, fundos levemente tingidos.
- Cantos mais arredondados e consistentes (cartões 16 px, campos 10 px).
- Vidro fosco (blur) em elementos flutuantes: barra superior, menus, modais e barra inferior do celular.
- Gradientes discretos em indicadores e cabeçalhos.
- Tipografia com mais contraste: números grandes e rótulos pequenos em cinza.
- Ícones em círculos suaves nos indicadores e selos com ponto colorido.

## 5. Fases

Cada fase é feita em branch própria (`ajuste/` ou `feat/`), com um commit por alteração, e termina com `pytest` verde e conferência no app em claro, escuro e celular.

**Fase 1: Base moderna (`ajuste/base-moderna`)**
1. Consolidar o bloco duplicado do modo escuro.
2. Escala de tons da marca e das cores de status, mantendo o botão grafite.
3. Novo conjunto de raios, sombras e fundos em camadas.
4. Barra superior e barra lateral com vidro fosco e identidade.

**Fase 2: Tipografia e indicadores (`ajuste/tipografia-kpis`)**
1. Escala tipográfica com mais contraste.
2. KPIs com ícone, número maior e tendência; só o realmente crítico em alerta.
3. Alturas iguais nos cartões e correção do "Indeterminad/o".
4. Números tabulares nas colunas de dinheiro.

**Fase 3: Listas e fichas (`ajuste/listas-fichas`)**
1. Linha clicável no lugar de "Abrir ficha"; ações aparecem no hover. Em Cobranças, "Pagar" primário e "Cancelar" discreto.
2. Selos de status mais presentes.
3. Coluna Km escondida quando todos são 0; campos vazios discretos.
4. Barra superior útil (título da página e atalhos).

**Fase 4: Interatividade (`feat/interatividade`)**
1. Busca global com atalho de teclado (`/` ou `Ctrl+K`).
2. Filtros instantâneos nas listas, com HTMX.
3. Painel lateral de pré-visualização, sem sair da lista.
4. Abas e ordenação com transição suave.
5. Ações em linha (marcar pago, enviar mensagem) com confirmação imediata.
6. Atalhos de teclado para as ações mais comuns.

**Fase 5: Animações e feedback (`feat/animacoes-feedback`)**
1. Entrada escalonada de cartões e linhas, curta (150 a 250 ms), sem esconder o conteúdo.
2. Números que contam até o valor; gráficos e barras que crescem.
3. Toasts de confirmação.
4. Skeleton nas listas e estados vazios ilustrados.
5. Microinterações em botões, linhas e modais.
6. Transição suave entre páginas.

**Fase 6: Formulários e celular (`ajuste/formularios-celular`)**
1. Campos agrupados em seções, como na ficha do veículo.
2. Validação com feedback imediato.
3. Celular: KPIs em duas colunas, botões compactos, sensação de aplicativo.

A ordem das fases 3 e 4 ainda pode ser trocada, a pedido do dono.

## 6. Cuidados técnicos

- A CSP do app proíbe `eval` e estilos inline: toda interatividade fica em `static/js/app.js`, com HTMX e CSS externo.
- CSS-fonte em `src/web/estilos/app.css`; regenerar `static/css/app.css` com `python scripts/construir_css.py`.
- Toda animação respeita `prefers-reduced-motion`.
- Dinheiro, datas e formatos seguem as regras do `CLAUDE.md`.
