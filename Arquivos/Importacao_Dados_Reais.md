# Importação dos dados reais (planilha "PAGAMENTO MOTOS")

Proposta de modelo de dados e plano de carga. **Aprovada em 21/10/2026** (desenho e recomendações D1, D2, D4, D5, D6).
**Status (23/10/2026):** as migrations 1 a 5 (`supabase/migrations/20261022*`) estão aplicadas no banco de **dev** e o roteiro
`supabase/verificar_importacao_modelo.sql` passou. Cinco cargas de dados já rodaram no dev (seção 7): veículos, contas, fornecedores, despesas, multas,
sócio, dívidas sem conflito, capital do Etios e do Celta e, dos locatários, apenas os de identidade confirmada (8 clientes e 5 contratos).
As cargas são geradas fora do repositório porque contêm dados reais (CPF, telefone). **Nada foi carregado em produção.** Faltam os demais
locatários e contratos, pagamentos de locação restantes e três dívidas com saldo conflitante (seção 7). D3 foi decidida (encargos valem na promessa).

Desvio do desenho aprovado: `vw_resultado_moto` ganhou as colunas `custo_despesas` e `resultado_com_despesas` em vez de alterar `resultado`,
para não divergir de `src/domain/relatorios.py` enquanto as telas não incorporam as despesas.

Planilha de origem: Google Sheets "PAGAMENTO MOTOS" (19 abas). Controle de cobrança na planilha começa em 12/10/2026.

## 1. Princípios

- Acrescentar sem quebrar o que existe: o app em produção continua funcionando a cada migration.
- Dinheiro em `numeric(12,2)`; datas em America/Sao_Paulo.
- Toda tabela nova com RLS restrita a `is_dono()` e as mesmas permissões das migrations atuais.
- Operação em mais de uma tabela é RPC PL/pgSQL (transação única).
- A carga é um SQL gerado pela IA e colado pelo dono no SQL Editor. Sem `service_role`, sem segredos no repositório.
- Ensaio **sempre** no projeto Supabase de desenvolvimento. Produção só depois de backup e autorização expressa do dono.
- **CPF e telefone dos locatários não existem na planilha.** A carga de `clientes` e `contratos` espera a planilha ser completada.

## 2. Origem dos dados e o que é (ou não) dado real

| Aba | Natureza | Destino |
| --- | --- | --- |
| Frota, Histórico, Documentos | Real | `motos`, `clientes`, `contratos` |
| Pagamentos | Real | `pagamentos` (e cobranças de saldo anterior) |
| Despesas | Real | `despesas` |
| Etios, Celta, Capital de fora | Real (abas criadas em 22/10/2026) | `despesas` (categoria `aquisicao`), `dividas`, `dividas_vencimentos`, `movimentos_socio`; "Capital de fora" é derivada (`vw_capital_veiculo`) |
| Dívidas | Real | `dividas`, `pagamentos_divida` |
| Retiradas, Aportes | Real | `movimentos_socio` |
| Multas | Real | `multas_transito` |
| Seguros | Real | colunas em `motos` e `despesas` |
| MOTOS PROMESSA COMPRA, PAGAMENTO MOTOS | Real (histórico antigo) | pagamentos antigos e `pagamentos_divida` |
| cobrança motos | Desatualizada | só conferência |
| Simulador | Hipotético (propostas para a PNH1H96) | não importa |
| Painel, Dashboard | Derivados por fórmula | não importa |
| Config, Página2, Pendências | Apoio / vazia / perguntas | não importa (Config vira cadastro de contas) |

Não foi encontrado dado fictício nas abas de dados. A confirmação final é do dono.

## 3. Migrations propostas

### Migration 1: veículos, contratos e pagamentos

- `motos` ganha: `tipo` (`moto` ou `carro`, padrão `moto`), `proprietario_documento`, `link_documento`, `possui_rastreador`,
  `seguro_valor_mensal`, `seguro_dia_vencimento`. Modelo desconhecido entra como `A INFORMAR` (marca e modelo são obrigatórios).
  Motos já vendidas (OIH0D80, NVE8D78) entram como `inativa`, para que as multas tenham a quem se ligar.
