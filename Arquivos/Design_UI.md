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
- **Botões**: ação primária de página = grafite sólido com label; ação por linha de tabela = ícone só (ex.:
  check para "registrar pagamento"); ação destrutiva (encerrar contrato) = contorno vermelho, nunca preenchido.
- **Modais**: usados para formulários únicos (registrar pagamento, encerrar contrato, registrar manutenção,
  novo/regularizar documento, registrar vistoria) — não para fluxos de múltiplas etapas.
- **Assistente (wizard)**: só o "Novo contrato" usa esse padrão — indicador de progresso com círculos numerados
  conectados por linha, navegação Voltar/Avançar.
- **Tabs**: usadas nas fichas (Moto, Cliente, Contrato) e em páginas com múltiplas visões (Cobranças, Manutenção,
  Relatórios) — sublinhado `grafite-900` no item ativo, sem pílula.
- **Tabelas**: hairline entre linhas, sem zebra, sem sombra. Números sempre `mono` e alinhados à direita.
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
