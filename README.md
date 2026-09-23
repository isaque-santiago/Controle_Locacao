# Controle de Locação e Manutenção de Motos

Sistema web para controlar locação, manutenção, documentação e vistorias de uma frota de motos de aluguel.

Ver plano completo em [Arquivos/Projeto_Locação.md](Arquivos/Projeto_Locação.md).

## Stack

Python 3.11+, Streamlit, Supabase (PostgreSQL + Auth + Storage), Plotly, pytest.

## Setup

1. Crie um projeto no Supabase. As migrations em `supabase/migrations/` seguem o formato `AAAAMMDDHHMMSS_descricao.sql` (exigido pela integração Supabase ↔ GitHub, que aplica cada push automaticamente); ao adicionar uma nova, use um timestamp maior que o da última. `supabase/seed.sql` **não** é aplicado por essa integração — rode-o manualmente no SQL Editor após a primeira aplicação das migrations.
2. Desative o cadastro público em Authentication > Providers > Email e crie manualmente o usuário do dono.
3. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Rode o app:

```bash
streamlit run app.py
```

## Testes

```bash
pytest
```

## Estrutura

Ver seção 3 do plano ([Arquivos/Projeto_Locação.md](Arquivos/Projeto_Locação.md)).

## Status da implementação

As telas das fases 1 a 7 estão implementadas: cadastros, contratos com vistorias,
cobranças, manutenção, documentos, Dashboard, relatórios, configurações e backup.
As regras existentes foram complementadas com transações para entrega/devolução,
conclusão de manutenção, plano automático de motos e proteção de pagamentos.

Revisão de fidelidade visual ao `Arquivos/Design_UI.md` (22/09/2026): paleta de
status corrigida para os tokens exatos do documento, chip de placa em mono no
padrão do plano, selos circulares tracejados para alertas (Dashboard e
Manutenção), barra de ocupação segmentada substituindo a barra padrão do
Streamlit e assistente em 4 etapas (Cliente, Moto, Condições, Vistoria de
entrega) na criação de contrato. O painel autenticado agora oferece modo escuro
na barra lateral, com contraste específico para cartões, tabelas e formulários.
A tela de login foi validada em viewport mobile de 390 × 844 px; a validação
mobile autenticada continua dependendo do acesso ao ambiente de homologação.

Reconstrução do Dashboard (22/09/2026), conferida linha a linha contra o
artboard `Main.dc.html`: faixa de instrumentos como um único painel com quatro
seções (frota com barra segmentada, recebido no mês com barra de progresso,
em atraso, manutenção no mês), cartão "Hoje" com ação real de registrar
pagamento (leva à página Cobranças com a cobrança pré-selecionada) e cartão
"Alertas" único combinando manutenção, documentos e CNH com os selos
circulares tracejados de 40px do mockup. `app.py` passou a usar
`st.navigation`/`st.Page` para eliminar a entrada duplicada "app" da barra
lateral, e o rodapé da barra lateral (avatar, nome, botão Sair) segue o
padrão visual do mockup. As demais páginas ainda não foram revisadas contra
seus artboards — trabalho em andamento, uma página por vez.

Reconstrução de Motos (22/09/2026), conferida contra `Motos.dc.html` e
`MotoFicha.dc.html`: lista com pílulas de filtro por status, busca, chip de
placa mono e paginação de 7 por página; cadastro/edição movidos para modais
(`st.dialog`), como pedem os demais formulários de passo único do plano; a
ficha da moto virou uma visão própria (navegação `‹ Motos` / `→` na lista,
sem recarregar página) com faixa de dados rápidos e 6 abas — Resumo (contrato
ativo, dados da moto, quilometragem), Plano de manutenção, Histórico,
Documentos (com ação "Regularizar"), Contratos e Financeiro (receita, custos
e custo por km). Novos componentes reutilizáveis em `componentes.py`:
`chip_placa`, `selo_situacao` e `tabela_html`. Corrigido também um bug
anterior: as classes CSS `.rotulo`/`.mono`/`.campo` usadas no HTML injetado
do Dashboard não tinham regra correspondente no tema global — só o seletor de
tag (`h1,h2,h3`) pegava por acidente; várias leituras em mono no Dashboard
podiam não estar com a fonte certa.

