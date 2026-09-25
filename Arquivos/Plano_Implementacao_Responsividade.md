# Plano de Implementação de Responsividade

> Plano técnico incremental para tornar o Controle de Locação operacional entre
> 320 e 1920 CSS px, com reflow, acessibilidade e manutenção previsível.
>
> Este documento detalha a dimensão de responsividade do
> `Plano_Melhorias_UI_UX.md`. Ele preserva o conceito visual e os tokens definidos
> em `Design_UI.md`, sem alterar regras de negócio ou a arquitetura
> página → serviço → repositório.

## 1. Objetivo e definição de responsividade

O sistema será considerado responsivo quando conteúdo, contexto e funcionalidade
permanecerem disponíveis ao variar:

- largura e altura da janela;
- orientação retrato e paisagem;
- zoom, tamanho e espaçamento de texto;
- entrada por toque, mouse ou teclado;
- quantidade e comprimento dos dados;
- tema claro ou escuro;
- navegador entre Chromium, Firefox e WebKit.

Adaptar somente a geometria da página não é suficiente. Uma tarefa deve continuar
compreensível, alcançável e eficiente, especialmente nos fluxos de consulta,
cadastro, pagamento e manutenção.

## 2. Diagnóstico do estado atual

### 2.1 Base existente favorável

- O sistema usa `layout="wide"`, contêiner fluido com largura máxima e tokens
  centralizados em `src/ui/estilos.css`.
- Há tipografia fluida em indicadores com `clamp()` e limites de largura para
  imagens e mídia.
- Campos possuem altura mínima de 44 px e há foco visível para os principais
  elementos interativos.
- Existe tratamento para `prefers-reduced-motion`.
- A tabela HTML compartilhada já muda para cartões rotulados em telas estreitas.
- Listas de Motos, Clientes, Contratos, Cobranças, Manutenções, Documentos,
  Vistorias e a seção Hoje do Dashboard já possuem adaptações abaixo de 700 px.
- O login, o cabeçalho, os formulários, as colunas do Dashboard e as fichas
  possuem regras de reorganização em larguras menores.
- Estados usam texto junto à cor, e os temas claro e escuro partem dos mesmos
  tokens semânticos.

### 2.2 Lacunas e riscos encontrados

1. **Somente o Dashboard usa `cabecalho_pagina`.** As demais páginas montam
   cabeçalho e ação principal com combinações próprias de `st.columns`, criando
   comportamento e espaçamento inconsistentes.
2. **Há 93 ocorrências de `st.columns` na camada de UI.** Muitas são corretas no
   desktop, mas formulários, filtros e ações dependem do empilhamento automático
   do Streamlit, sem decisão explícita para 320, 390 e 768 px.
3. **As listas responsivas são frágeis.** O CSS associa conteúdo a áreas de grid
   por `nth-child` e seletores `data-testid`. Alterar a ordem ou quantidade de
   colunas pode colocar um dado sob o rótulo errado.
4. **A responsividade está concentrada em um bloco extenso abaixo de 700 px.** Há
   poucos ajustes intermediários, embora tablets, notebooks estreitos e janelas
   divididas sejam cenários operacionais prováveis.
5. **Ações compactas ficam abaixo do padrão do próprio plano de UI/UX.** Há
   botões de lista com 32–34 px e navegação com 42 px; o alvo adotado pelo projeto
   deve ser 44 × 44 px.
6. **Filtros são construídos em colunas rígidas.** Grupos de pílulas e busca
   competem por espaço; não há componente único de filtros ativos, limpeza e
   apresentação compacta no celular.
7. **Abas dependem do comportamento nativo.** Os seis conjuntos de `st.tabs`
   não possuem estratégia explícita para excesso de largura, indicação de
   rolagem ou substituição por seletor em telas estreitas.
8. **Formulários extensos precisam de revisão por tarefa.** Existem grupos de
   duas ou três colunas, rodapés de ação lado a lado e um assistente de contrato
   com rótulos `nowrap`, todos sujeitos a compressão e quebra em 320 px ou zoom.
