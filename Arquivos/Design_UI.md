# Design de Interface (UI/UX)

> Documento de referência para qualquer sessão futura (Claude Code ou humano) continuar o trabalho de front-end
> definido nesta etapa. Complementa o `Projeto_Locação.md` (que define as telas e regras de negócio) com as decisões
> visuais e de componentes.

**Mockup navegável (fonte visual):** https://claude.ai/artifact/Co75ZTgZrumx8AYTF7TMpc
> Artifact privado do Claude — não é um arquivo do repositório. Para uma sessão nova continuar a partir dele, cole
> esse link na conversa (o Claude consegue ler o conteúdo do Artifact a partir da URL). Ele contém 15 artboards
> navegáveis (clicáveis entre si) cobrindo todas as páginas do plano, com tabs e modais funcionais.

---

## 1. Conceito

O sistema é uma ferramenta de trabalho operacional (não uma landing page): o dono da frota abre para decisão rápida
— quem está atrasado, qual moto precisa de manutenção, o que vence essa semana. A identidade visual nasce do
universo de oficina/moto/estrada, evitando os padrões genéricos de dashboard SaaS (gradientes, sombras pesadas, paleta cream+terracota ou preto+neon).

Conceito central: **painel de instrumentos**. KPIs como leitura tipo odômetro (números grandes em mono), barra de
ocupação da frota como medidor de combustível, selos de status circulares tracejados como adesivo de
vistoria/licenciamento.

## 2. Paleta de cores

| Token | Hex | Uso |
|---|---|---|
| `grafite-900` | `#1E2227` | Sidebar, texto principal, elementos "selecionados/ativos" |
| `grafite-700` | `#2B3036` | Avatar/variações escuras |
| `grafite-500` | `#585F66` | Texto secundário, ícones neutros |
| `grafite-300` | `#9AA0A6` | Texto terciário, placeholders |
| `neblina-50` | `#EEF0F0` | Fundo da página (modo claro) |
| `neblina-0` | `#FAFAF9` | Fundo de cards/painéis |
| `amarelo-farol` | `#F2B705` | Acento da marca **e** status "próxima/a vencer" — nunca usado em botões de ação (fica reservado para sinalizar atenção) |
| `verde-ok` | `#2F9E6E` | Status "em dia / disponível / paga" |
| `vermelho-freio` | `#D64545` | Status "vencida / atrasada / vencido" |
| `cinza-inativo` | `#9AA0A6` | Status "inativa / encerrado" |
| `linha` | `rgba(30,34,39,0.12)` | Bordas hairline (cards, tabelas, divisores) |

Regra: a cor de status é a única que "grita" na interface. Tudo em volta fica neutro (grafite/neblina). Ainda não
existe modo escuro definido — pendente (ver seção 6).

## 3. Tipografia

Duas famílias com motivo funcional, carregadas via Google Fonts:

- **Barlow Semi Condensed** (600/700) — títulos, rótulos de seção. Remete a sinalização viária/placas.
- **IBM Plex Sans** (400/500/600) — texto corrido, tabelas, formulários.
- **IBM Plex Mono** (500/600) — **apenas leituras numéricas** (km, R$, datas, placas). Nunca usado em rótulos ou
  texto decorativo — é funcional, como um odômetro real.

Nunca usar caixa alta em rótulos (exceto os pequenos selos de status, que imitam adesivos reais). Nunca separar
itens com "·" decorativo fora de listas realmente compactas.

## 4. Componentes padrão

- **Sidebar**: fixa, 240px, fundo `grafite-900`. Item ativo com barra esquerda `amarelo-farol` + fundo sutil.
- **Selo de status**: bolinha de 6-8px colorida + texto (tabelas) ou círculo maior com borda tracejada + número
  dentro (alertas do Dashboard/Manutenção) — remete a adesivo de vistoria.
- **Chip de placa**: `mono`, fundo `grafite-900`, texto `neblina-0`, `border-radius: 6px`, letter-spacing.
- **Botões**: ação primária de página = grafite sólido com label; ação destrutiva (encerrar contrato) = contorno
  vermelho, nunca preenchido. Todo controle interativo tem alvo mínimo de 44 × 44 px (`--alvo-min`).
