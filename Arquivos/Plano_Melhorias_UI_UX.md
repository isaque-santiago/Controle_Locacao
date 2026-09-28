# Plano de Melhorias de UI/UX e Responsividade

> Plano único e incremental para evolução do frontend do Controle de Locação:
> usabilidade, acessibilidade, consistência e responsividade entre 320 e 1920 CSS px.
> Complementa `Design_UI.md` e `Projeto_Locação.md`; não substitui as decisões
> visuais ou as regras de negócio desses documentos.
>
> Este documento **unifica** o antigo `Plano_Melhorias_UI_UX.md` e o antigo
> `Plano_Implementacao_Responsividade.md`. Responsividade não é uma trilha
> paralela: cada etapa abaixo entrega, ao mesmo tempo, a melhoria de UI/UX e o
> comportamento responsivo correspondente, evitando retrabalho na mesma tela.

## 1. Objetivo

Melhorar a usabilidade operacional, a acessibilidade, a consistência e a
responsividade do sistema sem descaracterizar o conceito visual de **painel de
instrumentos** já adotado.

As prioridades são:

1. tornar as ações confortáveis e compreensíveis em desktop e celular;
2. permitir navegação adequada por teclado e tecnologias assistivas;
3. reduzir diferenças de comportamento entre páginas;
4. melhorar filtros, formulários e feedback de operações;
5. diminuir a fragilidade causada por seletores dependentes do DOM do Streamlit;
6. manter conteúdo, contexto e funcionalidade disponíveis ao variar largura e
   altura da janela, orientação, zoom, tipo de entrada (toque, mouse, teclado),
   volume de dados, tema (claro/escuro) e navegador (Chromium, Firefox, WebKit).

Adaptar somente a geometria da página não é suficiente: uma tarefa deve continuar
compreensível, alcançável e eficiente, especialmente nos fluxos de consulta,
cadastro, pagamento e manutenção.

## 2. Princípios da evolução

- Preservar a paleta, tipografia, linguagem visual e componentes definidos em
  `Design_UI.md`.
- Priorizar os fluxos mais frequentes: consultar pendências, localizar registros,
  abrir fichas, criar contratos e registrar pagamentos.
- Nenhuma informação deve depender apenas de cor, ícone ou tooltip.
- Manter a interface simples: uma ação primária evidente por contexto.
- Tratar celular como ambiente operacional, não apenas como versão reduzida do
  desktop.
- Usar conteúdo, não modelos de aparelho, para decidir mudanças de layout.
- Trabalhar mobile first nos componentes novos ou migrados.
- Preservar a ordem semântica do conteúdo no HTML; o CSS pode reorganizar a
  apresentação, mas não deve criar uma sequência de leitura incoerente.
- Não ocultar informação ou ação essencial para fazer o layout caber.
- Preferir componentes com classes estáveis geradas pelo projeto a seletores da
  estrutura interna do Streamlit.
- Usar `rem`, `%`, `fr`, `minmax()`, `clamp()` e limites intrínsecos; reservar
  pixels para alvos mínimos, bordas e casos realmente fixos.
- Tratar 320 px como largura mínima de conformidade, 390 px como referência móvel
  operacional e 768–1024 px como faixa intermediária obrigatória.
- Permitir rolagem horizontal somente dentro de conteúdo legitimamente
  bidimensional, como uma tabela que perderia significado ao ser linearizada.
- Migrar por componente e fluxo; não reescrever todo o CSS de uma vez.
- Implementar e validar uma etapa por vez.

## 3. Diagnóstico consolidado

### 3.1 Pontos fortes

- Design system centralizado em tokens CSS (`src/ui/estilos.css`), com tema claro e
  escuro próprios a partir dos mesmos tokens semânticos.
- Hierarquia visual consistente e identidade adequada ao domínio de locação de
  motos.
- Estados acompanhados por texto, sem depender exclusivamente de cor.
- Estados vazios, cartões, KPIs e formatação brasileira reutilizáveis.
- `layout="wide"`, contêiner fluido com largura máxima, tipografia fluida em
  indicadores (`clamp()`) e limites de largura para imagens e mídia.