9. **O modo escuro ainda inverte `st.dataframe` por filtro CSS.** Além da
   fragilidade visual, esse recurso dificulta uma solução consistente de tabela
   em diferentes tamanhos.
10. **Não existe suíte automatizada específica de viewport.** Os 240 testes
    atuais passam, mas verificam principalmente domínio e renderização lógica,
    não overflow, reflow ou regressão visual.
11. **Fontes vêm do Google Fonts.** A interface precisa continuar estável e
    legível quando a rede externa estiver lenta ou indisponível.
12. **Não há evidência registrada do critério WCAG de reflow.** Ainda é
    necessário comprovar ausência de perda de conteúdo e funcionalidade a 320
    CSS px e no cenário equivalente a 400% de zoom.

### 2.3 Classificação atual

| Dimensão | Estado | Observação |
|---|---|---|
| Fundação visual | Boa | Tokens, limites de mídia e espaçamento centralizados |
| Adaptação mobile | Parcialmente boa | Cobertura ampla, porém muito acoplada ao DOM |
| Tablet e janela dividida | Parcial | Poucos comportamentos intermediários explícitos |
| Reflow e zoom | Não comprovado | Requer teste a 320 px, 200% e 400% equivalente |
| Toque e teclado | Parcial | Foco existe; alguns alvos têm menos de 44 px |
| Componentes reutilizáveis | Parcial | Tabela HTML existe; cabeçalhos, filtros e ações variam |
| Testes responsivos | Ausente | Não há matriz automatizada de viewports |
| Manutenibilidade CSS | Crítica | Uso intenso de `data-testid`, `:has()` e `nth-child` |

## 3. Diretrizes de implementação

1. Usar conteúdo, não modelos de aparelho, para decidir mudanças de layout.
2. Trabalhar mobile first nos componentes novos ou migrados.
3. Preservar ordem semântica do conteúdo no HTML; CSS pode reorganizar a
   apresentação, mas não deve criar uma sequência de leitura incoerente.
4. Não ocultar informação ou ação essencial para fazer o layout caber.
5. Preferir componentes com classes estáveis geradas pelo projeto a seletores da
   estrutura interna do Streamlit.
6. Usar `rem`, `%`, `fr`, `minmax()`, `clamp()` e limites intrínsecos; reservar
   pixels para alvos mínimos, bordas e casos realmente fixos.
7. Tratar 320 px como largura mínima de conformidade, 390 px como referência
   móvel operacional e 768–1024 px como faixa intermediária obrigatória.
8. Permitir rolagem horizontal somente dentro de conteúdo legitimamente
   bidimensional, como uma tabela que perderia significado ao ser linearizada.
9. Todo componente alterado deve ser validado em tema claro e escuro, teclado,
   toque e dados extremos.
10. Migrar por componente e fluxo; não reescrever todo o CSS de uma vez.

## 4. Arquitetura responsiva proposta

### 4.1 Faixas de comportamento

As faixas abaixo são pontos iniciais e devem ser ajustadas quando o conteúdo
demonstrar necessidade:

| Faixa | Uso principal | Comportamento esperado |
|---|---|---|
| 320–479 px | Celular estreito | Uma coluna, ações em largura total, filtros compactos |
| 480–767 px | Celular amplo | Cartões e pequenos pares de campos quando couberem |
| 768–1023 px | Tablet/janela dividida | Duas colunas seletivas, navegação recolhida |
| 1024–1439 px | Notebook/desktop | Layout operacional completo com densidade controlada |
| 1440–1920 px | Desktop amplo | Conteúdo limitado; linhas não devem ficar excessivamente longas |

Não criar uma media query para cada faixa por padrão. Usar apenas os pontos em
que um componente efetivamente perde clareza ou funcionalidade.

### 4.2 Componentes compartilhados a consolidar

- `cabecalho_pagina`: título, descrição, contexto e ação primária responsiva.
- `barra_filtros`: filtros com quebra, busca, resumo, limpar e modo compacto.
- `grupo_acoes`: ações primária, secundária e destrutiva com alvos de 44 px.
- `lista_registros`: cartão interativo com campos nomeados e ordem semântica.
- `tabela_html`: somente leitura, com `data-label` e alternativa de overflow
  localizado quando o dado for realmente tabular.