- **Ações por linha** (`botao_acao` em `componentes.py`, Etapa 1 do Plano de melhorias): `st.button(type="tertiary")`
  com ícone Material + texto real. O texto é o nome acessível, o rótulo visível e a dica (`help`, com o alvo: "Abrir a
  ficha da moto ABC-1D23"); desde a Etapa 4 **o texto fica sempre visível** (antes sumia nas listas do desktop),
  porque nenhuma ação pode depender só de ícone ou dica (Pagar, Editar, Abrir, Concluir, Cancelar, Regularizar,
  Comprovante, Atualizar km, Comparar, Selecionar, Remover). A mesma ação usa o
  mesmo texto e ícone em todas as páginas (`ACOES`); nunca um glifo Unicode (`→ ✓ ✎ ›`). "Pagar" é sólido (grafite
  no claro, amarelo no escuro); "Cancelar" é contorno vermelho. Concluir e cancelar são ações distintas, cada uma
  com o próprio botão e diálogo. Retorno das fichas: `botao_voltar("motos", chave)` → "Voltar para motos".
- **Cabeçalho de página** (`cabecalho_pagina` em `componentes.py`, Etapa 2 do Plano de melhorias): todas as páginas
  usam o mesmo componente — sobretítulo opcional, título (h1), descrição/resumo contextual e uma linha
  divisória. A ação primária da página (no máximo uma, ex.: "Nova moto", "Salvar alterações") é passada em
  `acao={"rotulo", "chave", "icone"?, "ajuda"?, "formulario"?}`: é um botão do Streamlit (fora do HTML), primário,
  com ícone Material (`:material/add:` por padrão; nunca `+` no rótulo) e a função devolve `True` ao clicar. No
  desktop fica à direita do título, alinhado à base do texto; quando o cabeçalho tem menos de 34 rem (consulta ao
  contêiner `.st-key-pagina_cabecalho`, não à janela) desce para depois da descrição em largura total. Dentro de
  `st.form`, `"formulario": True` usa o botão de envio. Sem `acao`, o cabeçalho é só HTML (`lateral` aceita um
  indicador contextual, como o do Dashboard). As fichas (moto, cliente, contrato, vistoria) mantêm cabeçalho próprio
  até a Etapa 6.
- **Estados vazios**: sempre dizem o motivo e, quando possível, o próximo passo. `vazio_lista(encontrado, ausente,
  tem_registros, acao)` monta a linha das listas: com registros cadastrados, "Nenhum resultado para o filtro ou a
  busca atual…"; sem registros, "Ainda não há … cadastrados" + "Use “Nova moto”, no topo da página, para cadastrar".
  `tabela_html(..., vazio=...)` aceita o mesmo HTML. Alertas (`st.info/warning/error/success`) seguem o estilo
  único de `[data-testid="stAlert"]` (faixa lateral colorida); o texto específico é revisto na Etapa 7.
- **Foco**: anel de 2 px `--foco` em botões, links, campos, abas, resumos de expander e no rótulo de
  radio/checkbox/toggle, nos dois temas.
- **Modais**: usados para formulários únicos (registrar pagamento, encerrar contrato, registrar manutenção,
  novo/regularizar documento, registrar vistoria) — não para fluxos de múltiplas etapas.
- **Assistente (wizard)**: só o "Novo contrato" usa esse padrão — indicador de progresso com círculos numerados
  conectados por linha, navegação Voltar/Avançar.
- **Navegação lateral** (Etapa 3): o menu do dono é agrupado por área com `st.navigation({seção: [páginas]})`, sem
  mudar nenhuma rota — **Operação** (Dashboard, Contratos, Cobranças), **Cadastros** (Motos, Clientes), **Frota**
  (Manutenção, Documentos, Vistorias), **Gestão** (Relatórios), **Sistema** (Configurações). Os títulos de seção são
  do próprio Streamlit; o item ativo mantém a barra `amarelo-farol` nos dois temas. O locatário continua com um
  menu de um item. *Ação rápida "Novo contrato" persistente na barra lateral: avaliada e não adotada* — "Novo
  contrato" já é a ação primária do cabeçalho de Contratos (a um clique do menu) e um botão fixo competiria com
  os alertas do Dashboard e com as ações destrutivas; reavaliar se a medição de uso mostrar o contrário.
- **Filtros e busca** (`barra_filtros` em `src/ui/listas.py`): pílulas nativas do Streamlit (`st.pills`, grupo
  `radiogroup` com `aria-checked`) que **quebram de linha** em vez de empilhar em colunas; alvo de 44 px, rótulo
  inteiro (`Alugada · 9`, contagem no rótulo) e o filtro escolhido leva um **check** além do preenchimento
  (grafite no claro, amarelo no escuro), então não depende só da cor. Não há como desmarcar: sempre existe um filtro
  (o "padrão" da lista — `Todas`, ou `Ativo` em Contratos). A busca é o `st.text_input` com ícone de lupa: só
  aplica com Enter ou ao sair do campo (nunca a cada tecla). No desktop a busca fica ao lado das pílulas; no celular
  (≤ 640 px) desce para linha própria. Abaixo da barra, `filtros.resumo(n, ("moto", "motos"))` mostra **quantos
  resultados** restaram, os **filtros ativos** como chips de texto (`Situação: Alugada`, `Busca: “pop”`) e o botão
  **Limpar filtros** (uma ação: filtro padrão, sem busca, página 1), que só aparece com filtro ativo.
- **Paginação** (`paginar` + `rodape_paginacao`): `Anterior`, "Mostrando 11 a 20 de 23 · página 2 de 3", `Próxima` e
  seletor "Itens por página" (10, 25 ou 50; padrão 10). Sem `number_input`. O rodapé some enquanto tudo cabe em 10
  itens. A página volta a 1 quando o filtro, a busca ou os itens por página mudam, e é corrigida se a lista encolher.
  No celular os dois botões dividem a linha e o seletor ocupa a linha de baixo. A aritmética é pura, em
  `src/domain/paginacao.py`.
- **Contexto preservado**: filtro, busca, itens por página, página e aba ficam em `st.session_state`
  (`persist_state="session"` nos widgets), por isso abrir uma ficha (ou outra página) e voltar devolve a lista como
  estava. Uma ficha nova volta à primeira aba (`reiniciar_abas`). *Limite*: a posição de rolagem não é preservada
  (o Streamlit não a expõe); a página, o filtro e a busca são.
- **Abas** (`abas` + `aba_ativa` em `src/ui/listas.py`): `st.tabs` nativo com estado (`on_change="rerun"`), usado nas
  fichas (Moto, Cliente, Contrato) e nas páginas com várias visões (Cobranças, Manutenção, Relatórios). Estratégia
  única: (1) **as abas quebram de linha** em telas estreitas, nenhuma some fora da área visível (o indicador
  deslizante e as setas de rolagem foram desligados; a ativa é marcada por sublinhado de 3 px e negrito, `--texto` no
  claro e `--marca` no escuro); (2) a **aba ativa é lembrada** entre execuções, inclusive quando o rótulo muda de
  contagem (`Hoje · 3` → `Hoje · 2` após registrar um pagamento) e na volta de outra página; (3) **só o conteúdo da
  aba ativa executa** (`if aba_ativa(guia): …`), o que também evita consultas das abas ocultas.
- **Listas interativas** (`src/ui/registros.py`, Etapa 4): todo conjunto de registros com ação (Motos, Clientes,
  Contratos, Cobranças, Documentos, Manutenção — histórico e catálogo —, Vistorias, "Hoje" do Dashboard, contratos na
  ficha do cliente, documentos na ficha da moto e as opções do assistente de contrato) é uma lista de **cartões**:
  identidade (placa ou nome + selo de situação), **dados rotulados** (`<dl>`, rótulo pequeno em cima do valor) e um
  **grupo de ações**. Estrutura por chaves de container (`lista_<prefixo>` > `reg_<prefixo>_<id>` >
  `regacoes_<prefixo>_<id>`) e classes (`.registro__id`, `.registro__campo`, `.registro__rotulo`, `.registro__valor`):
  nada de `nth-child` nem de coluna posicional, então reordenar campos no Python não associa o conteúdo ao rótulo
  errado. `lista_registros(prefixo, acoes=N)` reserva a coluna de ações no desktop para os dados alinharem entre as
  linhas. Layout por **container query** (largura do cartão da lista, também vale em janela dividida): ≥ 1000 px
  uma linha só (identidade | dados | ações, ~70 px de altura); até 1000 px as ações sobem ao lado da identidade e os
  dados vão para a linha de baixo; até 560 px tudo empilha, com as ações **logo abaixo da identidade**. Sem rolagem
  horizontal no documento (conferido de 320 a 1600 px). `estado="selecionado"|"indisponivel"` serve às listas de
  escolha (assistente): barra lateral + botão "Selecionado" com ícone, nunca só a cor. Dado tabular sem ação não é
  cartão: é `tabela_html`.
- **Tabelas somente leitura** (`tabela_html(cabecalhos, linhas, legenda=...)`): `<th scope="col">`, `role` explícito
  em table/row/columnheader/cell (a semântica sobrevive quando o CSS, no celular, transforma cada linha em cartão e
  esconde o cabeçalho só visualmente), `legenda` como nome acessível e cabeçalho `""` para coluna decorativa (barra
  de proporção, `aria-hidden`). Overflow lateral localizado só se uma tabela precisar comparar colunas (hoje nenhuma).
- **Sem canvas**: `st.dataframe` e `st.data_editor` não são usados — não seguem o tema escuro nem o celular. As peças
  e serviços extras do registro de manutenção são linhas de campos (Descrição, Quantidade, Valor unitário) com
  "Remover" e "Adicionar peça ou serviço".
- **Tabelas**: hairline entre linhas, sem zebra, sem sombra. Números sempre `mono` e alinhados à esquerda, sob o cabeçalho da coluna (decisão de 25/09/2026, valores monetários incluídos). Selos de status com largura única (104px, `--selo-largura`) e texto curto.
- **Barras/medidores**: usadas em vez de gráficos de biblioteca — barra de ocupação segmentada (Dashboard), barra
  proporcional em Relatórios. Mantém a página autocontida em HTML/CSS puro.

## 5. Páginas construídas (15 artboards)

| Página | Arquivo no Artifact | Observações |
|---|---|---|
| Dashboard | `Main.dc.html` | Faixa de instrumentos + Hoje + Alertas |
| Motos — lista | `Motos.dc.html` | Filtros por status, paginação |
| Motos — ficha | `MotoFicha.dc.html` | 6 abas (Resumo, Plano, Histórico, Documentos, Contratos, Financeiro) |
| Clientes — lista | `Clientes.dc.html` | CPF mascarado, alerta de CNH |
| Clientes — ficha | `ClienteFicha.dc.html` | 3 abas (Resumo, Contratos, Pagamentos) |
| Contratos — lista | `Contratos.dc.html` | — |
| Contratos — novo | `ContratoNovo.dc.html` | Assistente em 4 etapas, totalmente navegável |
| Contratos — ficha | `ContratoFicha.dc.html` | 3 abas + modal de encerramento |
| Cobranças | `Cobrancas.dc.html` | 4 abas, cálculo de encargos ao vivo, modal de pagamento |
| Manutenção | `Manutencao.dc.html` | 3 abas (Alertas, Histórico, Catálogo) + modal de registro |
| Documentos | `Documentos.dc.html` | Modal de novo documento + modal de regularização |
| Vistorias — lista | `Vistorias.dc.html` | + modal de registro (checklist completo) |
| Vistorias — comparação | `VistoriaComparacao.dc.html` | Entrega x devolução lado a lado |
| Relatórios | `Relatorios.dc.html` | 4 abas (Resultado, Manutenção, Inadimplência, Fluxo de caixa) |
| Configurações | `Configuracoes.dc.html` | Encargos, alertas, backup manual |

## 6. Pendências conhecidas

1. A tela de login foi validada em 390 × 844 px. As telas autenticadas ainda precisam de validação mobile no
   ambiente de homologação com a conta do proprietário.
2. Os dados de exemplo usados no mockup são fictícios e não foram reconciliados matematicamente entre todas as
   telas (ex.: um mesmo cliente pode aparecer com valores ligeiramente diferentes em telas distintas) — servem
   para validar o padrão visual, não como fonte de verdade numérica.

Concluído em 22/09/2026: modo escuro no painel autenticado; navegação direta das fichas de Moto e Cliente para o
contrato selecionado; tabela dinâmica para adicionar ou remover várias peças e serviços livres no registro de
manutenção.

## 7. Como continuar em outra sessão

1. Cole o link do Artifact (seção 1) na conversa para o Claude reabrir o mockup e ler o HTML de cada tela.
2. Leia este arquivo para recuperar paleta, tipografia e padrões de componente sem precisar re-perguntar.
3. Ao implementar de verdade em Streamlit, os tokens de cor/tipografia daqui devem virar CSS custom injetado
   (`st.markdown(..., unsafe_allow_html=True)` ou arquivo `.css` próprio), já que Streamlit não usa HTML puro.

## 8. Design system (modernização de 24/09/2026)

Evolução visual, sem trocar a identidade: cards e modais mais arredondados, tipografia com hierarquia mais clara e
tudo centralizado em tokens (`src/ui/estilos.css`; modo escuro em `src/ui/estilos_escuro.css`).

- **Raios**: `sm` 6px (chips, botões de ação), `campo` 8px (inputs, botões), `md` 10px (tabelas, listas), `lg` 14px
  (cartões, KPIs), `xl` 18px (modais). Sombras só de sussurro; a hierarquia vem da borda.
- **Escala tipográfica**: display 28–38px (mono), título de página 30px, seção 18px, subtítulo 16px, corpo 14,5px,
  secundário 13px, legenda 12px (mínimo). O rótulo dos KPIs é em caixa alta (decisão desta revisão; o restante
  continua sem caixa alta).
- **Espaçamento**: 4, 8, 12, 16, 24, 32, 40, 48px (`--e1` a `--e8`).
- **Estados**: `sucesso`, `alerta`, `perigo`, `info`, `neutro`, cada um com cor cheia, cor de texto (contraste
  ≥ 4,5:1) e fundo suave. Selo = bolinha + texto (nunca só cor).
- **Botão primário**: grafite no claro, amarelo no escuro (o amarelo continua fora dos botões no tema claro).
- **Foco**: contorno de 2px na cor `--foco` (visível nos dois temas).
