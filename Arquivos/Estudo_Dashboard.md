# Estudo: como se faz um bom dashboard, e o que isso muda no nosso (05/11/2026)

> Estudo para orientar a reformulação do Dashboard (`/`). Parte 1: o que a literatura e os produtos profissionais ensinam.
> Parte 2: como isso se aplica a locação de motos. Parte 3: diagnóstico do Dashboard atual, com medições. Parte 4: proposta de
> redesenho. **Nada foi implementado ainda.** As decisões do dono sobre a proposta estão na seção 4.9 (05/11/2026); nenhuma fase foi iniciada.
>
> **Sobre as fontes.** Pesquisei na web em 05/11/2026. As fontes primárias são poucas (Stephen Few, WCAG, Carbon, NN/g, Cleveland e McGill via
> resumos). O resto é prática de blogs e fornecedores: serve como heurística, não como regra. Onde um número vem de fornecedor
> (metas de utilização, custo de parada), digo isso e não o trato como fato. A lista completa de links está na parte 5.

---

## 1. O que a literatura e os produtos profissionais ensinam

### 1.1 O que é um dashboard (e o que não é)

- **Definição de Stephen Few** (*Information Dashboard Design*): "uma exibição visual das informações mais importantes para atingir um ou mais objetivos,
  consolidadas e organizadas numa única tela, para serem monitoradas num relance". Ele descreve o uso em três passos: **(1) ver o quadro geral,
  (2) focar nos itens que pedem atenção, (3) aprofundar rápido na informação necessária para agir**. Os passos 1 e 2 dependem de design visual; o 3, de
  atalhos para o detalhe.
- **Tipos** (Few): **estratégico** (saúde geral, estático, para dirigentes), **operacional** (atividade do dia a dia, chama a atenção quando um valor
  passa do limite, precisa de drill-down) e **analítico** (exploração, com contexto, comparação e histórico). Um painel que mistura os três vira uma
  tela longa que não serve a nenhum deles.
- **NN/g:** dashboard é uma visão de página única para entender o essencial num relance e **agir rápido**; não é para exploração aberta. Operacional
  = decisões sensíveis ao tempo; analítico = análise menos urgente.
- **As 13 armadilhas de Few** (resumo): passar da fronteira de uma tela; dar contexto insuficiente aos dados; mostrar detalhe ou precisão em excesso;
  expressar medidas indiretamente; escolher a mídia errada; variedade sem sentido; mídias mal desenhadas; codificar quantidades de forma imprecisa;
  organizar mal os dados; não destacar o que importa; poluir com decoração inútil; usar cor demais ou errada; visual pouco atraente.

### 1.2 Hierarquia, leitura e espaço

- **O mais importante em cima e à esquerda; mais contraste e mais área para o que mais importa** (Carbon). A atenção cai ao longo de uma linha de cartões
  iguais: do quinto em diante quase ninguém lê (heurística de blogs de UX; vale como cautela, não como medida).
- **Ranquear por importância** e remover o que distrai. Perguntar: *quais 3 a 5 perguntas o usuário precisa responder em menos de 10 segundos?*
  Se o painel mostra tudo, não responde nada.
- **Espaço em branco agrupa e dá prioridade** (Carbon; o ganho de "20% de compreensão" citado lá vem de um estudo da Human Factors International, que
  não verifiquei). Agrupar por proximidade e por forma (Gestalt) antes de usar cor.
- **Teste de relance:** em poucos segundos o usuário diz onde está e o que fazer a seguir? Se não, a hierarquia falhou.
- **Divulgação progressiva:** resumo primeiro, fatores em seguida, registros brutos no fim; no celular, poucas colunas sempre visíveis e o resto
  recolhido; evitar rolagem horizontal da tabela inteira.

### 1.3 Anatomia de um cartão de indicador (KPI)

- **Número grande + rótulo curto** (o rótulo é uma palavra ou poucas, não uma frase). Em volta dele: o **contexto** que dá sentido: comparação com o
  período anterior, meta ou previsto.
- **Delta (variação):** mostrar a direção real e **colorir pelo resultado, não pelo sinal**: queda de atraso é boa (verde), queda de receita é ruim
  (vermelho). Escolher a base da comparação conforme a pergunta (período anterior, ou acumulado).
- **Sparkline** (Tufte, *Beautiful Evidence*): gráfico do tamanho de uma palavra, sem eixos, ao lado do número, só para a **tendência**; a leitura exata
  fica no número. Cuidado com eixo que não começa no zero, que exagera a tendência.