- Campos com altura mínima de 44 px, foco visível nos principais elementos e
  tratamento de `prefers-reduced-motion`.
- Tabela HTML compartilhada que já vira cartões rotulados em telas estreitas.
- Listas de Motos, Clientes, Contratos, Cobranças, Manutenções, Documentos,
  Vistorias e a seção Hoje do Dashboard adaptadas abaixo de 700 px; login,
  cabeçalho, formulários, colunas do Dashboard e fichas com regras de
  reorganização.
- Fluxo de novo contrato dividido em etapas.

### 3.2 Lacunas e riscos

**Ações e acessibilidade**

1. Ações por ícone têm áreas clicáveis de 32 a 34 px e a navegação tem 42 px; o
   alvo adotado pelo projeto deve ser 44 × 44 px.
2. Símbolos como `→`, `✓`, `✎` e `›` dependem de tooltip para explicar a ação.
3. O foco visível não cobre todos os controles (links, radio, checkbox, select,
   uploads, diálogos).

**Estrutura e consistência**

4. Somente o Dashboard usa `cabecalho_pagina`; as demais páginas montam cabeçalho
   e ação principal com combinações próprias de `st.columns`, com espaçamento e
   comportamento inconsistentes.
5. Cabeçalhos, mensagens de sucesso e estados vazios não seguem um padrão único.
6. Algumas listas simulam tabelas com `st.columns`, sem semântica de tabela ou de
   cartão para tecnologias assistivas.
7. A navegação lateral tem dez destinos no mesmo nível.

**Responsividade**

8. Há 94 chamadas a `st.columns` na camada de UI; muitas dependem do
   empilhamento automático do Streamlit, sem decisão explícita para 320, 390 e
   768 px.
9. As listas responsivas são frágeis: o CSS associa conteúdo a áreas de grid por
   `nth-child` e `data-testid`. Alterar a ordem ou a quantidade de colunas pode
   colocar um dado sob o rótulo errado.
10. A responsividade está concentrada em um bloco extenso abaixo de 700 px, com
    poucos ajustes intermediários (tablets, notebooks estreitos, janelas
    divididas).
11. Filtros em colunas rígidas competem por espaço; não há componente único de
    filtros ativos, limpeza e modo compacto no celular.
12. Os seis conjuntos de `st.tabs` não têm estratégia para excesso de largura,
    indicação de rolagem ou substituição por seletor em telas estreitas.
13. Formulários extensos (grupos de duas ou três colunas, rodapés de ação lado a
    lado, assistente de contrato com rótulos `nowrap`) sofrem compressão e quebra
    em 320 px ou com zoom.

**Formulários e feedback**

14. Campos monetários, percentuais e numéricos são frequentemente campos de texto
    comuns.
15. A confirmação genérica `Alterações salvas.` não descreve o que mudou.

**Robustez e verificação**

16. O modo escuro do `st.dataframe` depende de inversão visual por CSS.
17. Parte relevante do CSS depende de `data-testid`, `:has()` e `nth-child`.
18. Não existe suíte automatizada de viewport. Os 240 testes Python (linha de base
    de 25/09/2026) verificam domínio e renderização lógica, não overflow, reflow
    ou regressão visual.
19. As fontes vêm do Google Fonts; a interface precisa permanecer estável e legível
    com a rede externa lenta ou indisponível.
20. Não há evidência registrada do critério WCAG de reflow (320 CSS px e cenário
    equivalente a 400% de zoom).

### 3.3 Classificação atual

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

## 4. Arquitetura responsiva

### 4.1 Faixas de comportamento

Pontos iniciais, a ajustar quando o conteúdo demonstrar necessidade:

| Faixa | Uso principal | Comportamento esperado |
|---|---|---|
| 320–479 px | Celular estreito | Uma coluna, ações em largura total, filtros compactos |
| 480–767 px | Celular amplo | Cartões e pequenos pares de campos quando couberem |
| 768–1023 px | Tablet/janela dividida | Duas colunas seletivas, navegação recolhida |
| 1024–1439 px | Notebook/desktop | Layout operacional completo com densidade controlada |
| 1440–1920 px | Desktop amplo | Conteúdo limitado; linhas não devem ficar excessivamente longas |