- `paginacao`: Anterior, estado da página e Próxima, preservando filtros.
- `navegacao_secundaria`: abas no desktop e alternativa compacta quando não
  couberem de forma reconhecível.
- `rodape_formulario`: empilhamento previsível das ações e botão primário claro.
- `indicador_etapas`: wizard que aceite quebra ou versão compacta no celular.

## 5. Plano incremental

### Fase 0 — Instrumentação e linha de base

**Objetivo:** tornar os problemas reproduzíveis antes de alterar componentes.

#### Implementação

1. Criar inventário de páginas, visões e diálogos por fluxo.
2. Definir dados de teste com textos longos, valores grandes, listas vazias e
   listas extensas.
3. Adicionar Playwright como suíte separada dos testes Python.
4. Configurar projetos para Chromium desktop, Chromium móvel, Firefox e WebKit.
5. Criar capturas de referência em 320, 390, 768, 1024 e 1440 px.
6. Adicionar verificações de overflow horizontal do documento e de elementos
   interativos fora do viewport.
7. Registrar uma planilha ou Markdown de achados por tela, severidade e fluxo.

#### Critérios de aceite

- Todos os fluxos do `Plano_Melhorias_UI_UX.md` possuem cenário de teste.
- Cada problema pode ser reproduzido por viewport e estado de dados.
- A suíte Python continua com 240 testes aprovados.
- As capturas não contêm dados reais ou segredos.

### Fase 1 — Fundação responsiva e acessibilidade

**Objetivo:** corrigir regras globais antes de tratar telas isoladas.

#### Arquivos principais

- `src/ui/estilos.css`
- `src/ui/estilos_escuro.css`
- `src/ui/componentes.py`
- `src/ui/tema.py`

#### Implementação

1. Criar tokens de largura de conteúdo, espaçamento responsivo e alvo mínimo.
2. Tornar o padding de `.block-container` fluido com `clamp()`.
3. Garantir `min-width: 0` em contêineres flex/grid compartilhados.
4. Aplicar quebra segura a textos longos, links e identificadores, preservando
   `nowrap` apenas em placas, datas e valores cujo agrupamento seja necessário.
5. Elevar controles e navegação operacional para alvo mínimo de 44 × 44 px.
6. Padronizar foco visível também para links, radio, checkbox, select, uploads e
   controles de diálogo.
7. Revisar modais para `max-inline-size`, `max-block-size` e rolagem interna.
8. Definir comportamento das abas quando excederem o espaço.
9. Manter fallback tipográfico dimensionalmente compatível e avaliar fontes
   locais na fase de robustez.

#### Critérios de aceite

- Nenhuma página vazia apresenta overflow horizontal entre 320 e 1920 px.
- Todos os alvos operacionais atingem 44 × 44 px.
- O foco é visível nos dois temas.
- Textos longos não invadem cartões ou ações.
- Diálogos cabem na altura e largura disponíveis.

### Fase 2 — Cabeçalho, filtros, paginação e navegação secundária

**Objetivo:** eliminar padrões repetidos e inconsistentes antes de migrar listas.

#### Implementação

1. Evoluir `cabecalho_pagina` para aceitar ação Streamlit fora do HTML, mantendo
   relação visual estável entre título e botão.
2. Migrar as nove páginas restantes para o cabeçalho compartilhado.
3. No desktop, manter ação à direita; abaixo do ponto de quebra do conteúdo,
   posicioná-la depois da descrição e em largura total.
4. Implementar `barra_filtros` com quebra natural; em celular, usar painel ou
   seletor compacto com indicador da quantidade de filtros ativos.
5. Incluir `Limpar filtros`, quantidade de resultados e persistência do estado.
6. Padronizar paginação sem `number_input` como mecanismo primário.
7. Criar estratégia única para abas: rolagem sinalizada ou seletor em telas
   estreitas, preservando a aba ativa após rerun.
