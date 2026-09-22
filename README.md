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
entrega) na criação de contrato. Pendências conhecidas continuam as da seção 6
do `Design_UI.md`: modo escuro e validação em layout mobile.

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

Validação local em 21/09/2026:

- Testes pytest de regras, exportação, paginação, login e telas com serviços simulados.
- Todas as 10 migrations executadas em PostgreSQL embarcado (PGlite 0.5.8).
- Roteiro `supabase/verificar_fluxos.sql` executado com rollback: contrato duplicado,
  pagamento parcial/total, preservação da parcela parcialmente paga no encerramento,
  cancelamento de futuras sem pagamento, vistorias, plano e conclusão de manutenção,
  custo total e resultado financeiro.
- `seed_demo.sql` executado duas vezes, sem duplicar o cenário.

**Aceite externo pendente:** aplicar migrations no Supabase de destino, conferir RLS
com usuário real, uploads/URLs assinadas, executar o roteiro manual, revisar celular
no aplicativo publicado e confirmar deploy. O teste local não valida Supabase Auth,
Storage, infraestrutura ou publicação. Nenhuma fase é declarada homologada apenas
com base nas telas e testes isolados.

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

## Convenções dos relatórios

Receita usa a data de pagamento e exclui caução. Custo de manutenção considera
serviços concluídos, pela data de entrada. Documentos entram na data de regularização.
Essas datas representam o controle disponível no sistema; não há uma tabela separada
de pagamentos a fornecedores. O custo/km representa manutenção dividida pela distância
registrada. Os cálculos financeiros usam `Decimal`; as células do Excel são numéricas.