- **Bullet graph** (Few): barra horizontal com o valor, um marcador de meta e faixas de qualidade (tons de uma só cor). Substitui o velocímetro: ocupa
  pouco, mostra o valor contra a meta. Não serve para tendência nem parte-do-todo.
- **Dado ausente não é zero:** "sem dados" no cartão, nunca "R$ 0" (blogs de dashboard; também é honestidade com o dono).
- **Um nome, uma definição, um lugar:** o mesmo indicador não pode aparecer com valores diferentes em dois pontos da tela (ver a parte 3).

### 1.4 Escolha de gráficos

- **Ranking de precisão** (Cleveland e McGill, 1984): posição num eixo comum > posição em eixos não alinhados > comprimento > ângulo e área > cor.
  Reavaliações posteriores relativizam a ordem exata, mas o essencial se mantém: **barras e linhas vencem pizzas e áreas**.
- **NN/g:** barras para comparar, linhas para tendência, dispersão para relação, **bullet** para valor contra meta; **pizza e rosca só quando uma
  categoria domina**; evitar 3D, treemap em painel de ação, **velocímetro**; ordenar barras; não usar cor para magnitude; cor nunca sozinha.
- **Tufte:** razão dado-tinta e eliminação de "chartjunk". Útil como filtro (cada pixel carrega dado?), sem virar dogma: um gráfico minimalista não é
  automaticamente claro.
- **Rótulo direto no gráfico** em vez de legenda longa; tooltips repetem os valores; anotações destacam picos e quedas sem cobrir os dados.

### 1.5 Cor e acessibilidade (WCAG 2.2)

- **1.4.1 Uso de cor (A):** a cor não pode ser o único meio de transmitir a informação. Dupla codificação: cor + forma, rótulo ou padrão.
- **1.4.11 Contraste não textual (AA):** objetos gráficos necessários (barras, linhas, ícones) pedem **3:1** contra o fundo; o limite é estrito
  (2,999 reprova). Fatias de pizza só dispensam o contraste se houver rótulo e valor visíveis.
- **1.4.3 Contraste de texto:** 4,5:1 (3:1 para texto grande), inclusive o texto dentro de gráficos.
- **Cor reservada para significado:** o que é neutro fica neutro; a cor "grita" só no que pede ação (vermelho, âmbar, verde). Cores consistentes por
  conjunto de dados em todo o painel.
- Teste prático: ver em escala de cinza; oferecer **tabela ou texto alternativo** para cada gráfico; ferramentas automáticas pegam cerca de 30% dos
  problemas, o resto é revisão manual.

### 1.6 Estados e honestidade

- Todo bloco precisa de **quatro estados**: carregando (esqueleto com a forma final, para o layout não pular), vazio (com próximo passo, e diferente de
  "sem resultado do filtro"), erro (linguagem simples, tentar de novo, **só o bloco afetado falha**) e sucesso.
- Respeitar `prefers-reduced-motion`; anunciar mudança de estado a leitores de tela.

### 1.7 Padrões que os produtos profissionais repetem

- **Caixa de entrada de atenção** ("o que precisa de você agora") no topo, com severidade e **botão de ação na própria linha** (modelos de painéis de
  frota: Reflex, MotoLogic, Fleetio, Fleet Chaser).
- **Horizonte de manutenção em três faixas:** atrasado, a vencer, depois.
- **Visões por papel** e **drill-down em um clique** a partir de qualquer número.
- **Aging (envelhecimento) de recebíveis:** totais por faixa de atraso, com contagem, % do total e **ação sugerida por faixa**; âmbar nas faixas médias e
  vermelho nas antigas. Idade não é o único critério: valor e chance de receber também pesam. Definir se a idade conta pelo vencimento ou pela emissão.

---

## 2. O que isso significa para locação de motos

### 2.1 O que o dono precisa decidir todo dia (e portanto o que o painel responde)

1. **Quem tem que pagar hoje, e quem já deveria ter pago?** → cobrar (ligar, mandar mensagem, registrar pagamento).
2. **Tem dinheiro?** → caixa do mês, o que entra nos próximos dias, parcelas de dívida a vencer.
3. **Qual moto está parada e por quê?** → disponível, em manutenção, sem contrato, documento vencido.
4. **O que vai dar problema?** → IPVA, CNH, manutenção, contrato acabando, parcela de dívida.
5. **O negócio está melhor ou pior que o mês passado?** → receita, resultado, atraso.