Não criar uma media query para cada faixa por padrão. Usar apenas os pontos em que
um componente efetivamente perde clareza ou funcionalidade.

### 4.2 Componentes compartilhados a consolidar

- `cabecalho_pagina`: título, descrição/resumo, sobretítulo ou breadcrumb,
  indicador contextual e ação primária responsiva.
- `barra_filtros`: filtros com quebra, busca, resumo, limpar e modo compacto.
- `grupo_acoes`: ações primária, secundária e destrutiva com alvos de 44 px.
- `lista_registros`: cartão interativo com campos nomeados e ordem semântica.
- `tabela_html`: somente leitura, com `data-label` e overflow localizado quando o
  dado for realmente tabular.
- `paginacao`: Anterior, estado da página e Próxima, preservando filtros.
- `navegacao_secundaria`: abas no desktop e alternativa compacta quando não
  couberem de forma reconhecível.
- `rodape_formulario`: empilhamento previsível das ações e botão primário claro.
- `indicador_etapas`: wizard com quebra ou versão compacta no celular.
- Componentes de estado vazio, confirmação, alerta e erro padronizados.

## 5. Plano de implementação por etapas

Cada etapa entrega UI/UX **e** responsividade dos itens que trata. Os critérios de
aceite valem para ambas as dimensões.

### Etapa 0 — Linha de base e instrumentação

**Prioridade:** pré-requisito

**Objetivo:** tornar os problemas reproduzíveis antes de alterar componentes.

#### Trabalho previsto

1. Criar inventário de páginas, visões e diálogos por fluxo.
2. Definir dados de teste com textos longos, valores grandes, listas vazias e
   listas extensas.
3. Adicionar Playwright como suíte separada dos testes Python.
4. Configurar projetos para Chromium desktop, Chromium móvel, Firefox e WebKit.
5. Criar capturas de referência em 320, 390, 768, 1024 e 1440 px.
6. Adicionar verificações de overflow horizontal do documento e de elementos
   interativos fora do viewport.
7. Registrar em Markdown (ou planilha) os achados por tela, severidade e fluxo.

#### Critérios de aceite

- Todos os fluxos mínimos (Etapa 9) possuem cenário de teste.
- Cada problema pode ser reproduzido por viewport e estado de dados.
- A suíte Python continua com 240 testes aprovados.
- As capturas não contêm dados reais ou segredos.

### Etapa 1 — Fundação, acessibilidade e ações operacionais

**Prioridade:** crítica

**Objetivo:** corrigir regras globais e ações antes de tratar telas isoladas.

**Arquivos principais:** `src/ui/estilos.css`, `src/ui/estilos_escuro.css`,
`src/ui/componentes.py`, `src/ui/tema.py`.

#### Trabalho previsto

*Fundação responsiva*

1. Criar tokens de largura de conteúdo, espaçamento responsivo e alvo mínimo.
2. Tornar o padding de `.block-container` fluido com `clamp()`.
3. Garantir `min-width: 0` em contêineres flex/grid compartilhados.
4. Aplicar quebra segura a textos longos, links e identificadores, preservando
   `nowrap` apenas em placas, datas e valores cujo agrupamento seja necessário.
5. Revisar modais para `max-inline-size`, `max-block-size` e rolagem interna.
6. Manter fallback tipográfico dimensionalmente compatível (fontes locais são
   avaliadas na Etapa 8).

*Ações e acessibilidade*

7. Aumentar para pelo menos 44 × 44 px a área clicável das ações por linha e da
   navegação, mantendo o desenho do ícone compacto (amplia-se só a área de
   interação).
8. Substituir símbolos Unicode por ícones consistentes do mesmo conjunto visual.
9. Garantir nome acessível e explicação textual para todas as ações.
10. No celular, exibir texto junto ao ícone quando a intenção não for óbvia:
    `Pagar`, `Editar`, `Abrir`, `Concluir` e `Regularizar`.
11. Separar ações semanticamente diferentes. Um botão não deve significar
    simultaneamente “concluir ou cancelar”.
