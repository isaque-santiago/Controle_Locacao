# Inventário de páginas, visões e diálogos

> Etapa 0 do `Plano_Melhorias_UI_UX.md` (item 1). Levantado do código em 28/09/2026.
> Serve de mapa para a suíte `e2e/` e para as etapas seguintes. Atualize quando uma
> página, visão ou diálogo for criado, removido ou renomeado.

## Páginas, visões e diálogos

Todas as páginas exigem login (`require_login`). Visões alternam por `st.session_state`
dentro da mesma URL. Diálogos usam `@st.dialog`.

| Página | Visões | Abas | Diálogos |
|---|---|---|---|
| Dashboard | única (Hoje, Alertas, KPIs) | — | registrar pagamento (a partir da seção Hoje) |
| Motos | lista · ficha da moto | ficha: Resumo, Plano de manutenção, Histórico, Documentos, Contratos, Financeiro | Nova moto · Editar dados da moto · Atualizar quilometragem · Regularizar documento |
| Clientes | lista · ficha do cliente | ficha: Resumo, Contratos, Pagamentos | Novo cliente · Editar dados do cliente |
| Contratos | lista · assistente (4 etapas: Cliente, Moto, Condições, Confirmar) · ficha do contrato | ficha: Cobranças, Vistorias, Manutenções | Encerrar contrato |
| Cobranças | única | Abas por situação (com contagem) | Registrar pagamento · popover de mensagem de cobrança |
| Manutenção | única | Alertas, Histórico, Catálogo | Registrar manutenção · Atualizar manutenção aberta · Item do catálogo |
| Documentos | única | — | Novo documento · Editar documento · Marcar como regularizado · Comprovante |
| Vistorias | lista · comparação (entrega × devolução) | — | Registrar vistoria · Adicionar fotos |
| Relatórios | única (filtros de período e exportação) | Resultado por moto, Custo de manutenção (visão Por moto/Por modelo), Inadimplência, Fluxo de caixa | — |
| Configurações | única (inclui backup) | — | — |
| Login | única | — | — |

Menu lateral: dez destinos no mesmo nível (`app.py`), mais alternância de tema e Sair.

## Cobertura por fluxo mínimo (Etapa 9)

Cada fluxo tem um cenário em `e2e/`. Na Etapa 0 os cenários percorrem o fluxo até o
ponto de gravar e fecham sem salvar; a submissão real entra nas Etapas 5 e 9.

| # | Fluxo | Cenário | Até onde vai na Etapa 0 |
|---|---|---|---|
| 1 | Entrar e navegar por todas as páginas | `test_login.py`, `test_paginas.py` | login e as dez páginas |
| 2 | Consultar Dashboard e alertas | `test_fluxos.py::fluxo_dashboard` | página |
| 3 | Buscar, filtrar, paginar e abrir Moto e Cliente | `fluxo_buscar_e_abrir_fichas` | busca, abrir ficha, voltar |
| 4 | Criar e revisar um Contrato | `fluxo_contrato` | abre o assistente e volta |
| 5 | Registrar um Pagamento | `fluxo_pagamento` | abre o diálogo |
| 6 | Registrar e concluir uma Manutenção | `fluxo_manutencao` | abre o diálogo de registro |
| 7 | Cadastrar e regularizar um Documento | `fluxo_documento` | abre o diálogo de cadastro |
| 8 | Registrar, abrir e comparar Vistorias | `fluxo_vistoria` | abre o diálogo de registro |
| 9 | Filtrar e exportar Relatórios | `fluxo_relatorios` | percorre as quatro abas |
| 10 | Alterar Configurações e gerar/baixar backup | `fluxo_configuracoes` | página |

## Estados de dados

| Estado (`E2E_DADOS`) | Como montar o projeto de desenvolvimento |
|---|---|
| `vazio` | migrations + `supabase/seed.sql`, sem seeds de exemplo |
| `normal` | + `supabase/seed_exemplos.sql` |
| `extremo` | + `supabase/seed_e2e.sql` (textos longos, valores grandes, listas extensas) |