- `contratos` ganha: `tipo_contrato` (`locacao` ou `promessa_compra`), `numero_parcelas`, `valor_total`, `valor_entrada`,
  `parcelas_pagas_inicial`, `dia_cobranca` (dia da semana ou do mês) e `primeira_cobranca`.
  Restrição: se for promessa, `numero_parcelas` e `valor_total` são obrigatórios e `valor_total = numero_parcelas * valor_periodo`
  (confere: Ronildo 260 x 550, José Henrique 200 x 650, Wagner 200 x 550, Ricardo 130 x 260). Promessa quitada vai para `encerrado`.
- Tabela nova `contas` (Ana Quezia, Ana Luiza, Letícia Ariadne, Alisson, Espécie).
- `pagamentos` ganha: `conta_id`, `data_estimada` (booleano) e a forma `abatimento` (desconto sem dinheiro, ex.: pastilha de
  freio do Otavio; não entra no caixa).
- `domain/agenda_cobrancas.py`: ancora na semana ou no dia do mês, respeita `numero_parcelas`, começa em
  `parcelas_pagas_inicial + 1` e só gera cobranças a partir de 12/10/2026. O anterior vira uma cobrança única de
  "saldo anterior" (tipo `outros`), com o pagamento em 12/10/2026 e `data_estimada = true`.
- `rpc_criar_contrato` (e a variante com vistoria) passam a aceitar os campos de promessa.

### Migration 2: despesas, sócio e dívidas

- `fornecedores` (Lima Auto Peças, Hinova Pay, Ícaro, Nicolas, Nilson).
- `despesas`: `data`, `data_estimada`, `moto_id` (nulo se não houver placa), `descricao_veiculo` (ex.: "Biz Yangry"),
  `categoria` (Manutenção, Documentação, Seguro e rastreador, Multas, Combustível, Outros), `valor`, `fornecedor_id`,
  `conta_id`, `repassar_locatario`, `repassado`, `contrato_id`, `observacoes`. A view `vw_resultado_moto` passa a somar as despesas.
- `movimentos_socio`: retiradas e aportes (tipo, data, valor, conta/origem, destino, flag de exceção).
- `dividas`: tipo (`moto_fiado`, `financiamento`, `fornecedor`, `rastreador`), credor, `moto_id` opcional, valor original,
  parcelas, valor da parcela, `dia_vencimento`, `saldo_confirmado` e `confirmado_em`.
- `pagamentos_divida`: data, `data_estimada`, valor, conta.
- View `vw_saldo_dividas`: saldo calculado ao lado do confirmado (expõe divergências, como XRE e Bros/Pop). O saldo da Lima
  soma a dívida anterior com as despesas ligadas ao fornecedor, menos os pagamentos.

### Migration 3: multas

- `multas_transito`: `moto_id`, `data_infracao`, `ait`, `descricao`, `valor`, `valor_atual`, `vencimento`, `situacao`,
  `responsabilidade` (`locatario`, `locadora`, `a_definir`), `cliente_id` opcional, `responsavel_nome` (texto livre para
  ex-locatários sem cadastro), `repasse` (`nao`, `parcial`, `sim`), `valor_repassado`, `observacoes`.
- O "locatário na data" vem de uma view por sobreposição de datas com os contratos, não é digitado.
- A carga não gera cobranças a partir das multas; isso depende de decisão de negócio.

### Migration 4: rastreio da importação

- `importacoes_lote`: lote, tabela, aba e linha de origem, id gravado. Dá idempotência e permite desfazer um lote inteiro.
  Cada carga roda numa transação única.

### Migration 5: capital em veículos sem operação (Etios e Celta)

Aprovada em 22/10/2026. Aplica-se a veículos que ainda não rendem (Etios) ou sem placa conhecida (Celta).

- `motos.placa_provisoria`: o Etios e o Celta entram com placa provisória (`PROV-ETIOS`, `PROV-CELTA`) e marca/modelo `A INFORMAR`
  onde faltar, até a placa real ser informada.
- `despesas`: nova categoria `aquisicao` (compra e reforma até o veículo render), `pago_por` (`locadora`, `locatario`, `terceiro`;
  o compressor de R$ 450 do Celta é do locatário) e `a_confirmar` (valores de memória, como o arremate do Etios).
- `dividas.tipo` ganha `emprestimo` (Etios: R$ 14.000, R$ 3.000 pagos). Nova tabela `dividas_vencimentos` guarda parcelas futuras,
  com a data podendo ser nula (R$ 1.000 sem data e R$ 10.000 em 06/11/2026 do Etios; 4 parcelas do motor do Celta).