Correções complementares (22/09/2026): as fichas de Moto e Cliente abrem
diretamente o contrato selecionado; o registro de manutenção aceita várias
peças ou serviços livres numa tabela com linhas adicionáveis e removíveis; a
ficha de Cliente escapa dados cadastrados antes de inseri-los em HTML, carrega
históricos financeiros em lote e mantém todos os cálculos monetários em
`Decimal`.

Reconstrução de Vistorias (23/09/2026), conferida contra `Vistorias.dc.html` e
`VistoriaComparacao.dc.html`: lista de todas as vistorias (mais recentes
primeiro) com pílulas Todas/Entrega/Devolução, busca por cliente ou placa,
paginação, chip de placa, combustível e avarias em vermelho. O registro virou
modal (só oferece contratos e tipos ainda pendentes, data não anterior ao início
do contrato, checklist em duas colunas, itens adicionais e envio de várias fotos;
falha no envio de foto não desfaz a vistoria, apenas avisa). A seta da linha abre
a comparação entrega × devolução lado a lado, com faixa de resumo (período, km
rodados, avarias na devolução), itens que mudaram destacados em amarelo, fotos
por URL assinada e "Adicionar fotos" em cada lado. A lógica pura (rótulos,
ordem do checklist, contagem de avarias, km rodados, tipos pendentes e o
instante gravado no fuso America/Sao_Paulo) ficou em `src/domain/vistorias.py`,
com testes; a tela está em `src/ui/vistorias.py`. O formulário usado pelo
assistente e pelo encerramento de contratos (`campos`/`preparar`) não mudou.

Reconstrução de Manutenção (23/09/2026), conferida contra `Manutencao.dc.html`:
cabeçalho com contagem de vencidas/próximas e botão "Registrar manutenção",
3 abas — Alertas (pílulas Todas/Vencidas/Próximas, chip de placa, restante em
vermelho quando negativo), Histórico (filtro por tipo, busca por moto/oficina,
paginação e ação ✓ para concluir/cancelar manutenções abertas) e Catálogo
(interruptor de ativo, edição por ícone). O registro virou modal com prévia ao
vivo de custo de peças e total; a lógica está em `src/ui/manutencao.py`.

Reconstrução de Clientes (22/09/2026), conferida contra `Clientes.dc.html` e
`ClienteFicha.dc.html`: lista com pílulas de filtro por status, busca por
nome/CPF, avatar com inicial (grafite-900 quando ativo, grafite-500 quando
não), selo de validade da CNH por cliente (novo `src/domain/cnh_regras.py`,
com testes, pois a view `vw_alertas_cnh` só alerta clientes com contrato
ativo — a lista mostra a validade de todos) e moto atual via chip de placa;
cadastro/edição em modal. Ficha com faixa de dados rápidos e 3 abas — Resumo
(contrato ativo, dados pessoais, situação financeira), Contratos e
Pagamentos. Corrigida uma inconsistência de paleta encontrada nesta revisão:
"ativo" é neutro para contrato (confirmado em `MotoFicha`/`ClienteFicha`),
mas verde para cliente — os dois usos agora têm chaves de situação
diferentes (`ativo` vs `ativo_cliente`) na paleta compartilhada.