8. Agrupar a navegação lateral conforme `Plano_Melhorias_UI_UX.md` se a API de
   navegação da versão do Streamlit permitir sem hacks de DOM.

#### Ordem de migração

1. Motos, Clientes e Contratos.
2. Manutenção, Documentos e Vistorias.
3. Cobranças e Relatórios.
4. Configurações e Dashboard.

#### Critérios de aceite

- 100% das páginas usam o cabeçalho padrão.
- Filtros funcionam e permanecem legíveis a 320 px.
- Busca, filtros, paginação e aba são preservados ao abrir e fechar uma ficha.
- Ações primárias não ficam espremidas ou isoladas do contexto.

### Fase 3 — Listas e tabelas resilientes

**Objetivo:** reduzir o acoplamento entre conteúdo, posição de coluna e DOM do
Streamlit.

#### Implementação

1. Classificar cada conjunto como tabela somente leitura ou lista interativa.
2. Usar `tabela_html` para dados verdadeiramente tabulares sem ações.
3. Para registros interativos, renderizar cartões com rótulos e classes
   explícitas, em vez de inferir significado por `nth-child`.
4. Manter ações junto à identidade do registro no celular.
5. Permitir overflow localizado apenas em tabelas que precisem comparar colunas.
6. Remover gradualmente os blocos de CSS dependentes da posição das colunas.
7. Substituir os dois usos restantes de `st.dataframe` quando a inversão do tema
   ou a experiência móvel não puder ser garantida.

#### Prioridade por risco

| Prioridade | Área | Motivo |
|---:|---|---|
| 1 | Documentos | Até nove colunas e três ações por registro |
| 2 | Manutenção | Histórico extenso, catálogo e formulários densos |
| 3 | Cobranças | Quatro estruturas distintas de linha e ação financeira |
| 4 | Vistorias | Comparação, fotos e listas com metadados variados |
| 5 | Contratos | Lista, wizard e ficha com múltiplas relações |
| 6 | Motos e Clientes | Padrões semelhantes e boa cobertura móvel existente |
| 7 | Dashboard e Relatórios | Composição especial e gráficos/tabelas de síntese |

#### Critérios de aceite

- Alterar a ordem de um campo no Python não associa conteúdo ao rótulo errado.
- Listas interativas apresentam identidade, metadados e ações compreensíveis.
- Tabelas mantêm cabeçalhos associados às células.
- Nenhuma ação depende exclusivamente de ícone ou tooltip.
- Não há rolagem horizontal no documento.

### Fase 4 — Formulários e fluxos transacionais

**Objetivo:** garantir conclusão de tarefas em celular, zoom e teclado.

#### Implementação

1. Revisar cada `st.columns(2|3)` de formulário e definir explicitamente se o
   agrupamento deve permanecer ou empilhar.
2. Manter campos relacionados lado a lado apenas quando cada um conservar largura
   e rótulo suficientes.
3. Empilhar rodapés de ação em telas estreitas, deixando a ação primária por
   último na ordem de leitura e em largura total.
4. Adaptar o assistente de contrato: etapas compactas, rótulos sem overflow,
   revisão e retorno sem perda de dados.
5. Revisar formulários de manutenção, documentos e vistorias, que concentram os
   grupos mais densos.
6. Garantir teclado numérico e tipos adequados para moeda, quilômetros,
   quantidades e datas quando suportados pelo Streamlit.
7. Validar mensagens sem alterar altura de maneira que esconda ações.
8. Testar teclado virtual, orientação paisagem e viewport com altura reduzida.

#### Critérios de aceite

- Todos os formulários podem ser concluídos a 320 e 390 px.
- Nenhum campo ou mensagem é cortado a 200% de zoom.
- O envio permanece visível ou alcançável sem rolagem em duas dimensões.
- Erros preservam os valores e o foco pode ser levado ao primeiro campo inválido.

### Fase 5 — Fichas, dashboard, gráficos e conteúdo complexo

**Objetivo:** finalizar as composições que dependem de contexto e comparação.

#### Implementação