- `movimentos_socio.moto_id`: o dinheiro próprio colocado no Etios (R$ 2.965) é um aporte ligado ao veículo.
- `vw_capital_veiculo`: custo total, pago pelo locatário, a pagar (saldo confirmado ou, sem ele, o calculado das dívidas de
  empréstimo/fornecedor do veículo), saiu do bolso (= custo - pago pelo locatário - a pagar), recebido e saldo. Reproduz a aba
  "Capital de fora" (Etios 16.965 = 0 + 5.965 + 11.000; Celta 9.550 = 450 + 5.100 + 4.000).
- `vw_resultado_moto`: `custo_despesas` e `resultado_com_despesas` ignoram a categoria `aquisicao` (capital) e o que não foi a
  locadora que pagou.
- Celta: motor de R$ 8.000 em despesa + dívida de fornecedor com 5 parcelas pagas (R$ 5.000) e saldo confirmado de R$ 4.000; a
  diferença de R$ 1.000 (9 parcelas x R$ 8.000) fica visível em `vw_saldo_dividas` e como despesa `a_confirmar` de R$ 1.000.

## 4. Decisões

| # | Decisão | Resultado |
| --- | --- | --- |
| D1 | Promessa de compra: coluna em `contratos` ou tabela separada | **Coluna** (aprovado) |
| D2 | Pagamentos sem data | **Data fixa 12/10/2026 com `data_estimada`** para os agregados; datas que afetam o caixa serão pedidas ao Alisson (aprovado) |
| D3 | Cobrar encargos de atraso (R$ 15 + R$ 7/dia) nas promessas | **Sim** (decidido em 22/10/2026). As parcelas de promessa são cobranças `locacao`, então a regra já vale; entrada, caução e saldo anterior não pagam encargos |
| D4 | `km_inicial` sem dado na planilha | **Gravar 0** e anotar em `observacoes` (aprovado) |
| D5 | Ex-locatários sem CPF (Jonatha, outro Wagner) | **Texto livre em multas**, sem cadastro em `clientes` (aprovado) |
| D6 | Escopo agora | **Só banco e carga em dev**; telas depois (aprovado) |
| D7 | Como alocar os pagamentos de locação nas cobranças | **FIFO por vencimento**: cada pagamento abate a cobrança mais antiga com saldo e é dividido se passar do saldo; o saldo anterior ao controle é a primeira cobrança (23/10/2026) |
| D8 | Quais locatários carregar já | **Só os de identidade confirmada** (nome, placa e data de início batem entre o Drive e a planilha). Os inferidos ou em conflito esperam a confirmação do Alisson (23/10/2026) |

## 5. Conflitos nos dados a resolver antes de gerar a carga

| Assunto | Conflito | Leitura provisória |
| --- | --- | --- |
| XRE e Bros/Pop | Calculado: XRE R$ 5.600 e Bros R$ 3.425. Confirmado: XRE R$ 3.425 e Bros R$ 9.050 | Parece troca; perguntar ao Alisson (pendência 15) |
| Financiamento TIA1B71 | Pago R$ 864,24 vs parcela R$ 912,58; saldo calculado R$ 21.037,68 vs informado R$ 20.989,34; Documentos cita R$ 834 | Confirmar com o Alisson |
| PNG3F96 (Mateus e Leo) | Contratos sobrepostos: Leo consta com início 01/10, mas pegou a moto em 20/10; pagamentos de 12/10 em nome do Mateus (R$ 250 vs contrato de R$ 290) | Início do Leo em 20/10, primeira parcela 05/11; confirmar |
| SBE1B80 (Leo e Mateus) | Quem está com a moto hoje é incerto; R$ 500 por mês, dia 5 | Confirmar |
| POU7015, início | 02/07/2026 (Histórico, Multas) vs 02/06/2026 (obs. da Frota) | Usar 02/07 |
| Valores de aluguel | Ronildo 550 vs 500; Pedro 800 vs 850; Apolinário 250 vs 286; José Henrique 650 vs 550 | Usar a Frota; a aba "cobrança motos" é antiga |
| OIH8D29 / OIH8329 | Placa atual vs anterior (CRLV) | Usar OIH8D29 |
| Julho (NUV9G14) | Mensal de R$ 220 (provável erro de periodicidade); nome mudou de Badboy para Julho | Confirmar |
| Yangry (PSG0C86) | Aluguel de R$ 250, paga R$ 135 por causa da Biz | Registrar R$ 135 efetivos, com observação |
| João Filho (OCN2C32) | Dia de pagamento quinta ou quarta | Confirmar |
| Placas | OIQ6556, OIQ5024, OIQ6F50; vendidas NVE8D78 e OIH0D80; PNM0A18 (não é da frota) | Confirmar |
| Contas | "Luzia" e "Luiza" são a Ana Luiza; Ana Quezia é outra pessoa | Resolvido (pendência 14) |
| Thierry e Ronildo (Pagamentos antigos) | Parcelas de R$ 257 a R$ 280 rotuladas "Promessa de compra" vêm do histórico antigo de motos | Tipo provavelmente errado; confirmar |
| Datas de Dívidas | Anos assumidos como 2026 e uma data corrigida de 2025 | Registrar como `data_estimada` |