Reconstrução de Contratos (23/09/2026), conferida contra `Contratos.dc.html`,
`ContratoNovo.dc.html` e `ContratoFicha.dc.html`: lista com pílulas de filtro
(Ativo por padrão), busca por cliente/placa e linhas de contratos não ativos
esmaecidas; assistente em 4 etapas (Cliente, Moto, Condições, Confirmar) com
cartões selecionáveis (cliente bloqueado/inativo aparece desabilitado, "já
aluga X" como aviso), periodicidade em pílulas e etapa final com resumo,
prévia da agenda e a vistoria de entrega exigida pela Fase 5; ficha com
faixa de dados, abas Cobranças/Vistorias/Manutenções e encerramento em
modal. **Limitação conhecida:** o mockup mostra "Prazo indeterminado", mas
`rpc_criar_contrato_com_vistoria` exige `data_fim_prevista` — por isso o
"Fim previsto" continua obrigatório no assistente.

Reconstrução de Cobranças (23/09/2026), conferida contra `Cobrancas.dc.html`:
subtítulo com total em atraso e nº de clientes; abas Hoje, Atrasadas, Próximos 7
dias e Pagas (com contagem); Atrasadas mostra atraso, original, encargos e total;
ações por linha: mensagem de cobrança para copiar (popover) e registrar
pagamento em diálogo, com multa/juros recalculados ao mudar a data. O pagamento
mantém principal e "multa e juros" em campos separados (como grava a tabela
`pagamentos`), em vez do campo único "Valor a pagar" do mockup. A aba Pagas
mostra as 30 mais recentes. Regras de abas/resumo/mensagem em
`src/domain/painel_cobrancas.py`, testadas em `tests/test_painel_cobrancas.py`.

Reconstrução de Documentos (23/09/2026), conferida contra `Documentos.dc.html`:
a página deixou de ser um seletor por moto e passou a listar os documentos de
toda a frota (Moto, Tipo, Referência, Vencimento, Valor, Situação), com subtítulo
de vencidos/a vencer, pílulas Todos/Vencido/A vencer/Em dia com contagem, busca
por placa e paginação de 10. Novo documento e regularizar são diálogos; as ações
por linha são ver comprovante (URL assinada de 5 minutos), editar e regularizar.
A situação vem de `situacao_documento` em `src/domain/documentos.py` (mesma regra
da view `vw_alertas_documentos`, testada em `tests/test_documentos.py`); documento
regularizado aparece como "Regularizado" e conta em "Em dia". Diferenças em
relação ao mockup: há um campo "Descrição" (é ele que alimenta a coluna
Referência, ex.: apólice), o botão de editar (o mockup não previa edição) e, ao
regularizar, o "documento do ano seguinte" abre o cadastro já preenchido em vez
de criar direto, porque `vencimento` é obrigatório no banco.

Correção em 22/09/2026: a sessão de login ficava apenas em `st.session_state`, que o
Streamlit descarta a cada refresh completo do navegador — o usuário logado caía na
tela de login ao atualizar a página. Agora o refresh token é guardado num cookie do
navegador (`streamlit-cookies-controller`) e a sessão é restaurada automaticamente a
partir dele; um segundo cookie, renovado a cada requisição e com validade de 30
minutos, mantém a regra de expiração por inatividade mesmo entre refreshes.

Validação local em 21/09/2026:

- Testes pytest de regras, exportação, paginação, login e telas com serviços simulados.
- Todas as 10 migrations executadas em PostgreSQL embarcado (PGlite 0.5.8).
- Roteiro `supabase/verificar_fluxos.sql` executado com rollback: contrato duplicado,
  pagamento parcial/total, preservação da parcela parcialmente paga no encerramento,
  cancelamento de futuras sem pagamento, vistorias, plano e conclusão de manutenção,
  custo total e resultado financeiro.
- `seed_demo.sql` executado duas vezes, sem duplicar o cenário.

**Validação em produção (22/09/2026):** as 11 migrations aplicadas no Supabase de
destino (as 7 mais recentes ficaram pendentes por um tempo — aplicadas via
`Arquivos/aplicar_migrations_pendentes.sql`, depois `NOTIFY pgrst, 'reload
schema'` + restart do projeto para o PostgREST reconhecer os objetos novos).
Login do dono confirmado: RLS e as permissões do papel `authenticated`
(migration `20260921154000_permissoes_authenticated.sql`) funcionando —
Dashboard carrega sem erro de permissão.

**Aceite externo ainda pendente:** uploads/URLs assinadas, executar o roteiro
manual completo (seção abaixo), revisar em celular no aplicativo publicado e
confirmar deploy no Streamlit Community Cloud. O teste local não valida
Supabase Storage, infraestrutura ou publicação. Nenhuma fase é declarada
homologada apenas com base nas telas e testes isolados.

## Atualização de uma instalação existente

1. Faça backup antes de aplicar alterações no projeto de produção.
2. Aplique somente as migrations pendentes, na ordem dos timestamps. As novas são:
   - `20260921150000_cadastro_moto.sql`: plano e histórico iniciais atômicos, km não regride.
   - `20260921151000_fluxos_contratos.sql`: contratos com vistorias e validação de pagamentos.
   - `20260921152000_finalizar_manutencao.sql`: conclusão/cancelamento de manutenção aberta.
   - `20260921153000_resultado_km.sql`: distância registrada e custo por km na view.
3. Se a integração GitHub já aplica as migrations, confira o histórico antes de
   executá-las manualmente. Não reaplique migrations antigas. Pela CLI, revise o
   projeto conectado com `supabase link` e use `supabase db push`.
4. Rode `supabase/seed.sql` para o catálogo, caso ainda não tenha sido aplicado.
5. Em homologação, execute `supabase/verificar_fluxos.sql`. O roteiro usa `ROLLBACK`.
6. Reinicie o aplicativo com as dependências de `requirements.txt`.

Referência: [migrations do Supabase](https://supabase.com/docs/guides/deployment/database-migrations).

## Publicação no Streamlit Community Cloud

1. Envie o código revisado ao repositório GitHub conectado à sua conta.
2. Em [Streamlit Community Cloud](https://share.streamlit.io), escolha **Create app**,
   selecione o repositório, a branch desejada e o arquivo principal `app.py`.
3. Em configurações avançadas, selecione Python 3.11 ou superior e configure os
   segredos conforme `.streamlit/secrets.toml.example`. Use `SUPABASE_URL` e
   `SUPABASE_ANON_KEY`; não use a chave `service_role`.
4. Confirme que as migrations foram aplicadas, o cadastro público do Supabase foi
   desativado e o usuário do dono foi criado. Os buckets devem continuar privados.
5. Publique. Em janela anônima, todas as páginas devem exibir somente o login.
6. Entre com o usuário do dono e execute o roteiro abaixo. Registre a URL e os
   resultados da homologação antes de considerar a implantação concluída.

Referência: [guia oficial de deploy](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Roteiro manual de aceite

Use um projeto de homologação; os passos criam dados.

1. Sem login, visite a página inicial e cada página do menu; nenhuma deve exibir dados.
2. Cadastre uma moto e um cliente. Confira o plano automático e o histórico inicial.
   Confira recusa de placa/CPF duplicados e inválidos; confira CPF mascarado nas listas.
3. Atualize o km. Uma leitura histórica menor exige confirmação e não reduz o km atual.
4. Crie contrato com caução e vistoria. Compare a prévia com as parcelas geradas;
   confira que a moto deixa de aparecer entre as disponíveis.
5. Registre pagamentos em dia, atrasado, parcial e total. Confira principal separado
   dos encargos, saldo residual e recusa de pagamento superior ao saldo.
6. Suba o km até o limite preventivo. Abra manutenção com peças e mão de obra; conclua
   o serviço. Confira custo total, status da moto e reinício apenas dos itens marcados.
7. Cadastre documento vencido e confira destaque no Dashboard. Anexe comprovante,
   abra a URL assinada, regularize e crie o próximo ano pela sugestão de vencimento vazio.
8. Anexe fotos à entrega. Encerre contrato com devolução e avaria; compare checklists.
   Confira preservação de dívida parcial, cancelamento das futuras sem pagamento e km final.
9. Compare Dashboard e relatórios com as consultas no banco. Caução não é receita.
   Exporte CSV e Excel e confira acentos, valores e período. Custo/km sem leitura suficiente
   fica vazio; o cálculo usa a distância observada, sem extrapolar leituras ausentes.
10. Gere e baixe o backup. Confira as 14 tabelas e as contagens em `manifesto.json`.
    O ZIP não inclui os binários de fotos/comprovantes nem usuários do Auth. Evite
    alterações durante a geração, pois as leituras não formam um snapshot transacional.
11. Confira os formulários e tabelas em celular. Saia da conta e verifique que os dados
    deixam de aparecer. Após 30 minutos sem interação, a próxima ação exige novo login.

## Demonstração

`supabase/seed_demo.sql` cria uma moto, um cliente fictício, contrato, cobranças,
pagamentos e documento vencido. Execute apenas em projeto de demonstração, após
migrations e `seed.sql`. É idempotente pela placa `DEM1A23`; não rode em produção.

`supabase/seed_exemplos.sql` popula um cenário mais completo para explorar o
sistema: 6 motos (uma em cada status), 5 clientes (ativo, CNH a vencer,
bloqueado, sem contrato), 3 contratos (2 ativos e 1 encerrado, com vistorias
de entrega/devolução), cobranças pagas/em aberto/vencida/paga com atraso,
manutenção preventiva concluída e corretiva em aberto, e documentos vencido/a
vencer/regularizado. Rode manualmente no SQL Editor após migrations e
`seed.sql`. É idempotente pela placa `EXA1A11`; não rode em produção.

## Convenções dos relatórios

Receita usa a data de pagamento e exclui caução. Custo de manutenção considera
serviços concluídos, pela data de entrada. Documentos entram na data de regularização.
Essas datas representam o controle disponível no sistema; não há uma tabela separada
de pagamentos a fornecedores. O custo/km representa manutenção dividida pela distância
registrada. Os cálculos financeiros usam `Decimal`; as células do Excel são numéricas.