1. Padronizar resumo e ações das fichas de Moto, Cliente e Contrato.
2. Empilhar painéis laterais quando a coluna secundária perder largura útil.
3. Garantir que voltar restaure lista, filtros, página e posição lógica.
4. Ajustar KPIs para valores grandes sem sobreposição.
5. Revisar Dashboard em 320, 390, 768 e janela dividida, especialmente o par
   Hoje/Alertas.
6. Tornar gráficos de Relatórios fluidos e fornecer resumo ou tabela equivalente.
7. Evitar legenda, eixos e tooltips truncados; limitar altura de gráficos por
   `clamp()` quando aplicável.
8. Revisar comparação de vistorias e galerias de fotos em retrato e paisagem.

#### Critérios de aceite

- Fichas não perdem ações ou contexto em nenhuma faixa.
- KPIs aceitam os maiores valores plausíveis do domínio.
- Gráficos são compreensíveis ou possuem alternativa textual/tabular.
- O retorno à lista preserva o contexto anterior.

### Fase 6 — Robustez, desempenho e compatibilidade

**Objetivo:** reduzir custo de manutenção e evitar responsividade apenas aparente.

#### Implementação

1. Remover seletores `nth-child` já substituídos por componentes explícitos.
2. Inventariar `data-testid` remanescentes e documentar os inevitáveis.
3. Eliminar a inversão global de `st.dataframe` no tema escuro.
4. Empacotar fontes localmente ou validar fallback sem mudança significativa de
   layout.
5. Evitar mídia maior que o tamanho de apresentação e declarar dimensões para
   reduzir deslocamento de layout.
6. Medir páginas representativas com Lighthouse, observando LCP, INP e CLS.
7. Validar versões suportadas de Chromium, Firefox e WebKit.
8. Incluir testes responsivos e capturas no processo de integração contínua.

#### Critérios de aceite

- CSS mobile não depende da posição ordinal de campos migrados.
- Temas funcionam sem filtro global de inversão.
- Falha no carregamento das fontes externas não quebra o layout.
- Não há regressões críticas nos indicadores de desempenho.

### Fase 7 — Homologação e encerramento

**Objetivo:** produzir evidência verificável de qualidade.

#### Matriz mínima

| Largura | Altura de referência | Tema | Entrada |
|---:|---:|---|---|
| 320 | 568 | claro e escuro | toque/teclado |
| 390 | 844 | claro e escuro | toque |
| 768 | 1024 | claro e escuro | toque/teclado |
| 1024 | 768 | claro e escuro | mouse/teclado |
| 1440 | 900 | claro e escuro | mouse/teclado |

Adicionar ainda:

- desktop a 200% de zoom;
- viewport equivalente a 320 CSS px para reflow;
- retrato e paisagem;
- textos com 200% do comprimento comum;
- listas vazias, normais e extensas;
- rede e CPU reduzidas nas páginas representativas.

#### Fluxos de homologação

1. Login e navegação completa.
2. Consultar Dashboard e alertas.
3. Buscar, filtrar, paginar e abrir Moto e Cliente.
4. Criar e revisar um Contrato.
5. Registrar Pagamento.
6. Registrar e concluir Manutenção.
7. Cadastrar e regularizar Documento.
8. Registrar, abrir e comparar Vistorias.
9. Filtrar e exportar Relatórios.
10. Alterar Configurações e gerar backup.

#### Critérios finais

- Ausência de overflow horizontal no documento, salvo exceção documentada e
  localizada.
- Reflow a 320 CSS px sem perda de informação ou funcionalidade.
- Texto a 200% e espaçamento WCAG sem corte ou sobreposição.
- Todos os fluxos concluídos em desktop e celular.
- Navegação integral por teclado, com ordem e foco previsíveis.
- Sem violações críticas ou graves na auditoria automatizada de acessibilidade.
- Capturas aprovadas nas cinco larguras e nos dois temas.
- Testes Python e testes de viewport aprovados.

## 6. Estratégia de testes automatizados

### 6.1 Testes Python existentes