Ordem de importância sugerida: 1 → 4 → 3 → 2 → 5. A pergunta 1 é diária; a 5 é semanal ou mensal.

### 2.2 Indicadores do setor (com a ressalva das fontes)

| Indicador | Definição usada pelo setor | Observação |
|---|---|---|
| **Utilização** | dias alugados ÷ dias disponíveis × 100 | Metas citadas (75 a 80%, ou acima de 80%) vêm de fornecedores; só utilização engana, então pareie com receita por veículo |
| **Receita por veículo disponível** (RevPAU, RevPAVD) | receita de locação ÷ dias-veículo disponíveis | Combina preço e ocupação; um ganho de 1% de utilização "valer 1,5 a 2% de receita" é alegação de fornecedor, não verificada |
| **Tempo parado** (downtime) | dias em reparo ÷ dias disponíveis | Meta "abaixo de 5%" aparece em fornecedores; o custo por dia parada varia muito entre fontes |
| **Inadimplência por faixa** | total em aberto por faixa de atraso | Em vez de um número só: 1-30, 31-60, 61-90, 90+ (padrão de contas a receber); com cobrança **semanal** as faixas devem ser mais curtas |
| **Custo de manutenção por km** | custo ÷ km rodados | Compara veículos e modelos; acompanhar **preventiva × corretiva** (muita corretiva = "apagando incêndio") |
| **Conformidade de manutenção preventiva** | % de itens do plano em dia | Já existe o plano por moto no sistema |

Para o nosso caso (poucas dezenas de motos, cobrança semanal ou mensal, Pix, WhatsApp), os de maior retorno são: **inadimplência em faixas curtas**,
**utilização/ocupação**, **receita por moto**, **tempo parado** e **o previsto dos próximos 7 dias**. Custo por km depende de ter km e manutenção
registrados com regularidade, então entra depois.

### 2.3 O que a planilha PAGAMENTO MOTOS já resolvia bem (e vale manter)

Faixa de 7 indicadores financeiros no topo; faixa de 7 da frota; evolução de 6 meses; entradas por conta; ranking de quem deve; **alertas com
semáforo**. Pontos fracos dela, que o sistema não deve repetir: números iguais em lugares diferentes, parcelas possivelmente contadas duas vezes,
corte de atraso fixo, e meses zerados exibidos como se fossem resultado real.

---

## 3. Diagnóstico do Dashboard atual

Medido no preview com os dados do dev (05/11/2026), tema escuro.

### 3.1 Medições

| Medida | Desktop (977 px) | Celular (375 px) |
|---|---|---|
| Altura da página | 8.280 px, **10,3 telas** | 13.125 px, **15,9 telas** |
| Cartões de indicador (KPI) | 17 | 17 |
| Tabelas | 6 | 6 |
| Seções e cartões principais | 10 | 10 |
| Botões de ação na página | — | 12 |

Few: "exceder a fronteira de uma tela" é a primeira armadilha. Aqui, o essencial (quem cobrar hoje) está a uma tela do topo, mas o painel inteiro
exige 10 a 16 telas de rolagem.

### 3.2 Estrutura atual (de cima para baixo)

1. Título, data e **dois botões grandes** (modo compacto, ocultar dados).
2. 4 indicadores: Frota, Recebido no mês, Em atraso, Manutenção no mês.
3. **Hoje** (lista de cobranças, 7 de 24).
4. Ocupação da frota (rosca + legenda) e **Precisa de atenção** (alertas).
5. **Financeiro · mês** (seletor) com 13 indicadores em duas faixas.
6. Últimos 6 meses (gráfico + tabela) e **Quem está devendo**.
7. Entradas por conta e Despesas por categoria.
8. Resultado por veículo e **Alertas e pendências**.

### 3.3 Problemas, por gravidade

**A. Números que se contradizem (quebra a confiança; é o problema mais sério).**