12. Padronizar foco visível também para links, radio, checkbox, select, uploads e
    controles de diálogo; verificar ordem de tabulação e ativação por teclado.
13. Verificar contraste dos estados nos modos claro e escuro.

#### Áreas afetadas

- Dashboard: registrar pagamento.
- Motos: atualizar quilometragem e abrir ficha.
- Clientes e contratos: abrir ficha.
- Cobranças: copiar mensagem e registrar pagamento.
- Manutenção: concluir, cancelar e editar item.
- Documentos: editar, ver comprovante e regularizar.
- Vistorias: abrir comparação.

#### Critérios de aceite

- Toda ação interativa possui alvo de pelo menos 44 × 44 px.
- Toda ação possui nome compreensível sem depender de hover.
- É possível percorrer e acionar os controles usando apenas teclado.
- O foco permanece visível nos dois temas.
- A mesma ação usa o mesmo ícone, texto e tratamento visual em todas as páginas.
- Nenhuma operação ambígua permanece representada por um único botão.
- Nenhuma página vazia apresenta overflow horizontal entre 320 e 1920 px.
- Textos longos não invadem cartões ou ações; diálogos cabem na altura e largura
  disponíveis.

### Etapa 2 — Cabeçalho de página e padrões de estado

**Prioridade:** alta

**Objetivo:** eliminar cabeçalhos e mensagens improvisados antes de migrar listas.

#### Trabalho previsto

1. Evoluir `cabecalho_pagina` para receber título, descrição ou resumo
   contextual, ação primária (Streamlit, fora do HTML, com relação visual estável
   com o título), sobretítulo/breadcrumb opcional e indicador contextual opcional.
2. Migrar as nove páginas restantes para o cabeçalho compartilhado.
3. No desktop, posicionar a ação principal à direita; abaixo do ponto de quebra do
   conteúdo, posicioná-la depois da descrição e em largura total.
4. Padronizar estados vazios com título, explicação e ação de recuperação quando
   aplicável.
5. Padronizar confirmações, alertas e erros (aparência e posição; o conteúdo
   específico das mensagens é tratado na Etapa 7).

#### Ordem de migração

1. Motos, Clientes e Contratos.
2. Manutenção, Documentos e Vistorias.
3. Cobranças e Relatórios.
4. Configurações e Dashboard.

#### Critérios de aceite

- 100% das páginas usam o cabeçalho padrão, com o mesmo alinhamento e
  espaçamento.
- Cada página apresenta no máximo uma ação primária no cabeçalho.
- Ações primárias não ficam espremidas ou isoladas do contexto em nenhuma faixa.
- Estados vazios informam o motivo e, quando possível, o próximo passo.

### Etapa 3 — Navegação, filtros, abas e paginação

**Prioridade:** alta

**Objetivo:** localizar e circular com pouco esforço, inclusive em telas estreitas,
sem perder contexto.

#### Trabalho previsto

*Navegação e localização*

1. Agrupar a navegação lateral sem alterar as rotas, se a API de navegação da
   versão do Streamlit permitir sem hacks de DOM:
   - **Operação:** Dashboard, Contratos, Cobranças;
   - **Cadastros:** Motos, Clientes;
   - **Frota:** Manutenção, Documentos, Vistorias;
   - **Gestão:** Relatórios;
   - **Sistema:** Configurações.
2. Avaliar uma ação rápida persistente para `Novo contrato`.
3. Manter claramente visível a página ativa.
4. Nas fichas, apresentar retorno contextual: `Voltar para motos`, `Voltar para
   clientes` ou `Voltar para contratos`.
5. Preservar busca, filtros, página e posição lógica da lista quando o usuário
   abrir uma ficha e voltar.

*Filtros e busca*

6. Implementar `barra_filtros`: chips com quebra de linha no desktop; no celular,
   seletor compacto ou painel `Filtros` com indicador da quantidade de filtros
   ativos.
7. Mostrar filtros ativos, oferecer `Limpar filtros` e exibir a quantidade de
   resultados após busca e filtragem.
