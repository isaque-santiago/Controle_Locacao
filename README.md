# Controle de Locação e Manutenção de Motos

Sistema web para controlar locação, manutenção, documentação e vistorias de uma frota de motos de aluguel.

Ver plano completo em [Arquivos/Projeto_Locação.md](Arquivos/Projeto_Locação.md).

## Stack

Python 3.11+, Streamlit, Supabase (PostgreSQL + Auth + Storage), Plotly, pytest.

## Setup

1. Crie um projeto no Supabase. As migrations em `supabase/migrations/` seguem o formato `AAAAMMDDHHMMSS_descricao.sql` (exigido pela integração Supabase ↔ GitHub, que aplica cada push automaticamente); ao adicionar uma nova, use um timestamp maior que o da última. `supabase/seed.sql` **não** é aplicado por essa integração — rode-o manualmente no SQL Editor após a primeira aplicação das migrations.
2. Desative o cadastro público em Authentication > Providers > Email e crie manualmente o usuário do dono. Copie o UUID dele (Authentication > Users) e troque o UUID dentro de `is_dono()` na migration `20260922000000_restringe_rls_ao_dono.sql` **antes de aplicá-la** — a RLS libera o acesso somente a esse usuário; com um UUID errado, ninguém consegue ler nem gravar dados.
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
na barra lateral — automático por padrão (acompanha o tema do sistema/navegador),
com o toggle manual sobrepondo a escolha e o botão "Usar tema do sistema" para voltar
ao automático — com paleta própria (fundos em camadas e texto claro com contraste
mínimo de 4,5:1) para cartões, tabelas, formulários, abas e alertas. As cores inline
dos módulos são remapeadas por seletores sobre o `style` normalizado pelo navegador
(`color: rgb(...)`), não pelo hexadecimal escrito no código.
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
modal. O contrato é por **prazo indeterminado** por padrão (decisão de negócio,
seção 14.4 do plano): o assistente começa com "Prazo indeterminado" marcado e a
periodicidade **semanal**; desmarcar mostra o "Fim previsto" para o caso de data final
combinada. Sem data final a prévia mostra só os 30 primeiros dias e as cobranças
seguintes são geradas por `rpc_gerar_cobrancas_pendentes` enquanto o contrato estiver ativo.
No encerramento o dono informa os **danos**, que são descontados da caução recebida
(`src/domain/caucao.py`, espelhado na RPC): caução R$ 1.000 − dano R$ 300 = devolver
R$ 700; dano acima da caução zera a devolução e gera uma cobrança de dano com o excedente.