| O que aparece em cima | O que aparece embaixo |
|---|---|
| Recebido no mês **R$ 1.303** | Receita **R$ 1.128** (mesmo mês) |
| Em atraso **R$ 6.676**, "8 clientes atrasados" | Em atraso **4** + Inadimplentes **4** (mesmos 8, sem o valor por faixa) |
| Gasto com manutenção **R$ 0** | Despesas por categoria: Manutenção **R$ 1.105** |
| Ocupação 76% (26 de 34 **ativas**) e "Frota 38 motos" | Dois denominadores diferentes na mesma tela |
| "Dívidas em aberto R$ 17.042" com "motos fiado R$ 0,00" | Rótulo lê como zero, mas é "sem dívida desse tipo" |

Causa provável: o topo ainda usa o cálculo antigo (relatórios por moto, que soma `abatimento` e usa só `manutencoes`) e o bloco financeiro usa as
RPCs novas. **Dois cálculos para o mesmo conceito.**

**B. Duplicação.** "Em atraso R$ 6.676" aparece em 3 lugares (indicador do topo, "A receber" e a lista "Quem está devendo"). **Hoje** e **Quem está
devendo** listam as mesmas pessoas. **Precisa de atenção** e **Alertas e pendências** são duas caixas de alertas. A ocupação aparece em 3 formas
(indicador, rosca, tabela da legenda).

**C. Ordem que não segue a decisão.** O Financeiro (analítico, mensal) fica **depois** da lista de cobrança (operacional, diária), tudo na mesma
rolagem, sem separação. O seletor de mês só vale para o bloco financeiro, mas está no meio da página, e quem o usa pode achar que o topo mudou
também. No celular, a primeira tela é ocupada por dois botões de configuração, antes de qualquer número.

**D. Hierarquia plana.** São 17 cartões do mesmo peso. O que pede ação (inadimplentes, caixa negativo) não se destaca do que só informa. O único
destaque é a borda vermelha de "Em atraso". O Caixa de **−R$ 10.978** assusta, mas decorre de um investimento de R$ 10.845 em veículo: o número
é correto e a leitura é enganosa sem contexto.

**E. Gráficos com pouca informação por pixel.** O gráfico de colunas repete a tabela logo abaixo; três meses seguidos com os mesmos R$ 520
parecem dado, mas são ausência de histórico; a rosca da ocupação divide só 4 categorias e repete a legenda ao lado (NN/g: rosca só quando uma
categoria domina). Faltam: **tendência junto ao número**, **meta ou previsto** contra o realizado (existe "de R$ 15.650 previstos" em texto, sem
barra comparativa no financeiro), e **faixas de atraso**.

**F. Perguntas que o painel não responde.** O que **entra nos próximos 7 dias**; **próximas parcelas de dívida**; **contratos que acabam**; qual
**moto está parada** e há quanto tempo; **como cobrar** (a mensagem de WhatsApp existe em Cobranças, mas não aparece no painel); o que **mudou desde ontem**.

**G. Estados e acessibilidade.** O painel inteiro cai se a leitura principal falha (só o bloco financeiro tem aviso). Não há esqueleto de
carregamento. O gráfico de colunas depende de verde e vermelho (WCAG 1.4.1: há a tabela, que é a alternativa correta, mas o gráfico em si não
tem rótulo direto). Vários botões "Pagar" de mesmo peso competem entre si.

**H. O que já está bom (manter).** Visual escuro e claro coerentes; tipografia numérica em mono; placa como chip; selos de situação; modo de ocultar
dados (útil para mostrar a tela a terceiros); estados vazios claros; tabelas que viram cartões no celular; gráficos em SVG, sem
dependência de JavaScript.

---

## 4. Proposta de redesenho

### 4.1 Princípios

1. **Um painel, três camadas** (Few): **Hoje** (operacional, cabe numa tela), **Dinheiro** (mensal) e **Frota**. Cada camada responde a um conjunto de
   perguntas; o resto é drill-down.
2. **O que pede ação sobe; o que só informa desce.** Cor forte só em quem exige decisão.
3. **Um indicador, uma definição, um lugar.** Toda a tela lê das mesmas fontes (as RPCs novas); o cálculo antigo sai do Dashboard.
4. **Todo número tem contexto:** variação contra o período anterior (colorida pelo resultado) e, quando faz sentido, o previsto ou a meta.
5. **Menos tipos de gráfico, mais clareza:** barras, linhas, sparkline e bullet. Sem rosca, sem velocímetro.
6. **Desktop primeiro, celular funcional:** o uso principal será no computador (decisão 4); no celular a primeira tela ainda deve responder "quem cobrar hoje".
7. **Honestidade de dados:** "sem dados" nunca vira zero; mês sem histórico fica claramente marcado; o caixa mostra o que o move.