8. Aplicar atraso curto à busca ou executá-la explicitamente, evitando
   atualizações a cada tecla.

*Abas e paginação*

9. Definir estratégia única para abas: rolagem horizontal sinalizada ou seletor
   compacto em telas estreitas; manter a aba ativa durante atualizações que não
   representem mudança de contexto.
10. Padronizar paginação (`Anterior`, informação da página, `Próxima`) sem
    `number_input` como mecanismo primário; quando apropriado, permitir escolher a
    quantidade de registros por página.

#### Critérios de aceite

- Um usuário identifica o grupo funcional de cada página sem percorrer toda a barra
  lateral; o item ativo é perceptível nos dois temas.
- A ação rápida não compete visualmente com alertas ou ações destrutivas.
- Nenhum filtro tem texto truncado ou alvo de toque reduzido entre 320 e 1920 px;
  filtros selecionados são identificáveis sem depender apenas da cor.
- A limpeza de filtros exige uma única ação; a busca informa claramente quando não
  há resultados.
- Busca, filtros, paginação e aba são preservados ao abrir e fechar uma ficha.

### Etapa 4 — Listas e tabelas resilientes

**Prioridade:** alta

**Objetivo:** reduzir o acoplamento entre conteúdo, posição de coluna e DOM do
Streamlit, com semântica adequada para tecnologias assistivas.

#### Trabalho previsto

1. Classificar cada conjunto como tabela somente leitura ou lista interativa.
2. Usar `tabela_html` semântica para dados verdadeiramente tabulares sem ações.
3. Para registros interativos, renderizar cartões com título, metadados, rótulos e
   classes explícitas e grupo de ações identificável — em vez de inferir
   significado por `nth-child`. Manter a densidade adequada ao uso operacional,
   sem cartões excessivamente altos.
4. Manter ações junto à identidade do registro no celular.
5. Permitir overflow localizado apenas em tabelas que precisem comparar colunas.
6. Remover gradualmente os blocos de CSS dependentes da posição das colunas.
7. Substituir o uso restante de `st.dataframe` (`componentes.py`) e avaliar o `st.data_editor` de Manutenção quando a inversão do tema
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
- Listas somente leitura usam cabeçalhos e células semanticamente relacionados.
- Listas interativas apresentam identidade, metadados e ações compreensíveis.
- Nenhuma ação depende exclusivamente de ícone ou tooltip.
- Não há rolagem horizontal no documento.

### Etapa 5 — Formulários, validação e fluxos transacionais

**Prioridade:** alta

**Objetivo:** prevenir erros de entrada e garantir conclusão de tarefas em celular,
zoom e teclado.

#### Trabalho previsto

*Tipo de dado e validação*

1. Aplicar comportamento adequado ao tipo do dado:
   - moeda com prefixo `R$` e formatação brasileira;
   - percentuais com sufixo `%`;
   - dias, quilômetros e quantidades com entrada numérica (teclado numérico e
     tipos adequados, quando suportados pelo Streamlit);
   - CPF, telefone e placa com máscara ou normalização previsível.
2. Validar campos o mais próximo possível da entrada incorreta, sem alterar a
   altura de forma que esconda ações.
3. Preservar todos os valores quando houver erro; permitir levar o foco ao
   primeiro campo inválido.
4. Exibir texto de ajuda apenas quando ele orientar uma decisão real.
5. Identificar campos obrigatórios antes do envio e desabilitar a confirmação
   enquanto os requisitos mínimos não forem atendidos, informando o motivo.
6. Em ações destrutivas, explicar o impacto, listar os registros afetados e
   solicitar confirmação explícita.

*Layout responsivo dos formulários*

7. Revisar cada `st.columns(2|3)` de formulário e definir explicitamente se o
   agrupamento permanece ou empilha; manter campos lado a lado apenas quando cada
   um conservar largura e rótulo suficientes.
8. Implementar `rodape_formulario`: empilhar ações em telas estreitas, com a ação
   primária por último na ordem de leitura e em largura total.
9. Adaptar o assistente de contrato: `indicador_etapas` compacto, rótulos sem
   overflow, e possibilidade de revisar dados anteriores e retornar sem perder o
   progresso.