## 6. Ordem de execução

1. Resolver os conflitos da seção 5 com o dono (D3 já decidida). **Parcial:** o Jefferson (PNH1H96) foi resolvido pelo contrato do Drive; o resto segue aberto.
2. Atualizar o plano e o `CLAUDE.md` se preciso (feito: seção 16 do plano).
3. Implementar as migrations 1 a 5, regras em `src/domain` e testes (`pytest`), README e commit. **Feito** (PRs 81, 82 e 100).
4. Gerar o SQL de carga em pasta temporária (fora do repositório quando tiver dado pessoal) e rodar no banco de **dev**. **Feito** para o que não tem
   pendência (seção 7).
5. Conferir totais contra a planilha (receita, débitos, saldos de dívida) e corrigir. **Feito** para o que foi carregado.
6. Com a conferência dos cadastros do Drive respondida, carregar os demais `clientes` e `contratos`. **Pendente.**
7. Backup de produção, autorização do dono e carga em produção. **Pendente.**

## 7. Estado do banco de dev (23/10/2026)

As cargas ficam fora do repositório e são aplicadas pelo dono no SQL Editor do dev. Cada uma roda em transação única, é idempotente
(`importacoes_lote` guarda a linha de origem de cada registro) e tem um SQL para desfazer.

| Carga | Lote | Conteúdo |
| --- | --- | --- |
| 01 parcial | `planilha-2026-10-22-dev-parcial` | 28 veículos, 5 contas, 5 fornecedores, 24 despesas, 72 multas, retirada e aporte do sócio, 2 dívidas |
| 02 complemento | mesmo lote | 3 despesas de 21 e 22/10 |
| 03 capital | `planilha-2026-10-22-dev-capital` | Etios e Celta (placa provisória), despesas de aquisição, empréstimo do Etios, motor do Celta, parcelas futuras e aporte |
| 04 clientes e contratos | `planilha-2026-10-23-dev-clientes` | 8 clientes e 5 contratos (4 ativos e 1 encerrado) com cobranças e pagamentos |
| 05 complemento | lote parcial | moto PMZ8278, 5 despesas e 3 aportes de cartão |

Total conferido no dev: 31 veículos, 5 contas, 6 fornecedores, 40 despesas, 72 multas, 6 movimentos de sócio, 4 dívidas, 3 pagamentos de dívida,
3 parcelas futuras, 8 clientes e 5 contratos. O Dashboard abriu sem erros e o débito do contrato conferido (R$ 270) bateu com a planilha.

Regras aplicadas na carga dos contratos (D7 e D8): cobrança controlada desde 12/10/2026, com a parcela nº 1 nessa data; o que veio antes entra como
cobrança única de "saldo anterior" (tipo `outros`); km inicial 0 com observação; cobranças futuras ficam por conta da janela móvel do app.

**Ainda pendente:**

- Contratos de três locatários que entraram só como cliente (moto, valor e dia de pagamento a confirmar) e de cinco com identidade inferida ou em conflito.
- Onze locatários sem dados no Drive e um CPF com dígito verificador inválido.
- Pagamento de 22/10 de um locatário cujo contrato ainda não foi carregado.
- Dívidas XRE, Bros/Pop e TIA1B71 (saldos conflitantes) e os dados do Celta e do Etios (placa, datas, credor).
- Escopo do histórico dos 64 contratos do Drive (atuais, histórico inativo ou não carregar).
- Produção: backup do Supabase, autorização do dono e carga.
