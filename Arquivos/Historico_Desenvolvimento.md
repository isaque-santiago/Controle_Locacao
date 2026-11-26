# Histórico do desenvolvimento

Diário do projeto: fases, entregas, correções, validações e estado das cargas de dados, cada qual com a situação **na data em que foi escrita**.
É aqui que se registra o que foi feito; o [README](../README.md) apresenta o projeto e a [Referência técnica](Referencia_Tecnica.md) descreve como o sistema funciona hoje.

**Como registrar:** acrescente uma entrada nova na seção [Registro](#registro), no topo, com o título `### dd/mm/aaaa: assunto`. Não reescreva entradas antigas; se algo mudou, registre a mudança numa entrada nova.

> Frases como «ainda sem tela» ou «pendente» valem para a data da entrada. Entradas anteriores à migração (até 06/10/2026) descrevem a
> interface em Streamlit (`app.py`, `pages/`, `src/ui/`, `st.*`, `streamlit-cookies-controller`), removida na Fase 4: esses arquivos não existem mais.
> As entradas anteriores a este arquivo vieram do antigo README e mantêm o texto original, inclusive referências a «seções» que hoje estão na Referência técnica.

## Registro

### 26/11/2026: organização da documentação

O README acumulava instalação, referência e diário. O diário passou para este arquivo, o funcionamento atual para a [Referência técnica](Referencia_Tecnica.md)
e o README ficou só com apresentação, instalação e uso. O `CLAUDE.md` passou a registrar onde cada coisa é escrita.

## Conector do claude.ai: etapas 1 a 3 (17 e 24/11/2026)

- **Conector do claude.ai (etapa 1 da seção 24 do plano; 17/11/2026).** `POST /mcp` (servidor MCP remoto, JSON-RPC sobre HTTP) com OAuth
  2.1: registro dinâmico de cliente (`/oauth/register`), PKCE S256 e callback fixo do claude.ai (`src/web/rotas/conector.py`, regras
  puras em `src/domain/conector_oauth.py` e `conector_mcp.py`). O dono entra com o login do app e autoriza o Claude numa tela de
  consentimento (só donos; o CSP libera o destino do Claude apenas nessa tela). Os tokens são **sem estado** (Fernet com
  `CONECTOR_CHAVE`; trocar a chave revoga tudo; sem a chave o conector fica desligado e todas as rotas dão 404). Nesta etapa a
  única ferramenta é `ping` (só leitura): não lê nem grava o banco. As ferramentas de verdade só **propõem** lançamentos; aprovar,
  editar e apagar nunca serão ferramentas. Variáveis: `CONECTOR_CHAVE` (chave Fernet) e `CONECTOR_URL_BASE` (endereço público
  do app, ex.: `https://SEU-SUBDOMINIO.duckdns.org`; evita depender do cabeçalho Host); `CONECTOR_PERMITE_LOOPBACK=1` só para testes
  locais. Como conectar: Claude > Personalizar > Conectores > Adicionar conector personalizado, URL `https://SEU-SUBDOMINIO.duckdns.org/mcp`,
  deixar a autenticação como detectada (registro automático).
- **Caixa de pendências de lançamento (etapa 2 da seção 24 do plano; 24/11/2026; só banco e regras, ainda sem tela nem ferramentas no
  conector).** O chat do claude.ai nunca grava no financeiro: ele **propõe** um pagamento ou uma despesa (`rpc_pendencia_criar`) e um usuário
  dono aprova, edita-e-aprova ou recusa (`rpc_pendencia_aprovar`, `rpc_pendencia_recusar`). Só na aprovação o registro é gravado, numa
  transação única e pelos gatilhos de sempre (a cobrança fica paga). Migration `20261124120000_pendencias_lancamento.sql`
  (roteiro `supabase/verificar_pendencias.sql`, só em dev, termina em ROLLBACK): tabela `pendencias_lancamento` (só o dono lê; ninguém
  grava direto), usuário de serviço `servico_conector` (mesmo padrão do WhatsApp: não lê tabela nenhuma, só chama as RPCs), idempotência por
  `chave_operacao`, trava de 200 pendências em aberto e consultas mínimas para o chat (`rpc_conector_cobrancas_abertas` por nome, CPF parcial
  ou placa, devolvendo só os 4 últimos dígitos do CPF; `rpc_conector_veiculos`; `rpc_conector_minhas_pendencias`). Avisos de divergência:
  cobrança não identificada, paga, cancelada, valor acima do saldo e veículo não encontrado **bloqueiam** a aprovação; pagamento parcial,
  duplicada, sem veículo e data no futuro só avisam. Regras puras (normalização, avisos, identificar o cliente por nome, CPF parcial e placa)
  em `src/domain/pendencias.py`, espelhadas no SQL. Para ligar o conector ao banco (etapa 4), crie o usuário em Authentication > Users e rode
  `insert into servico_conector (user_id) select id from auth.users where email = 'conector@exemplo.com';`.
- **Escrita direta do conector (etapa 3 da seção 24; 24/11/2026; só banco e regras, ainda sem as ferramentas no conector).** Decisão do dono:
  sem fila de aprovação; o chat **grava direto** o que está limpo e, na dúvida, **não grava** e devolve o motivo para o Claude perguntar na
  conversa. Migration `20261124130000_escrita_direta_conector.sql` (roteiro `supabase/verificar_escrita_direta.sql`, só em dev, termina em
  ROLLBACK): `rpc_conector_registrar_pagamento` (grava se a cobrança foi identificada, o valor é igual ao saldo, sem duplicidade nem data
  futura e **até R$ 10.000,00**), `rpc_conector_registrar_despesa` (**até R$ 5.000,00**, exige o veículo ou a descrição dele),
  `rpc_conector_cadastrar_cliente` (CPF válido, ou **CPF provisório** `0000000000N` com `[CPF PROVISÓRIO]` na observação; recusa CPF repetido e
  homônimo não confirmado), `rpc_conector_cadastrar_veiculo` (placa válida e única) e `rpc_pendencia_desfazer` (só dono, só lançamentos
  automáticos e só em **7 dias**; apaga o registro e reabre a cobrança; recusa se o registro já tem outros dados ligados). Cada RPC devolve
  `{"gravado": true, ...}` ou `{"gravado": false, "motivo": "duvida" | "acima_do_teto" | "cpf_ja_cadastrado" | "homonimo" | "placa_ja_cadastrada", "mensagem"}`;
  dado inválido levanta erro em português. Tudo o que o chat grava fica em `pendencias_lancamento` (histórico e auditoria, com
  `decisao_automatica`, quem pediu e o trecho do chat). Regras puras em `src/domain/pendencias.py` (tetos, o que é «limpo», normalização de
  cliente e veículo, CPF provisório).

## Importação dos dados reais (modelo pronto; parcela 1 em produção; parcela 2 pendente)

Desenho, conflitos nos dados e decisões: `Arquivos/dados/Importacao_Dados_Reais.md` (seção 16 do plano). A parcela 1 da carga está aplicada em
produção (conferida em 13/11/2026: 32 motos, 16 clientes, 12 contratos, 75 despesas, 72 multas, 5 dívidas); a parcela 2 depende de dados
que ainda faltam (cadastros sem CPF ou com identidade a confirmar e dívidas com saldo conflitante). Oito migrations
preparam o banco para a planilha "PAGAMENTO MOTOS":

- `20261022120000_importacao_veiculos_contratos.sql`: tipo/dono/rastreador/seguro em `motos`; promessa de compra em `contratos`
  (`tipo_contrato`, `numero_parcelas`, `valor_total`, `valor_entrada`, `parcelas_pagas_inicial`, `dia_cobranca`,
  `primeira_cobranca`); `contas`; `conta_id`, `data_estimada` e a forma `abatimento` em `pagamentos`; `rpc_criar_contrato` e
  `rpc_gerar_cobrancas_pendentes` respeitam a promessa (a janela móvel nasce em `primeira_cobranca`, não na data antiga de início).
- `20261022130000_importacao_despesas_socio_dividas.sql`: `fornecedores`, `despesas`, `movimentos_socio`, `dividas`,
  `pagamentos_divida`, `vw_saldo_dividas` e as colunas `custo_despesas` e `resultado_com_despesas` em `vw_resultado_moto`.
- `20261022140000_importacao_multas.sql`: `multas_transito` e `vw_multas_locatario`.
- `20261022150000_importacao_rastreio_lotes.sql`: `importacoes_lote` (idempotência e desfazer por lote).
- `20261022160000_importacao_capital_veiculos.sql`: capital em veículos sem operação (Etios, Celta): `placa_provisoria`, categoria `aquisicao`,
  `pago_por`, `a_confirmar`, dívida `emprestimo`, `dividas_vencimentos`, aporte ligado ao veículo e `vw_capital_veiculo`.

- `20261103120000_contrato_varias_motos.sql`: contrato com mais de uma moto (`contrato_motos`, moto principal em `contratos.moto_id`,
  `motos_vinculadas` em `rpc_criar_contrato`); `supabase/verificar_contrato_varias_motos.sql`.
- `20261103130000_compra_parcelada.sql`: dívida `compra_parcelada` com entrada, calendário de parcelas, `rpc_criar_compra_parcelada`,
  `rpc_pagar_parcela_divida` e `vw_parcelas_divida`; `supabase/verificar_compra_parcelada.sql`.
- `20261103140000_capital_inclui_compra_parcelada.sql`: `vw_capital_veiculo` soma também as compras parceladas.

**Telas (novo contrato):** o assistente de `/contratos/novo` aceita até 4 motos vinculadas na etapa Moto (a principal fica com a parcela e
a receita), o tipo "Promessa de compra" na etapa Condições (entrada, número de parcelas, parcelas já pagas, dia e primeira cobrança) e mostra
o total e a prévia da agenda na confirmação. A lista de contratos exibe "+N motos" e "Promessa de compra"; a ficha mostra as motos do contrato
e o total, a entrada e as parcelas pagas/restantes. A vistoria de entrega continua só na moto principal. As telas de dívidas (compra parcelada)
ainda não existem.

Aplicar **primeiro no projeto de desenvolvimento** e conferir com `supabase/verificar_importacao_modelo.sql` (desfaz tudo ao final).
Produção só depois de backup e autorização do dono. Regra pura da agenda: `src/domain/agenda_cobrancas.py` (`tests/test_agenda_promessa.py`).

**Estado em 23/10/2026:** as migrations 1 a 5 estão aplicadas no dev e cinco cargas de dados já rodaram lá (veículos, despesas, multas, sócio,
dívidas sem conflito, capital do Etios e do Celta, e 8 clientes com 5 contratos de identidade confirmada). As cargas são SQL gerado fora do
repositório (contêm CPF, telefone e dados reais), idempotente por lote (`importacoes_lote`) e com SQL para desfazer. Faltam os demais
locatários e contratos, três dívidas com saldo conflitante e a carga em produção. Detalhes, decisões (D1 a D8), conflitos e pendências em
`Arquivos/dados/Importacao_Dados_Reais.md`.

## Migração do frontend: Streamlit para FastAPI (Fases 1 a 5)

O Streamlit foi removido (Fase 4, parte F). Plano, fases e decisões em
[Arquivos/Analise_Migracao_Frontend.md](Analise_Migracao_Frontend.md). **Fase 1 (fundação) concluída (06/10/2026):** app, login/logout, sessão,
papéis, CSRF, erros e biblioteca de componentes. **Fase 2 (páginas piloto) concluída (06/10/2026):**
Dashboard (`/`) e Motos (`/motos`, `/motos/{id}`). **Fase 3 (demais páginas) concluída (08/10/2026):** Clientes (`/clientes`, `/clientes/{id}`), Contratos
(`/contratos`, `/contratos/{id}`, `/contratos/novo`), Cobranças (`/cobrancas`), Manutenção (`/manutencao`), Vistorias
(`/vistorias`), Documentos (`/documentos`), Relatórios (`/relatorios`), Configurações (`/configuracoes`) e Portal do
Locatário (`/portal`). Todas as telas estão migradas e o Streamlit saiu na Fase 4.

**Fase 3, andamento: Clientes concluída (07/10/2026).** Lista, ficha com quatro abas (Resumo com cartão de
contrato ativo, Contratos, Pagamentos paginados de 10 em 10 e Portal), cadastro e edição em diálogo, em
`src/web/rotas/clientes*.py` e `src/web/templates/clientes/`. A aba Portal cria o acesso do locatário, gera nova
senha e remove o acesso; a senha só existe na resposta do POST (sem sessão, URL ou cache, `Cache-Control: no-store`)
e as fotos das trocas abrem por redirecionamento para URL assinada de 5 minutos. Foi aceita sem a comparação lado a
lado com o Streamlit nos passos finais (decisão do proprietário).

**Fase 3, andamento: Contratos concluída (07/10/2026).** Lista (abre nos ativos; filtro por situação, busca por
cliente ou placa, paginação) e ficha com faixa de dados e abas Cobranças, Vistorias e Manutenções
(`rotas/contratos.py`, `templates/contratos/`). **Novo contrato** é um assistente de quatro etapas (Cliente, Moto,
Condições, Confirmar) em `rotas/contratos_novo.py`: cada etapa tem URL própria (`/contratos/novo?etapa=N`), funciona
sem JavaScript e o rascunho (escolhas e texto digitado, mesmo inválido) fica em `sessao.rascunho_contrato`, então dá
para voltar e revisar; a criação usa a RPC única de contrato com vistoria de entrega. **Encerrar contrato**
(`rotas/contratos_encerramento.py`) abre um diálogo com a vistoria de devolução, danos descontados da caução e uma
prévia (caução a devolver, excedente cobrado, cobranças canceladas) recalculada pelo servidor ao mudar a data ou os
danos. Regras puras em `src/domain/contratos_lista.py`, `formulario_contrato.py` e `encerramento.py`. Fotos da
vistoria continuam sendo anexadas na página Vistorias (como no Streamlit).

**Fase 3, andamento: Cobranças concluída (07/10/2026).** Abas Hoje, Atrasadas, Próximos 7 dias e Pagas com contagem
e URL própria (`?aba=`), resumo de atraso no cabeçalho, encargos por cobrança atrasada e paginação de 10 em 10
(`rotas/cobrancas.py`, `templates/cobrancas/`; regras puras em `src/domain/cobrancas_lista.py`). **Registrar pagamento**
(`rotas/cobrancas_pagamento.py`) abre em diálogo pelo HTMX e também como página sem JavaScript (é para onde o "Pagar" do
Dashboard leva): a prévia dos encargos é recalculada pelo servidor quando a data muda, a validação é por campo
(`src/domain/formulario_pagamento.py`: principal > 0 e <= saldo) e a gravação leva `chave_operacao`, então reenviar o
mesmo formulário não lança o pagamento duas vezes. **Mensagem de cobrança** (`rotas/cobrancas_mensagem.py`) mostra o
texto pronto para o WhatsApp com botão de copiar (`data-copiar` em `static/js/app.js`; a CSP não aceita script inline).
**Cancelar cobrança (12/11/2026).** Em Cobranças, o botão **Cancelar** (abas Hoje, Atrasadas e Próximos 7 dias) abre um diálogo
que pede o **motivo** (3 a 200 caracteres) e, sem JavaScript, o mesmo formulário abre como página (`rotas/cobrancas_cancelamento.py`).
Regra confirmada com o dono: só cobrança em aberto **e sem nenhum pagamento registrado** pode ser cancelada (`src/domain/cancelamento_cobranca.py`);
com pagamento, parcial que seja, o botão some e o estorno continua sendo feito no banco. Cancelada, a cobrança sai da dívida, das listas e dos avisos de WhatsApp
e não é gerada de novo. A gravação é a RPC `rpc_cancelar_cobranca` (migration `20261112140000_cancelar_cobranca.sql`, que acrescenta
`cobrancas.motivo_cancelamento` e `cancelada_em`; só o dono; roteiro `supabase/verificar_cancelar_cobranca.sql`, só em dev, termina em ROLLBACK).
**Fase 3, andamento: Manutenção concluída (07/10/2026).** Abas Alertas, Histórico e Catálogo; filtros, busca e
paginação; registro com itens do plano, peças adicionais, prévia de custos e idempotência; conclusão e cancelamento
de serviços abertos; cadastro, edição e inativação do catálogo. Diálogos têm alternativa sem JavaScript e validação
por campo. Homologada no banco de desenvolvimento e em 320, 390 e 1440 px; 981 testes passaram.

**Fase 3, andamento: Vistorias concluída (08/10/2026).** Lista (filtro por tipo, busca, paginação) e comparação entrega x
devolução com checklist e galeria de fotos por URL assinada (o CSP libera em `img-src` só a origem do Supabase); registro em
duas etapas, em diálogo e em página sem JavaScript, com até 10 fotos de 10 MB (validadas por extensão, tamanho e formato
antes de gravar). Adicionar fotos depois do registro ficou de fora por decisão do proprietário.
**Documentos:** lista com situação, busca por placa e comprovante por link assinado na hora do clique; novo, editar e
regularizar (com comprovante opcional e o cadastro do ano seguinte). **Relatórios:** quatro abas com período na URL, barras
em SVG e exportação CSV e Excel dos mesmos dados da tabela. **Configurações:** encargos, alertas e backup manual (ZIP
baixado por POST, só o dono). **Portal do Locatário** (`rotas/portal.py`): o locatário vê só o contrato ativo dele,
reporta a troca de óleo com a foto do painel e a da nota fiscal e troca a própria senha (`ServicoAutenticacao.alterar_senha`,
PUT em `/auth/v1/user` com o token dele). O contrato do formulário é sempre procurado entre os que a RPC devolve para o
locatário, e ele recebe 403 em todas as telas do dono. Homologadas no banco de desenvolvimento e em 320, 390 e 1440 px;
a suíte inteira passa (1168 testes, em 08/10/2026; os de Cobranças usam relógio congelado em 07/10/2026).

**Recarga automática resolvida (08/10/2026):** em desenvolvimento o armazém de sessões espelha as sessões no arquivo
`.sessoes_dev.json` (ignorado pelo git; só `executar_web.py` o configura, por `LOCACAO_SESSOES_ARQUIVO`, e só vale com
`LOCACAO_AMBIENTE=dev`), então salvar um `.py` reinicia o servidor sem derrubar o login. A recarga é do próprio
`executar_web.py` (o servidor roda como processo filho, reiniciado a cada `.py` salvo em `src/`), e não do `--reload` do
uvicorn, que no Windows manda Ctrl+C ao console e trava quando não há console (preview do Claude). Em produção nada vai a disco.

**Fase 4 concluída** (branch `fase-4-e2e-e-desligamento`; plano em `Arquivos/Analise_Migracao_Frontend.md`).
Partes A (núcleo sem Streamlit), B (suíte Playwright no app novo, ver `e2e/README.md`), C (CI do app novo), D (revisão de segurança:
`Arquivos/Revisao_Seguranca.md`), E (homologação com o proprietário: `Arquivos/homologacao/Roteiro_Homologacao_Manual.md`) e F (remoção do Streamlit:
`app.py`, `pages/`, `src/ui/`, `src/auth.py`, os testes de tela e as dependências `streamlit`, `streamlit-cookies-controller`, `pandas`,
`plotly` e `watchdog`).

**Fase 5 (deploy) publicada em `https://lamotos.duckdns.org` (verificada em 20/10/2026):** `Dockerfile`, `.dockerignore`, dependências de
produção separadas (`requirements.txt`; testes em `requirements-dev.txt`) e job `deploy` na CI (passo a passo em `Arquivos/Deploy_VPS.md`).
Confirmado: DNS (DuckDNS), `ufw` só com 22, 80 e 443, `unattended-upgrades` ativo, SSH só por chave, app no Coolify (Auto Deploy e webhook
desligados, limite de memória), `FORWARDED_ALLOW_IPS` restrito ao IP do Traefik, segredos do GitHub, migrations aplicadas no Supabase de
produção, `/saude`, HSTS/CSP, HTTP→HTTPS, `/componentes` com 404, login e portal do locatário, e monitor UptimeRobot em `/saude`.
Lighthouse medido em 26/10/2026 no app publicado (login, Dashboard, Cobranças, Motos e ficha: desempenho 89–100, acessibilidade 98–100, boas práticas 100, CLS ≤ 0,023; detalhes na seção 10 de `Arquivos/interface/Design_UI.md`).
Backup do Supabase: manual semanal (decisão de 29/10/2026; ver `Arquivos/Deploy_VPS.md`, seção 8). Pendente: roteiro de homologação manual no app publicado.

## Plano de UI/UX no Streamlit: etapas 8 e 9

Robustez visual (Etapa 8 do plano de UI/UX, feita ainda no Streamlit): sem `nth-child` e com pilhas de fonte com fallback do sistema; as fontes são locais (`static/fontes/`, declaradas em `src/web/estilos/app.css`). O Lighthouse foi medido depois, já no app novo (seção 10 do `Arquivos/interface/Design_UI.md`).

Homologação (Etapa 9 do plano de UI/UX): a suíte `e2e/` agora audita acessibilidade com axe-core (crítico/grave reprovam em `--e2e-estrito`), percorre as páginas só com teclado, testa zoom 200%, reflow a 320 px, texto a 200%, espaçamento WCAG, paisagem e rede/CPU reduzidas, e compara capturas com uma referência (`--atualizar-referencia`, `--tolerancia-visual`). `.github/workflows/ci.yml` roda `pytest` e o e2e do login em Chromium, Chromium móvel, Firefox e WebKit. O contraste dos tokens é protegido por `tests/test_contraste_tokens.py`. Resultado, exceções e pendências: seção 11 de `Arquivos/interface/Design_UI.md`. Falta o que só você pode fazer: gravar os 10 fluxos no banco de dev e testar em aparelhos reais (`Arquivos/homologacao/Roteiro_Homologacao_Manual.md`).

## Implementação inicial e reconstrução das telas (até 06/10/2026, Streamlit)

As telas das fases 1 a 7 estão implementadas: cadastros, contratos com vistorias,
cobranças, manutenção, documentos, Dashboard, relatórios, configurações e backup.
As regras existentes foram complementadas com transações para entrega/devolução,
conclusão de manutenção, plano automático de motos e proteção de pagamentos.

Revisão de fidelidade visual ao `Arquivos/interface/Design_UI.md` (22/09/2026): paleta de
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
R$ 700; dano acima da caução zera a devolução e gera uma cobrança de dano com o excedente. O diálogo mostra as avarias anotadas na vistoria de devolução como base para o valor dos danos.

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
minutos, mantém a regra de expiração por inatividade (agora de 90 dias) mesmo entre refreshes.

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

**Aceite externo:** uploads e URLs assinadas do Supabase Storage validados em produção em 26/10/2026 (ver a seção 7 de
`Arquivos/homologacao/Roteiro_Homologacao_Manual.md`). O bucket `trocas_oleo` do portal do locatário também foi validado no mesmo dia. O roteiro de aceite (fluxos 1 a 10) foi executado no app publicado em 26/10/2026, com achados menores listados no Roteiro de homologação. A rodada no celular (POCO M6 Pro) foi feita em 27/10/2026 e gerou a correção das fotos da entrega e da câmera. Ainda pendente:
conferir a câmera no aparelho depois do deploy e revisar no Firefox no aplicativo publicado. O teste local não valida Supabase Storage, infraestrutura
ou publicação. Nenhuma fase é declarada homologada apenas com base nas telas e testes isolados.

## Migrations da atualização de instalações antigas (setembro e outubro/2026)

Lista que ficava no passo «aplique as migrations pendentes» do README. A relação completa está em `supabase/migrations/`.

- `20260921150000_cadastro_moto.sql`: plano e histórico iniciais atômicos, km não regride.
- `20260921151000_fluxos_contratos.sql`: contratos com vistorias e validação de pagamentos.
- `20260921152000_finalizar_manutencao.sql`: conclusão/cancelamento de manutenção aberta.
- `20260921153000_resultado_km.sql`: distância registrada e custo por km na view.
- `20260921154000_permissoes_authenticated.sql`: permissões do papel `authenticated` (a RLS continua decidindo as linhas).
- `20260922000000_restringe_rls_ao_dono.sql`: RLS e Storage só para o dono (ajuste o UUID em `is_dono()` antes de aplicar). A migration `20261105120000_administradores.sql` passa o acesso para a tabela `administradores` (veja "Administradores").
- `20260922010000_finalizar_manutencao_payload_jsonb.sql`: `rpc_finalizar_manutencao` passa a receber `payload jsonb`.
- `20260928120000_portal_locatario.sql`: portal do locatário (Fase 7) — vínculo `clientes.auth_user_id`, tabela `trocas_oleo`, cobrança `multa_manutencao`, multa fixa em `configuracoes`, RPCs e bucket `trocas_oleo`. Veja "Portal do locatário" abaixo.
- `20261002120000_idempotencia_operacoes.sql`: coluna `chave_operacao` e índice único em `pagamentos`, `manutencoes`, `documentos_moto` e `historico_km`, e `rpc_registrar_manutencao` passa a devolver o resultado do primeiro envio quando a chave se repete (Etapa 7 do plano de UI/UX). Rode `supabase/verificar_fluxos.sql` no projeto de homologação depois de aplicar.
- `20261005120000_encargos_fixos.sql`: encargo de atraso fixo (decisão de negócio, seção 14.1 do plano) — `configuracoes` ganha `multa_atraso_valor` (R$ 15,00) e `encargo_diario_valor` (R$ 7,00) e perde `multa_atraso_percentual`, `juros_mensal_percentual` e `carencia_dias`. **Aplique antes de publicar esta versão do app**, que já não lê as colunas antigas.
- `20261005130000_contrato_indeterminado.sql`: `rpc_criar_contrato_com_vistoria` deixa de exigir `data_fim_prevista` (contrato por prazo indeterminado, seção 14.4 do plano).
- `20261005140000_caucao_danos.sql`: danos descontados da caução no encerramento (seção 14.3) — `contratos` ganha `caucao_desconto_danos`, `caucao_valor_devolvido` e `descricao_danos`; `rpc_encerrar_contrato` e `rpc_encerrar_contrato_com_vistoria` trocam `p_caucao_devolvida` por `p_valor_danos` e `p_descricao_danos` (as versões antigas são removidas). **Aplique antes de publicar esta versão do app.**
- `20261005150000_manutencao_faixa_km.sql`: faixa de km nos itens de manutenção (seção 14.5) — `itens_manutencao` e `moto_plano_manutencao` ganham `intervalo_minimo_km` (início do alerta; `intervalo_km` continua sendo o máximo, em que o item vence), a view `vw_alertas_manutencao` é recriada e o catálogo padrão passa a ter "Kit de tração" e "Patins de freio" de 3.000 a 5.000 km (renomeia os itens genéricos antigos só se ainda estiverem no valor original).
- `20261005160000_receita_caucao_retida.sql`: a parte da caução retida para danos (`contratos.caucao_desconto_danos`) passa a contar como receita da moto em `vw_resultado_moto`, como já faz `domain/relatorios.py` nos relatórios (seção 14.3).