10. Revisar os formulários de Manutenção, Documentos e Vistorias, que concentram os
    grupos mais densos.
11. Testar teclado virtual, orientação paisagem e viewport com altura reduzida.

#### Critérios de aceite

- Valores monetários são exibidos e editados no padrão `R$ 1.234,56`.
- Mensagens de validação identificam o campo e como corrigir o problema.
- Nenhum formulário é apagado após erro de validação ou falha do serviço.
- Operações destrutivas informam quais registros serão afetados.
- O botão principal comunica claramente quando está indisponível e por quê.
- Todos os formulários podem ser concluídos a 320 e 390 px.
- Nenhum campo ou mensagem é cortado a 200% de zoom; o envio permanece visível ou
  alcançável sem rolagem em duas dimensões.

### Etapa 6 — Fichas, dashboard, gráficos e conteúdo complexo

**Prioridade:** alta

**Objetivo:** finalizar as composições que dependem de contexto e comparação.

#### Trabalho previsto

1. Padronizar resumo e ações das fichas de Moto, Cliente e Contrato.
2. Empilhar painéis laterais quando a coluna secundária perder largura útil.
3. Garantir que voltar restaure lista, filtros, página e posição lógica (em
   conjunto com a Etapa 3).
4. Ajustar KPIs para valores grandes sem sobreposição.
5. Revisar o Dashboard em 320, 390, 768 e janela dividida, especialmente o par
   Hoje/Alertas.
6. Tornar os gráficos de Relatórios fluidos e fornecer resumo ou tabela
   equivalente; evitar legenda, eixos e tooltips truncados; limitar a altura dos
   gráficos por `clamp()` quando aplicável.
7. Revisar comparação de vistorias e galerias de fotos em retrato e paisagem.

#### Critérios de aceite

- Fichas não perdem ações ou contexto em nenhuma faixa.
- KPIs aceitam os maiores valores plausíveis do domínio.
- Gráficos são compreensíveis ou possuem alternativa textual/tabular.
- O retorno à lista preserva o contexto anterior.

### Etapa 7 — Feedback, carregamento e recuperação

**Prioridade:** média

**Objetivo:** operações previsíveis, com mensagens úteis e recuperação de falhas.

#### Trabalho previsto

1. Substituir a confirmação genérica `Alterações salvas.` por mensagens
   específicas, por exemplo: `Moto cadastrada.`, `Pagamento de R$ 450,00
   registrado.`, `Contrato encerrado.`
2. Usar toast para confirmações simples e alerta persistente para situações que
   exigem atenção.
3. Durante operações, trocar o rótulo do botão por um estado como `Salvando…` e
   impedir envios duplicados.
4. Usar spinner ou skeleton apenas quando a espera for perceptível.
5. Oferecer nova tentativa quando uma consulta falhar.
6. Diferenciar erro de validação, indisponibilidade do serviço, sessão expirada e
   falta de permissão.
7. Garantir que toasts e mensagens não cubram ações nem fiquem fora da área visível
   em telas estreitas.

#### Critérios de aceite

- Toda operação iniciada informa progresso, sucesso ou falha.
- Cliques repetidos não geram registros duplicados.
- Mensagens de sucesso descrevem o que foi alterado.
- Erros recuperáveis apresentam uma ação clara de nova tentativa.

### Etapa 8 — Robustez visual, desempenho e compatibilidade

**Prioridade:** média

**Objetivo:** reduzir custo de manutenção e evitar responsividade apenas aparente.

#### Trabalho previsto

1. Remover os seletores `nth-child` já substituídos por componentes explícitos.
2. Inventariar os `data-testid` remanescentes e documentar os inevitáveis.
3. Eliminar a inversão global de `st.dataframe` no modo escuro, preferindo tabelas
   HTML do design system ou configuração de tema nativa.
4. Encapsular padrões complexos em componentes com chaves e classes estáveis.
5. Eliminar estilos inline novos; migrar os existentes para classes quando o
   componente for alterado.
6. Empacotar fontes localmente ou validar fallback sem mudança significativa de
   layout.