### 4.2 Estrutura (wireframe em texto)

```
┌ Dashboard · quinta, 5 de novembro ─────────────── [ Hoje | Dinheiro | Frota ]   ⋯ (ocultar dados, compacto)
│
│  CAMADA "HOJE"  (cabe em uma tela no desktop)
│  ┌ A cobrar ┐ ┌ Atraso ──────────────┐ ┌ Frota ─────────────┐ ┌ Caixa do mês ┐
│  │ R$ …     │ │ R$ …                 │ │ 26 alugadas        │ │ R$ …         │
│  │ hoje + … │ │ [1-6d|7-14d|15-30|31+]│ │ ███████░░ 6 livres │ │ ▁▂▃▅▆ vs mês │
│  └──────────┘ └ barra de faixas ─────┘ └ 2 em manutenção ───┘ └──────────────┘
│
│  ┌ Cobrar agora ──────────────────────────┐ ┌ Atenção ───────────────────────┐
│  │ 1 lista só (une "Hoje" + "Quem deve"), │ │ 1 caixa só (une os 2 alertas):  │
│  │ priorizada por atraso e valor.         │ │ documento vencido · CNH ·       │
│  │ Linha: cliente · moto · dias · valor   │ │ manutenção · parcela de dívida  │
│  │ [Pagar] [WhatsApp]   ver todas →       │ │ a vencer · contrato acabando    │
│  └────────────────────────────────────────┘ └─────────────────────────────────┘
│  ┌ Próximos 7 dias ───────────────────────────────────────────────────────────┐
│  │ entra: R$ … (n cobranças)   sai: R$ … (parcelas de dívida)   saldo previsto │
│  └─────────────────────────────────────────────────────────────────────────────┘
│
│  CAMADA "DINHEIRO"  (seletor de mês só aqui)
│   Receita vs previsto (bullet) · Despesas · Resultado · Caixa (com "do qual investimento")
│   Evolução 6 meses (colunas + linha do caixa, rótulo direto) · Entradas por conta · Despesas por categoria
│   Dívidas: saldo, próximas parcelas, atrasadas
│
│  CAMADA "FROTA"
│   Situação (barra única segmentada, rótulo direto) · Motos paradas (há quantos dias) · Ranking de resultado
│   (5 melhores / 5 piores) · Manutenção (preventiva × corretiva, em dia)
```

- **Abas "Hoje | Dinheiro | Frota"** (progressive disclosure): cada aba cabe em cerca de uma tela no desktop. A aba padrão é Hoje. Funciona sem
  JavaScript (cada aba tem URL própria: `/?aba=dinheiro`), no padrão que o projeto já usa em outras páginas.
- **O seletor de mês passa para a aba Dinheiro**, onde de fato vale. O resto do painel é "hoje".
- **"Modo compacto" e "ocultar dados" saem do cabeçalho** e viram um menu discreto (⋯) ou ícones; ocultar dados continua sem expor nada no HTML.

### 4.3 Os quatro indicadores do topo (decidido em 05/11/2026)

| # | Indicador | Por quê | Contexto no cartão |
|---|---|---|---|
| 1 | **A cobrar** (vencendo hoje + em atraso) | é a pergunta diária nº 1 | quantos contratos; variação desde a semana passada |
| 2 | **Atraso por faixa** (barra empilhada 1-6, 7-14, 15-30, 31+ dias) | substitui "Em atraso" + "Inadimplentes" + rosca; mostra **onde** está o problema | R$ por faixa; a faixa de inadimplência segue a configuração |
| 3 | **Frota** (alugadas, livres, em manutenção, inativas numa barra só) | substitui a rosca e os 3 números repetidos | ocupação = alugadas ÷ ativas, **um só denominador**, dito na tela |
| 4 | **Caixa do mês** | o dono quer saber se "dá" | sparkline de 6 meses e "do qual investimento R$ …" para explicar o negativo |

### 4.4 Novos indicadores (todos calculáveis com o que já existe)

- **Próximos 7 dias:** cobranças a vencer (entra) e parcelas de dívida a vencer (sai).
- **Motos paradas:** há quantos dias estão sem contrato ou em manutenção.
- **Receita por moto disponível (mês)** e **tempo parado (%)**, como no setor.
- **Atenção unificada:** documento, CNH, manutenção, parcela de dívida a vencer e contrato terminando, numa lista só, com severidade.

