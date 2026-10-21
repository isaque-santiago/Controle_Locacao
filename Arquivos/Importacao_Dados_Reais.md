# Importação dos dados reais (planilha "PAGAMENTO MOTOS")

Proposta de modelo de dados e plano de carga. **Aprovada em 21/10/2026** (desenho e recomendações D1, D2, D4, D5, D6).
**Status (22/10/2026):** as migrations 1 a 4 (`supabase/migrations/20261022*`), o roteiro `supabase/verificar_importacao_modelo.sql` e a
regra da agenda (`src/domain/agenda_cobrancas.py`, `tests/test_agenda_promessa.py`) foram escritos, mas **ainda não aplicados** em nenhum
banco. A **carga** dos dados não existe. D3 segue pendente.

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

## 4. Decisões

| # | Decisão | Resultado |
| --- | --- | --- |
| D1 | Promessa de compra: coluna em `contratos` ou tabela separada | **Coluna** (aprovado) |
| D2 | Pagamentos sem data | **Data fixa 12/10/2026 com `data_estimada`** para os agregados; datas que afetam o caixa serão pedidas ao Alisson (aprovado) |
| D3 | Cobrar encargos de atraso (R$ 15 + R$ 7/dia) nas promessas. O plano diz "só locação" (seção 5.3), a planilha cobra | **PENDENTE** (decisão do dono) |
| D4 | `km_inicial` sem dado na planilha | **Gravar 0** e anotar em `observacoes` (aprovado) |
| D5 | Ex-locatários sem CPF (Jonatha, outro Wagner) | **Texto livre em multas**, sem cadastro em `clientes` (aprovado) |
| D6 | Escopo agora | **Só banco e carga em dev**; telas depois (aprovado) |

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

1. Resolver os conflitos da seção 5 e a decisão D3 com o dono.
2. Atualizar o plano e o `CLAUDE.md` se preciso (feito: seção 16 do plano).
3. Implementar as migrations 1 a 4, regras em `src/domain` e testes (`pytest`), README e commit.
4. Gerar o SQL de carga em pasta temporária (fora do repositório quando tiver dado pessoal) e rodar no banco de **dev**.
5. Conferir totais contra a planilha (receita, débitos, saldos de dívida) e corrigir.
6. Quando CPF e telefone estiverem na planilha, carregar `clientes` e `contratos`.
7. Backup de produção, autorização do dono e carga em produção.