7. Evitar mídia maior que o tamanho de apresentação e declarar dimensões para
   reduzir deslocamento de layout.
8. Medir páginas representativas com Lighthouse (LCP, INP e CLS).
9. Validar as versões suportadas de Chromium, Firefox e WebKit.
10. Incluir testes responsivos e capturas no processo de integração contínua.
11. Documentar componentes e variantes no `Design_UI.md` após estabilização.

#### Critérios de aceite

- Tabelas continuam legíveis nos dois temas sem filtros CSS de inversão.
- O CSS mobile não depende da posição ordinal de campos migrados; mudanças na
  ordem de colunas não quebram o layout.
- Componentes alterados não adicionam valores visuais fora dos tokens.
- Falha no carregamento das fontes externas não quebra o layout.
- Não há regressões críticas nos indicadores de desempenho.

### Etapa 9 — Homologação e encerramento

**Prioridade:** necessária para encerrar o plano

**Objetivo:** produzir evidência verificável de qualidade.

#### Matriz mínima

| Largura | Altura de referência | Tema | Entrada |
|---:|---:|---|---|
| 320 | 568 | claro e escuro | toque/teclado |
| 390 | 844 | claro e escuro | toque |
| 768 | 1024 | claro e escuro | toque/teclado |
| 1024 | 768 | claro e escuro | mouse/teclado |
| 1440 | 900 | claro e escuro | mouse/teclado |

Adicionar ainda: desktop a 200% de zoom; viewport equivalente a 320 CSS px para
reflow (400% de zoom); retrato e paisagem; textos com 200% do comprimento comum;
listas vazias, normais e extensas; rede e CPU reduzidas nas páginas
representativas.

#### Fluxos de homologação

1. Entrar no sistema e navegar por todas as páginas.
2. Consultar Dashboard e alertas.
3. Buscar, filtrar, paginar e abrir Moto e Cliente.
4. Criar e revisar um Contrato completo.
5. Registrar um Pagamento.
6. Registrar e concluir uma Manutenção.
7. Cadastrar e regularizar um Documento.
8. Registrar, abrir e comparar Vistorias.
9. Filtrar e exportar Relatórios.
10. Alterar Configurações e gerar/baixar backup.

#### Verificações

- Navegação completa por teclado, com foco visível e ordem lógica.
- Nomes acessíveis para botões e campos.
- Contraste mínimo de 4,5:1 para texto comum.
- Zoom de navegador em 200% sem perda de funcionalidade; texto a 200% e
  espaçamento WCAG sem corte ou sobreposição.
- Reflow a 320 CSS px sem perda de informação ou funcionalidade.
- Ausência de rolagem horizontal na página; tabelas podem ter rolagem interna
  quando realmente necessário (exceção documentada e localizada).
- Mensagens compreensíveis sem conhecimento técnico.
- Ausência de erros relevantes no console e nos logs do Streamlit.

#### Critérios de aceite

- Todos os fluxos são concluídos em desktop e celular.
- Não existem violações críticas ou graves na auditoria automatizada de
  acessibilidade.
- Não há regressão visual nas páginas autenticadas e na tela de login.
- Capturas aprovadas nas cinco larguras e nos dois temas, registradas como
  resultado da validação.
- Testes Python e testes de viewport aprovados.

## 6. Estratégia de testes automatizados

### 6.1 Testes Python existentes

Manter a suíte atual como proteção de regras de negócio e renderização lógica.
Linha de base em 25/09/2026: **240 testes aprovados**.

### 6.2 Testes de navegador (Playwright)

- `document.documentElement.scrollWidth <= clientWidth`;
- elementos focáveis dentro dos limites do viewport;
- alvo mínimo (44 × 44 px) das ações críticas;
- abertura e fechamento da barra lateral;
- cabeçalho e ação primária em cada faixa;
- persistência de filtros, paginação e aba;
- diálogos sem ações fora da área visível;
- screenshots das páginas e estados principais;
- Chromium, Firefox e WebKit nas rotas de maior risco.

Emulação não substitui aparelho real. A homologação final deve usar ao menos um
telefone Android e, quando disponível, um iPhone/iPad.