### 4.5 Mapa antes → depois

| Hoje | Depois |
|---|---|
| Recebido no mês (cálculo antigo) | Some: vale a Receita das RPCs novas, dentro de A cobrar e Caixa |
| Em atraso (R$) + Em atraso (n) + Inadimplentes (n) | Uma barra por faixa de atraso |
| Gasto com manutenção (cálculo antigo) | Aba Frota (preventiva × corretiva) |
| Hoje + Quem está devendo | **Cobrar agora** |
| Precisa de atenção + Alertas e pendências | **Atenção** |
| Rosca de ocupação + legenda | Barra única segmentada com rótulo direto |
| Financeiro (13 cartões, 3 faixas) | Aba Dinheiro, com 4 cartões e o resto em blocos |
| Tabela dos 6 meses + gráfico repetido | Um gráfico com rótulo direto; a tabela vira "ver os números" |
| Resultado por veículo (tabela) | Aba Frota: 5 melhores e 5 piores |

### 4.6 Qualidade (itens de aceite)

- Nenhum indicador aparece com dois valores; um teste compara as fontes.
- Desktop: a aba Hoje cabe em uma tela. Celular (uso secundário, mas não descartado): a primeira tela traz A cobrar + Atraso por faixa + os primeiros itens de Cobrar agora, sem botões de configuração à frente.
- Contraste 3:1 nos elementos gráficos e 4,5:1 no texto, nos dois temas; nenhum significado só por cor (faixas com rótulo e padrão).
- Esqueleto por bloco e erro só no bloco afetado; "sem dados" ≠ R$ 0.
- Mesmas funções do domínio, testadas (`src/domain`), sem lógica na rota; gráficos continuam em SVG sem script e sem estilo inline (política de conteúdo).
- Navegação por teclado e leitor de tela nas abas e nas listas.

### 4.7 Riscos e custo

- **Maior:** unificar os cálculos (parte 3.A). É a mudança de maior valor e a de maior cuidado: o topo atual usa `relatorios` e precisa passar a usar as RPCs
  do financeiro. Os relatórios por moto continuam como estão (fora do Dashboard).
- **Médio:** as faixas de atraso e o previsto dos próximos 7 dias precisam de consultas novas (uma RPC de leitura nova, sem escrita).
- **Menor:** abas, reorganização e gráficos são só tela.

### 4.8 Faseamento sugerido

1. **Fase 1, só verdade e ordem:** unificar os números, juntar as duas listas e as duas caixas de alertas, tirar os botões do topo, abas Hoje/Dinheiro/Frota.
2. **Fase 2, contexto:** variação e sparkline nos cartões, barra de faixas de atraso, barra segmentada da frota, bullet de receita contra previsto.
3. **Fase 3, o que falta:** próximos 7 dias, motos paradas, receita por moto, tempo parado, WhatsApp na lista.

### 4.9 Decisões do dono (05/11/2026)

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Abas ou rolagem única? | **Abas** (Hoje, Dinheiro, Frota), com Hoje como padrão |
| 2 | Os 4 indicadores do topo | **Aprovados**: A cobrar, Atraso por faixa, Frota e Caixa do mês |
| 3 | Faixas de atraso | **Servem**: 1-6, 7-14, 15-30 e 31+ dias; o corte de inadimplência continua configurável |
| 4 | Computador ou celular | O uso será **principalmente no computador**, sem descartar o celular: projetar desktop primeiro, com o celular funcional |
| 5 | Ação na lista Cobrar agora | **"Pagar" e "WhatsApp"** (a mensagem de cobrança já existe em Cobranças) |
| 6 | Cálculo antigo no Dashboard | **Pode sair**: o Dashboard passa a ler só das RPCs do financeiro; os relatórios por moto seguem como estão |

**Combinado:** só documentar as decisões por enquanto. **Nenhuma fase (4.8) foi iniciada**; a Fase 1 começa quando o dono mandar.