Reconstrução de Cobranças (23/09/2026), conferida contra `Cobrancas.dc.html`:
subtítulo com total em atraso e nº de clientes; abas Hoje, Atrasadas, Próximos 7
dias e Pagas (com contagem); Atrasadas mostra atraso, original, encargos e total;
ações por linha: mensagem de cobrança para copiar (popover) e registrar
pagamento em diálogo, com multa e adicional diário recalculados ao mudar a data. O pagamento
mantém principal e "multa e adicional" em campos separados (como grava a tabela
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

Reconstrução de Relatórios (23/09/2026), conferida contra `Relatorios.dc.html`:
subtítulo com o período, filtros De/Até e quatro abas — Resultado por moto,
Custo de manutenção (pílulas Por moto/Por modelo, esta com total e média por
moto), Inadimplência (total em atraso, % da carteira do mês, clientes atrasados
e valor com encargos por parcela) e Fluxo de caixa (mês corrente marcado como
parcial) — com barras proporcionais em HTML/CSS e exportação CSV/Excel por aba,
com os mesmos dados da tabela. **Decisão a confirmar:** o mockup não define
"% da carteira do mês"; foi adotado total em atraso ÷ previsto do mês (parcelas
sem caução nem canceladas que vencem no mês, o mesmo "previsto" do Dashboard).
Cálculos em `src/domain/relatorios.py`, testados em
`tests/test_relatorios_dominio.py`.

Reconstrução de Configurações (23/09/2026), conferida contra `Configuracoes.dc.html`:
quatro cartões em largura total (até 25/09/2026 eram de 780px) — Encargos por atraso (multa de atraso e adicional por dia, em reais,
com exemplo calculado: locação de R$ 500,00 vencida há 5 dias), Alertas de manutenção,
Alertas de documentos e CNH e Backup manual (ZIP de CSVs) — e botão "Salvar
alterações" no cabeçalho. Valores em reais com até duas casas, não negativos; demais
campos, inteiros não negativos; erros aparecem em português sem gravar nada.
O backup é gerado em dois passos (Gerar → Baixar) para não consultar as 14
tabelas a cada interação. **Decisão a confirmar:** o mockup mostra "Último backup"
com data/hora, mas o schema não guarda isso; a tela informa apenas o backup gerado
na sessão atual. O exemplo usa os valores já salvos (o formulário só grava ao salvar).
Validação em `src/domain/configuracoes.py`, testada em `tests/test_configuracoes.py`.

Rearranjo de elementos em 25/09/2026 (só interface, sem regra de negócio): na ficha do
cliente, o botão "Ver contrato →" passou para o cabeçalho do cartão Contrato ativo e
"Dados pessoais" ocupa a largura total em grade de 3 colunas (2 abaixo de 1100px, 1 abaixo
de 640px), sem quebrar CPF, CNH e e-mail no meio; o ícone de "Copiar mensagem de cobrança"
fica centralizado no botão; as colunas de valor de Cobranças > Pagas, Manutenção > Histórico
e Documentos ficam alinhadas à esquerda, como o cabeçalho (exceção deliberada à regra
"números à direita" do `Design_UI.md`); Configurações usa toda a largura da página; e os
selos de status/situação de tabelas e listas têm largura única (`--selo-largura`, 104px, nunca
maior que a coluna), com o texto centralizado.

Correção em 22/09/2026: a sessão de login ficava apenas em `st.session_state`, que o
Streamlit descarta a cada refresh completo do navegador — o usuário logado caía na
tela de login ao atualizar a página. Agora o refresh token é guardado num cookie do
navegador (`streamlit-cookies-controller`) e a sessão é restaurada automaticamente a
partir dele; um segundo cookie, renovado a cada requisição e com validade de 30
minutos, mantém a regra de expiração por inatividade mesmo entre refreshes.

Correção em 24/09/2026: o F5 ainda derrubava a sessão por dois motivos. (1) O login
chamava `st.rerun()` logo após pedir a gravação do cookie, e o Streamlit descartava o
componente antes de o navegador executá-lo; agora o formulário é esvaziado e a mesma
execução segue até a página, sem rerun. (2) O Supabase rotaciona o refresh token (uso
único) nas renovações automáticas do access token, e o cookie ficava com um token já
consumido; `sincronizar_refresh_token_cookie()` (`src/db.py`), chamada a cada execução
em `require_login()`, regrava o cookie sempre que o token muda. Testes em
`tests/test_sessao_cookie.py`.

Validação local em 21/09/2026:

- Testes pytest de regras, exportação, paginação, login e telas com serviços simulados.
- Todas as migrations então existentes executadas em PostgreSQL embarcado (PGlite 0.5.8).
- Roteiro `supabase/verificar_fluxos.sql` executado com rollback: contrato duplicado,
  pagamento parcial/total, preservação da parcela parcialmente paga no encerramento,
  cancelamento de futuras sem pagamento, vistorias, plano e conclusão de manutenção,
  custo total e resultado financeiro.
- `seed_demo.sql` executado duas vezes, sem duplicar o cenário.

**Validação em produção (22 e 23/09/2026):** as 13 migrations estão aplicadas no
Supabase de destino (as 7 que ficaram pendentes por um tempo foram aplicadas
manualmente no SQL Editor; o PostgREST só reconheceu os objetos novos depois do
restart do projeto). Login do dono confirmado: as permissões do papel
`authenticated` (`20260921154000_permissoes_authenticated.sql`) e a RLS restrita
ao UUID do dono (`20260922000000_restringe_rls_ao_dono.sql`) funcionam — o
Dashboard carrega sem erro de permissão. A RPC `rpc_finalizar_manutencao` passou
a receber `payload jsonb` (`20260922010000_finalizar_manutencao_payload_jsonb.sql`)
e o roteiro `supabase/verificar_fluxos.sql` foi executado em produção (23/09) sem
falhas; ele termina em `ROLLBACK`, então não deixa dados.

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
   - `20260921154000_permissoes_authenticated.sql`: permissões do papel `authenticated` (a RLS continua decidindo as linhas).
   - `20260922000000_restringe_rls_ao_dono.sql`: RLS e Storage só para o UUID do dono (ajuste o UUID em `is_dono()` antes de aplicar).
   - `20260922010000_finalizar_manutencao_payload_jsonb.sql`: `rpc_finalizar_manutencao` passa a receber `payload jsonb`.
   - `20260928120000_portal_locatario.sql`: portal do locatário (Fase 7) — vínculo `clientes.auth_user_id`, tabela `trocas_oleo`, cobrança `multa_manutencao`, multa fixa em `configuracoes`, RPCs e bucket `trocas_oleo`. Veja "Portal do locatário" abaixo.
   - `20261002120000_idempotencia_operacoes.sql`: coluna `chave_operacao` e índice único em `pagamentos`, `manutencoes`, `documentos_moto` e `historico_km`, e `rpc_registrar_manutencao` passa a devolver o resultado do primeiro envio quando a chave se repete (Etapa 7 do plano de UI/UX). Rode `supabase/verificar_fluxos.sql` no projeto de homologação depois de aplicar.
   - `20261005120000_encargos_fixos.sql`: encargo de atraso fixo (decisão de negócio, seção 14.1 do plano) — `configuracoes` ganha `multa_atraso_valor` (R$ 15,00) e `encargo_diario_valor` (R$ 7,00) e perde `multa_atraso_percentual`, `juros_mensal_percentual` e `carencia_dias`. **Aplique antes de publicar esta versão do app**, que já não lê as colunas antigas.
   - `20261005130000_contrato_indeterminado.sql`: `rpc_criar_contrato_com_vistoria` deixa de exigir `data_fim_prevista` (contrato por prazo indeterminado, seção 14.4 do plano).
   - `20261005140000_caucao_danos.sql`: danos descontados da caução no encerramento (seção 14.3) — `contratos` ganha `caucao_desconto_danos`, `caucao_valor_devolvido` e `descricao_danos`; `rpc_encerrar_contrato` e `rpc_encerrar_contrato_com_vistoria` trocam `p_caucao_devolvida` por `p_valor_danos` e `p_descricao_danos` (as versões antigas são removidas). **Aplique antes de publicar esta versão do app.**
   - `20261005150000_manutencao_faixa_km.sql`: faixa de km nos itens de manutenção (seção 14.5) — `itens_manutencao` e `moto_plano_manutencao` ganham `intervalo_minimo_km` (início do alerta; `intervalo_km` continua sendo o máximo, em que o item vence), a view `vw_alertas_manutencao` é recriada e o catálogo padrão passa a ter "Kit de tração" e "Patins de freio" de 3.000 a 5.000 km (renomeia os itens genéricos antigos só se ainda estiverem no valor original).
3. Se a integração GitHub já aplica as migrations, confira o histórico antes de
   executá-las manualmente. Não reaplique migrations antigas. Pela CLI, revise o
   projeto conectado com `supabase link` e use `supabase db push`.
4. Rode `supabase/seed.sql` para o catálogo, caso ainda não tenha sido aplicado.
5. Em homologação, execute `supabase/verificar_fluxos.sql`, `supabase/verificar_portal_locatario.sql` e `supabase/verificar_regras_negocio.sql`. Os roteiros usam `ROLLBACK`.
6. Reinicie o aplicativo com as dependências de `requirements.txt`.

Referência: [migrations do Supabase](https://supabase.com/docs/guides/deployment/database-migrations).

## Portal do locatário (Fase 7)

O locatário entra com **login completo** por **CPF + senha** (o app converte o CPF no e-mail
interno `<cpf>@portal.example.com` do Supabase Auth; o dono continua entrando com e-mail) e vê só a tela
"Troca de óleo": moto e contrato ativos dele, situação do óleo e o formulário para
reportar a troca com **foto do painel (hodômetro)** e **foto da nota fiscal** (cláusula 4.13
do contrato). O dono continua com o app completo; o menu depende do papel (`rpc_meu_papel`).

**Segurança.** As tabelas seguem com RLS só para o dono (`is_dono()`); o locatário não tem
acesso direto a nenhuma tabela. Ele lê e grava apenas por RPCs `SECURITY DEFINER`
(`rpc_portal_locatario`, `rpc_registrar_troca_oleo_locatario`), que o identificam por
`auth.uid()` e só enxergam o contrato ativo dele. No Storage, o bucket `trocas_oleo` é
privado (só imagens, até 10 MB): o locatário só envia para a própria pasta e não lê nem
sobrescreve arquivos; o dono vê as fotos por URL assinada na ficha do cliente (aba "Portal").
O cadastro público continua desativado e a `service_role` nunca é usada pelo app.

**Como liberar um locatário.** Na ficha do cliente, aba "Portal", o dono clica em **"Criar
acesso"**. O app chama a Edge Function `criar-locatario`, que cria o usuário no Supabase Auth
(e-mail interno do CPF, senha **aleatória e individual**, nunca uma senha padrão) e o vincula
ao cliente. O app mostra o CPF e a senha uma única vez (a senha não é gravada em lugar
nenhum): entregue-os ao locatário. Ele pode trocar a senha no portal ("Alterar minha senha"),
mas não é obrigado. "Gerar nova senha" redefine a senha e "Remover acesso" exclui o login.
Não há "esqueci minha senha": quem redefine é o dono. O bloqueio de tentativas do Supabase
Auth protege contra tentativas repetidas de senha.

**Edge Function `criar-locatario`** (`supabase/functions/criar-locatario/index.ts`). Criar,
redefinir e excluir usuários exige a `service_role`, que nunca vai para o app nem para o
repositório: a função roda dentro do Supabase, onde essa chave é um segredo injetado
automaticamente (`SUPABASE_SERVICE_ROLE_KEY`). Ela só atende o **dono** (repassa o JWT de quem
chamou e confere `rpc_meu_papel() = 'dono'`), monta o e-mail a partir do CPF do cadastro e
gera a senha com gerador criptográfico. O app só usa a anon key e a sessão do usuário.

Publicar (uma vez por projeto Supabase — dev e produção são projetos diferentes):

```bash
supabase login
supabase functions deploy criar-locatario --project-ref <ref-do-projeto>
```

Sem publicar a função, "Criar acesso" mostra um erro. Confira no painel: Edge Functions >
`criar-locatario` (com "Verify JWT" ligado, que é o padrão) e os logs em caso de falha.

**Regras da troca.** O hodômetro não pode ser menor que o último registrado. A troca grava
uma manutenção preventiva concluída (custo zero), reinicia o plano de óleo da moto e lança o
km no histórico. Se o km informado passar de `última troca + intervalo` (1.000 km no plano
padrão), é gerada a cobrança **fixa** `multa_manutencao`, com o valor definido em
Configurações > "Multa por troca de óleo fora do intervalo". Valor 0,00 (padrão) não cobra
multa. O app ainda não tem tela para cancelar cobrança: se a foto não confirmar o km, a
multa precisa ser cancelada direto no banco (`cobrancas.status = 'cancelada'`).

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
4. Crie contrato com caução e vistoria (prazo indeterminado, semanal). Compare a prévia
   com as parcelas geradas (caução e 1ª semana vencem na data de início); confira que a
   moto deixa de aparecer entre as disponíveis.
5. Registre pagamentos em dia, atrasado, parcial e total. Confira principal separado
   dos encargos (R$ 15 no vencimento + R$ 7 por dia, só locação), saldo residual e
   recusa de pagamento superior ao saldo.
6. Suba o km até o limite preventivo. Abra manutenção com peças e mão de obra; conclua
   o serviço. Confira custo total, status da moto e reinício apenas dos itens marcados.
7. Cadastre documento vencido e confira destaque no Dashboard. Anexe comprovante,
   abra a URL assinada, regularize e crie o próximo ano pela sugestão de vencimento vazio.
8. Anexe fotos à entrega. Encerre contrato com devolução e avaria, informando o dano
   (confira o valor a devolver da caução e, com dano maior que a caução, a cobrança do
   excedente); compare checklists.
   Confira preservação de dívida parcial, cancelamento das futuras sem pagamento e km final.
9. Compare Dashboard e relatórios com as consultas no banco. Caução não é receita.
   Exporte CSV e Excel e confira acentos, valores e período. Custo/km sem leitura suficiente
   fica vazio; o cálculo usa a distância observada, sem extrapolar leituras ausentes.
10. Gere e baixe o backup. Confira as 15 tabelas e as contagens em `manifesto.json`.
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

## Estilização do painel

A interface segue um design system em camadas: **tokens → `estilos.css` → componentes → páginas**.

- `src/ui/estilos.css` é o design system: tokens (`:root` com cores, espaçamento 4–48px, raios 6/8/10/14/18px, sombras, tipografia) e, na ordem, base, tipografia, layout, barra lateral, cartões, KPI, botões, campos, tabelas, selos, alertas, modais, estados vazios, login e responsivo.
- `src/ui/estilos_escuro.css` só redefine os tokens e ajusta os widgets nativos do Streamlit; regras novas devem usar `var(--…)`, nunca cores fixas.
- `src/ui/tema.py` carrega os dois arquivos e decide o modo (claro, escuro ou o do sistema).
- `src/ui/componentes.py` monta o HTML com classes do design system: `cabecalho_pagina`, `kpi`/`kpi_grade`, `cartao_html`, `selo_situacao`, `chip_placa`, `item_alerta`, `estado_vazio`/`mostrar_vazio`, `tabela_html`, barras de ocupação e proporção.

Botões: primário (grafite no claro, amarelo no escuro), secundário, terciário e destrutivo (contorno vermelho; use a chave `perigo_*` no `st.button`). Estados de status usam sempre bolinha + texto, sem depender só da cor.

Ações por linha usam `botao_acao(alvo, acao, chave, ajuda=...)` (`componentes.py`): ícone Material + texto real (nome acessível), alvo de 44 × 44 px (`--alvo-min`), com o texto sempre visível (nenhuma ação depende só de ícone ou dica). O vocabulário fica em `ACOES` (Abrir, Editar, Pagar, Concluir, Cancelar, Regularizar, Comprovante, Atualizar km, Comparar); não use glifos como `→ ✓ ✎ ›` em rótulos. O retorno das fichas é `botao_voltar("motos", chave)`. Detalhes em `Arquivos/Design_UI.md`.

Listas e abas seguem um padrão único em `src/ui/listas.py`: `barra_filtros(prefixo, opcoes, padrao, contagens=..., busca="Buscar por ...")` (pílulas que quebram de linha + busca + `.resumo(n)` com resultados, filtros ativos e "Limpar filtros"), `paginar`/`rodape_paginacao` (Anterior, informação da página, Próxima e itens por página; aritmética em `src/domain/paginacao.py`) e `abas`/`aba_ativa` (abas nativas que quebram de linha, lembram a aba ativa e só executam a aba aberta). Filtro, busca, página e aba sobrevivem a abrir uma ficha e voltar. O menu do dono é agrupado por área (Operação, Cadastros, Frota, Gestão, Sistema) em `app.py`, sem mudar as rotas. Nenhuma página monta pílulas, abas ou paginação na mão (`tests/test_listas_ui.py`).

Listas interativas (com ações) são cartões de `src/ui/registros.py`, e dados somente leitura são `tabela_html`. Cada registro é `with registro(prefixo, id, titulo, [campo("Vencimento", html), ...], selo=...) as acoes:` dentro de `with lista_registros(prefixo, acoes=N):`; as ações são `botao_acao(acoes, ...)`. O significado vem de classes (`.registro__id`, `.registro__campo`, `<dl>` com `<dt>` rótulo e `<dd>` valor) e de chaves (`lista_`, `reg_`, `regacoes_`), nunca da posição da coluna, então mudar a ordem de um campo no Python não troca o rótulo. A quebra em telas estreitas usa container query (largura da lista, não da janela): ≤ 1000 px as ações ficam ao lado da identidade e os dados abaixo; ≤ 560 px tudo empilha, com as ações logo abaixo da identidade. Não use `st.columns` para montar linhas de lista, nem `st.dataframe`/`st.data_editor` (canvas, sem tema nem celular); as peças e serviços extras de Manutenção são linhas de campos com `Remover`. `tabela_html(cabecalhos, linhas, legenda="...")` tem `<th scope="col">`, papéis ARIA explícitos (valem quando o CSS vira cartões no celular) e nome para leitor de tela; cabeçalho `""` marca coluna decorativa. Protegido por `tests/test_registros_ui.py`.

Formulários usam os campos tipados de `src/ui/formularios.py` e as regras de entrada de `src/domain/entradas.py` (funções puras, `tests/test_entradas.py`). `campo_moeda` mostra o prefixo `R$` e o valor no padrão `1.234,56`; `campo_percentual` e `campo_inteiro(sufixo="%"|"km"|"dias")` desenham a unidade dentro da moldura do campo (CSS pela chave do container, sem alterar o valor digitado); `campo_cpf`, `campo_telefone` e `campo_placa` pedem teclado numérico quando cabe, mostram a máscara (`000.000.000-00`, `(11) 91234-5678`, `ABC-1D23`) e usam a validação do navegador (`validate=`), que mostra o erro ao lado do campo sem apagar nada. A validação de verdade continua no servidor: `decimal_campo(texto, "Rótulo")` e `inteiro_campo` levantam erros que dizem o campo e como corrigir (aceitam `1.234,56`, `1234,56`, `1234.56` e `1.500`). Campos de dinheiro **fora de `st.form`** usam `ao_vivo=True`: o navegador não envia um valor inválido, então o servidor ficaria com o anterior enquanto a tela mostra outro. Obrigatórios levam `*` no rótulo e `legenda_obrigatorios()`.

Linhas de campos usam `with linha_campos([1, 1], "chave") as (a, b):` (cada campo mantém ~12 rem; abaixo disso a linha quebra e empilha na ordem de leitura) e todo rodapé é `rodape_formulario("Salvar", "chave", formulario=..., desabilitado=..., motivo=..., perigo=...)`: Cancelar e a ação principal à direita, a principal por último; em contêiner estreito (≤ 22 rem, vale também dentro de diálogos) empilham em largura total. Dentro de `st.form` os valores só chegam ao enviar, então o motivo vem da validação do envio; fora de formulário o botão fica desabilitado **e o motivo aparece escrito acima dele** (`Descrição: informe o serviço realizado.`). Ações destrutivas (encerrar contrato, cancelar manutenção) listam o que será alterado (`src/domain/encerramento.py` espelha a RPC e lista as cobranças canceladas), exigem marcar a confirmação e oferecem o botão neutro de voltar. O assistente de Novo contrato tem `indicador_etapas` (lista ordenada com `aria-current`; no celular só a etapa atual mostra o rótulo e a linha “Etapa N de 4” cobre o resto), resumo de cliente e moto com `Alterar` e rascunho das condições (`contrato_rascunho`): voltar ou alterar etapas anteriores não perde o que foi digitado. Nenhum formulário é esvaziado após erro (no portal, o formulário só é recriado depois de um envio bem-sucedido). Protegido por `tests/test_formularios_ui.py`.

Todas as páginas montam o cabeçalho com `cabecalho_pagina(titulo, sub=..., acao={"rotulo": "Nova moto", "chave": "motos_nova"})`: a ação primária (no máximo uma, botão do Streamlit com ícone) fica à direita do título no desktop e, quando o cabeçalho estreita, vai para depois da descrição em largura total; a função devolve `True` quando o botão é clicado (`"formulario": True` dentro de `st.form`). Listas vazias usam `vazio_lista(...)`, que informa o motivo (filtro/busca ou ainda sem cadastros) e o próximo passo.

Feedback, carregamento e recuperação (Etapa 7 do plano de UI/UX): nenhuma tela usa mais `Alterações salvas.`. Cada operação confirma o que mudou (`Moto ABC-1D23 cadastrada.`, `Pagamento de R$ 450,00 registrado. Cobrança quitada.`, `Contrato de Maria encerrado. A moto ABC-1D23 está disponível.`), com os textos em `src/domain/mensagens.py` (funções puras). `feedback.concluir(aviso)` (`src/ui/feedback.py`) guarda a mensagem e reexecuta a página: confirmação simples vira **toast** (embaixo e centralizado, inteiro, sem cobrir a ação do cabeçalho e deixando passar o clique) e o que pede atenção ou próximo passo (contrato criado, foto que falhou) vira **alerta** que fica na tela. Falhas passam por `src/domain/erros.py` (`classificar_erro`) e `proteger()` mostra cada categoria com ícone e ação próprios: validação (corrigir o campo), sessão expirada (`Entrar novamente`), sem permissão, indisponibilidade do serviço (`Tentar novamente` nas consultas; em formulários o que foi digitado continua nos campos). Ao confirmar, o botão do rodapé (e os de chave `ocupa_*`) vira `Salvando…` no instante do clique e não aceita outro clique até a execução terminar (script em `feedback.py`, estilo `button[data-ocupado]`). A proteção de verdade contra duplicidade é a **chave de operação**: cada envio leva um uuid (`feedback.chave_operacao(nome, conteúdo)`; a mesma chave vale enquanto o conteúdo for o mesmo) e o banco recusa a segunda gravação (pagamentos, manutenções, documentos e leituras de km; motos, clientes, contratos e vistorias já têm chave natural). Uploads (fotos, comprovantes) mostram `st.spinner`. Protegido por `tests/test_feedback_ui.py`, `tests/test_erros.py`, `tests/test_mensagens.py` e `tests/test_operacoes.py`.

Fichas e painéis (Etapa 6 do plano de UI/UX): Moto, Cliente, Contrato e a comparação de vistorias usam `cabecalho_ficha(ficha_identidade(...), acoes)` e `faixa_dados([...])` (`src/ui/componentes.py`); painéis lado a lado são `with paineis("chave") as (principal, lateral):` e empilham quando o contêiner perde largura (também o par Hoje/Alertas do Dashboard). KPIs encolhem o valor com a largura do cartão. Ao voltar de uma ficha, a lista mantém página, filtro e busca e traz o registro de origem à vista (`lembrar_registro`/`restaurar_posicao` em `src/ui/listas.py`). Cada aba de Relatórios tem um resumo em texto (`destaques`, `src/domain/relatorios.py`) além das barras. Protegido por `tests/test_fichas_ui.py`.

## Testes de navegador (UI/UX)

`e2e/` contém a suíte Playwright do `Arquivos/Plano_Melhorias_UI_UX.md` (Etapa 0), separada
de `tests/`: mede overflow, alvos de toque, diálogos e erros de console em cinco larguras,
dois temas e Chromium/Firefox/WebKit, contra o projeto Supabase de **desenvolvimento**.
`pytest` roda só `tests/`; `pytest e2e` roda a suíte de navegador. Instalação, variáveis de
ambiente e opções em `e2e/README.md`; inventário em `Arquivos/Inventario_UI_UX.md`;
achados curados em `Arquivos/Achados_UI_UX.md`; massa de dados extremos em
`supabase/seed_e2e.sql`.

Robustez visual (Etapa 8 do plano de UI/UX): sem `nth-child` nem inversão de `st.dataframe` no modo escuro; os `style=` estáticos das páginas viraram classes do design system (só largura de barra e cor de avatar seguem inline); pilhas de fonte com fallback do sistema; inventário dos `data-testid` inevitáveis em `Arquivos/Design_UI.md` (seção 9). Protegido por `tests/test_robustez_ui.py`. As fontes agora são locais (`static/fontes/`, `src/ui/fontes.css`; exige `enableStaticServing` no `config.toml`). Pendente: medição com Lighthouse (seção 10 do `Design_UI.md`).

Homologação (Etapa 9 do plano de UI/UX): a suíte `e2e/` agora audita acessibilidade com axe-core (crítico/grave reprovam em `--e2e-estrito`), percorre as páginas só com teclado, testa zoom 200%, reflow a 320 px, texto a 200%, espaçamento WCAG, paisagem e rede/CPU reduzidas, e compara capturas com uma referência (`--atualizar-referencia`, `--tolerancia-visual`). `.github/workflows/ci.yml` roda `pytest` e o e2e do login em Chromium, Chromium móvel, Firefox e WebKit. Correções de acessibilidade na marcação do Streamlit ficam em `src/ui/acessibilidade.py`; o contraste dos tokens é protegido por `tests/test_contraste_tokens.py`. Resultado, exceções e pendências: seção 11 de `Arquivos/Design_UI.md`. Falta o que só você pode fazer: gravar os 10 fluxos no banco de dev e testar em aparelhos reais (`Arquivos/Roteiro_Homologacao_Manual.md`).