### 6.3 Auditorias auxiliares

- Lighthouse para desempenho e verificações automatizadas de acessibilidade.
- axe-core integrado ao navegador para violações detectáveis automaticamente.
- Teste manual de teclado e leitor de tela para semântica e ordem de leitura.

## 7. Sequenciamento e dependências

| Ordem | Etapa | Resultado esperado |
|---:|---|---|
| 0 | Linha de base e instrumentação | Problemas reproduzíveis e medidos |
| 1 | Fundação, acessibilidade e ações | Uso confortável por toque e teclado; base responsiva |
| 2 | Cabeçalho e padrões de estado | Consistência entre páginas |
| 3 | Navegação, filtros, abas e paginação | Menos esforço para circular; melhor uso em telas estreitas |
| 4 | Listas e tabelas resilientes | Semântica clara e fim da dependência de `nth-child` |
| 5 | Formulários e fluxos transacionais | Menos erros de entrada; conclusão em qualquer viewport |
| 6 | Fichas, dashboard e conteúdo complexo | Composições completas e contexto preservado |
| 7 | Feedback, carregamento e recuperação | Operações mais previsíveis |
| 8 | Robustez, desempenho e compatibilidade | Menor custo de manutenção |
| 9 | Homologação | Evidência de qualidade e ausência de regressão |

```text
Linha de base
    ↓
Fundação, acessibilidade e ações
    ↓
Cabeçalho e padrões de estado
    ↓
Navegação, filtros, abas e paginação
    ↓
Listas e tabelas resilientes
    ↓
Formulários e fluxos transacionais
    ↓
Fichas, dashboard e conteúdo complexo
    ↓
Feedback e recuperação
    ↓
Robustez, desempenho e homologação
```

Não iniciar a migração em massa das telas antes de estabilizar os componentes
compartilhados. Cada etapa deve produzir uma entrega utilizável e não pode deixar
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

- 100% das ações operacionais com alvo mínimo de 44 × 44 px.
- 100% dos controles com nome acessível.
- 100% das páginas com o cabeçalho responsivo padronizado.
- 100% dos fluxos críticos concluídos entre 320 e 1440 px, em desktop e celular.
- Zero overflow horizontal no documento em estados homologados.
- Zero lista migrada dependente de `nth-child` para identificar conteúdo.
- Zero `st.dataframe` ou tabela dependente de inversão visual no modo escuro.
- Zero violação crítica ou grave nas auditorias automatizadas acordadas.
- Busca, filtros, paginação e aba preservados ao retornar de uma ficha.
- Redução de seletores dependentes de `nth-child` e do DOM interno do Streamlit.
- Capturas automatizadas para as cinco larguras mínimas.
- Testes Python e de navegador aprovados antes de encerrar cada etapa.

## 10. Fora do escopo

- Alteração das regras de negócio.
- Mudança da identidade visual ou da paleta principal.
- Reescrita do sistema em outro framework frontend.
- Criação de aplicativo móvel nativo.
- Inclusão de funcionalidades comerciais não previstas no projeto.
- Mudança da arquitetura página → serviço → repositório.
- Otimização de consultas ou banco sem relação comprovada com a experiência.
- Suporte a navegadores obsoletos fora da matriz definida.

## 11. Definição de pronto por etapa

Uma etapa só deve ser considerada concluída quando:

1. os critérios de aceite da etapa forem atendidos;
2. houver critérios demonstráveis e teste automatizado proporcional ao risco;
3. o comportamento funcionar a 320, 390, 768, 1024 e 1440 px, quando aplicável;
4. o comportamento for validado nos modos claro e escuro;
5. houver uso por teclado, com foco visível;
6. o componente for testado com dados vazios, normais e extremos;
7. não houver overflow horizontal no documento nem regressão nos fluxos
   diretamente relacionados;
8. os testes existentes (Python e, a partir da Etapa 0, de navegador) passarem;
9. o `Design_UI.md` for atualizado quando surgir ou mudar um padrão;
10. as mudanças forem registradas em commit descritivo, conforme as regras do
    projeto.