Manter a suíte atual como proteção de regras de negócio e renderização lógica.
Estado da linha de base em 25/09/2026: **240 testes aprovados**.

### 6.2 Testes de navegador

Adicionar testes para:

- `document.documentElement.scrollWidth <= clientWidth`;
- elementos focáveis dentro dos limites do viewport;
- alvo mínimo das ações críticas;
- abertura e fechamento da barra lateral;
- cabeçalho e ação primária em cada faixa;
- persistência de filtros e paginação;
- diálogos sem ações fora da área visível;
- screenshots das páginas e estados principais;
- Chromium, Firefox e WebKit nas rotas de maior risco.

Emulação não substitui aparelho real. A homologação final deve usar ao menos um
telefone Android e, quando disponível, um iPhone/iPad.

### 6.3 Auditorias auxiliares

- Lighthouse para desempenho e verificações automatizadas de acessibilidade.
- axe-core integrado ao navegador para violações detectáveis automaticamente.
- teste manual de teclado e leitor de tela para semântica e ordem de leitura.

## 7. Sequenciamento e dependências

```text
Linha de base
    ↓
Fundação e acessibilidade
    ↓
Cabeçalhos, filtros, paginação e abas
    ↓
Listas e tabelas resilientes
    ↓
Formulários e fluxos transacionais
    ↓
Fichas, dashboard e conteúdo complexo
    ↓
Robustez, desempenho e homologação
```

Não iniciar a migração em massa das telas antes de estabilizar os componentes
compartilhados. Cada fase deve produzir uma entrega utilizável e não pode deixar
duas implementações concorrentes do mesmo padrão sem prazo de remoção.

## 8. Priorização executiva

### P0 — Bloqueadores

- overflow ou perda de ação a 320/390 px;
- botões financeiros ou destrutivos inacessíveis;
- rótulo associado ao dado errado por regra ordinal;
- formulário impossível de concluir com teclado ou zoom;
- diálogo sem acesso à confirmação ou cancelamento.

### P1 — Alta prioridade

- alvos menores que 44 px;
- cabeçalhos, filtros e paginação inconsistentes;
- listas interativas sem semântica clara;
- quebra em tablet ou janela dividida;
- perda de filtros e contexto ao retornar de ficha.

### P2 — Evolução e robustez

- redução de seletores internos do Streamlit;
- fontes locais;
- refinamento de desempenho;
- cobertura visual de estados menos frequentes.

## 9. Indicadores de sucesso

- 100% das páginas com cabeçalho responsivo compartilhado.
- 100% das ações operacionais com alvo mínimo de 44 × 44 px.
- 100% dos fluxos críticos concluídos entre 320 e 1440 px.
- Zero overflow horizontal no documento em estados homologados.
- Zero lista migrada dependente de `nth-child` para identificar conteúdo.
- Zero `st.dataframe` dependente de inversão visual no tema escuro.
- Zero violação crítica ou grave nas auditorias automatizadas acordadas.
- Busca, filtros, paginação e aba preservados ao retornar de uma ficha.
- Capturas automatizadas para as cinco larguras mínimas.
- Testes Python e de navegador aprovados antes de encerrar cada fase.

## 10. Definição de pronto por incremento

Um incremento de responsividade só está pronto quando:

1. possui critérios de aceite demonstráveis;
2. funciona a 320, 390, 768, 1024 e 1440 px quando aplicável;
3. funciona em tema claro e escuro;
4. permite uso por teclado e apresenta foco visível;
5. foi testado com dados vazios, normais e extremos;
6. não cria overflow horizontal no documento;
7. possui teste automatizado proporcional ao risco;
8. mantém os testes existentes aprovados;
9. atualiza `Design_UI.md` quando introduz ou altera um padrão;
10. é registrado em commit descritivo, conforme as regras do projeto.

## 11. Fora do escopo

- reescrever o sistema em outro framework;
- alterar identidade visual ou regras de negócio;
- criar aplicativo móvel nativo;
- otimizar consultas ou banco sem relação comprovada com a experiência responsiva;
- suportar navegadores obsoletos fora da matriz definida.