**O que cada decisão muda no projeto da Fase 1:**
- **Abas** (1): cada aba tem URL própria (`/?aba=hoje|dinheiro|frota`), funciona sem JavaScript e mantém `mes`, `compacto` e `ocultar` na navegação; o seletor de mês vive só na aba Dinheiro.
- **Faixas** (3): nova regra pura em `src/domain/financeiro.py` (faixa por dias de atraso, com os limites 6, 14 e 30 em constante nomeada), testada nas fronteiras (dia 6/7, 14/15, 30/31).
- **Desktop primeiro** (4): a aba Hoje é desenhada para caber numa tela de computador (por volta de 1366×768 ou maior); no celular as colunas viram uma só, na ordem de leitura acima.
- **WhatsApp** (5): a lista reaproveita a rota e a mensagem de `cobrancas_mensagem`; é um link por linha, sem enviar nada sozinho.
- **Sem cálculo antigo** (6): `dados_painel.carregar` deixa de usar `services.dashboard.resumo` para receita e manutenção; um teste garante que nenhum indicador aparece com dois valores.

---

## 5. Fontes

**Principais (autoria identificável):**
- Stephen Few, *Common Pitfalls in Dashboard Design* (Perceptual Edge, 2006): definição de dashboard, os 3 passos de uso e as 13 armadilhas. https://www.perceptualedge.com/articles/Whitepapers/Common_Pitfalls.pdf
- Stephen Few, *Information Dashboard Design* (2ª ed., Analytics Press, 2013): bullet graphs, sparklines e tipos de dashboard (via resumos). https://www.theinformationlab.co.uk/community/blog/information-dashboard-design-stephen
- Nielsen Norman Group, *Dashboards: Making Charts and Graphs Easier to Understand*. https://www.nngroup.com/articles/dashboards-preattentive/
- IBM Carbon Design System (v10), *Data visualization: Dashboards*. https://v10.carbondesignsystem.com/data-visualization/dashboards
- W3C, *Understanding SC 1.4.11 Non-text Contrast* (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- Cleveland e McGill (1984), ranking de tarefas perceptivas (via resumo): https://flowingdata.com/2010/03/20/graphical-perception-learn-the-fundamentals-first
- Tufte (razão dado-tinta; sparklines em *Beautiful Evidence*) e bullet graph de Few (via resumos): https://en.wikipedia.org/wiki/Bullet_graph

**De prática (blogs e fornecedores; usar como heurística):**
- Hierarquia e layout: https://www.fusioncharts.com/blog/dashboard-design-best-practices/ · https://uxpilot.ai/blogs/dashboard-design-principles ·
  https://kindatechnical.com/data-visualization/dashboard-layout-best-practices-and-design-patterns.html
- Mobile e divulgação progressiva: https://www.toptal.com/designers/dashboard-design/mobile-dashboard-ui · https://querio.ai/articles/how-to-design-dashboards-for-mobile-users
- Acessibilidade de gráficos: https://web.accessibility.duke.edu/how/data-visualization/ · https://www.gooddata.ai/docs/cloud/create-dashboards/accessibility/
- Estados (carregando, vazio, erro): https://design-system.agriculture.gov.au/patterns/loading-error-empty-states · https://pluma.customer.io/patterns/states
- Cartões de KPI e sparklines: https://docs.cluvio.com/chart-types/sparkline-metric-chart · https://21st.dev/@ssychui/components/kpi-card-row.md
- Frota e locação: https://oxmaint.com/industries/fleet-management/fleet-vehicle-utilization-analysis-optimization-guide ·
  https://heavyvehicleinspection.com/blog/post/modern-fleet-management-ui-ux-dashboard-kpis-guide · https://hicronsoftware.com/blog/fleet-management-dashboard-design/ ·
  https://reflex.dev/templates/fleet-management-dashboard · https://fleetio.com/features/fleet-management-dashboards
- Manutenção e KPIs de frota em português: https://www.geotab.com/pt-br/blog/kpis-manutencao-de-frota-essenciais/ ·
  https://www.ayvens.com/pt-br/sobre-nos/blog/gestao-de-frotas/kpis-de-frota/
- Aging de recebíveis: https://ramp.com/blog/accounts-payable/ar-aging-report · https://racklify.com/encyclopedia/ar-aging-report-how-to-read-and-use-it-for-collections/ ·
  https://tabs.com/blog/ar-aging-guide

**Lacunas que encontrei (e como tratei):** não achei fonte específica sobre indicadores de locadora de **motos** (só de carros e frota em geral): adaptei com
cuidado e marquei como heurística. Não consegui abrir as páginas de KPI do Polaris (Shopify) nem do NN/g sobre dashboards além do artigo citado.
As metas numéricas (utilização, custo de parada, ganho de receita) vêm de fornecedores e **não** devem virar metas do negócio sem validação do dono ou de um contador.
