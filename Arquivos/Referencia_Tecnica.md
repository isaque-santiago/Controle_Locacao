# Referência técnica

Como o sistema funciona **hoje**: comportamento das telas, regras, segurança e integrações. Instalação e uso estão no [README](../README.md);
o que foi feito e quando, no [Histórico do desenvolvimento](Historico_Desenvolvimento.md).

Ao mudar um comportamento descrito aqui, **corrija o trecho correspondente** em vez de acrescentar uma entrada datada. Os caminhos em
`código` partem da raiz do repositório.

## Nomes: marca e termos técnicos

> **Nomes (16/11/2026).** A marca é **LA Locadora**. Nas telas e mensagens o termo é «veículo»; por dentro (tabelas `motos`, rotas `/motos`, colunas `moto_id`, funções) o nome técnico continua «moto», para não mexer no banco em produção. As mensagens de regra de negócio que vêm do banco são ajustadas na exibição (`src/domain/mensagens_banco.py`). O contrato em PDF também diz «veículo» (a frota tem motos e carros; o quadro do veículo mostra «Motocicleta» ou «Automóvel» conforme o tipo); só a razão social «L.A ALUGUEL DE MOTOS» continua como está.

## Arquitetura da interface

Estrutura: `src/web/` (rotas em `rotas/`, templates Jinja2 em `templates/`, macros dos componentes em
`templates/componentes/macros.html`, estilos em `estilos/app.css`), `static/` (CSS compilado, fontes,
`htmx.min.js` e `app.js`). Regras de negócio seguem em `src/domain`; o acesso ao Supabase, em
`src/services/autenticacao.py` e nos repositórios (o cliente da requisição entra por
`src.db.get_client()`).

- **Camadas:** a rota chama `dados_*.py` (leitura) e `acoes_*.py` (gravação), que chamam os serviços e o
  `src/domain`; os testes de rota trocam esses dois módulos por dados fictícios (`tests/web/conftest.py`).
- **Cache** de leituras (`repositories/consultas.py`): por usuário e por dia, 60 s; sem usuário identificado não
  há cache. O limite de "gerar cobranças uma vez por hora" também é por usuário.

## Sessão e segurança

- A sessão vive na **memória do processo**: o cookie leva só um identificador aleatório (`httpOnly`,
  `SameSite=Lax`, `Secure` em HTTPS) e os tokens do Supabase ficam no servidor.
- **Sessão longa (16/11/2026).** O locatário não quer entrar toda hora: a sessão expira após **90 dias sem uso** (cada uso renova)
  e, no máximo, **1 ano** depois do login (`src/domain/sessao_longa.py`). Os cookies têm validade de 90 dias (não somem ao fechar o
  navegador ou o app do celular). Como a memória do servidor some a cada deploy, o login também grava o cookie `lembrar`: o token de
  renovação do Supabase **criptografado** (Fernet) com a chave `SESSAO_CHAVE`, que só existe no servidor (`src/web/lacre.py`). Sem a
  sessão em memória, o app abre o cookie, renova os tokens e refaz a sessão sem pedir login. Nada vai a disco. **Sem `SESSAO_CHAVE`
  o recurso fica desligado** e reiniciar ou fazer deploy derruba o login de todos. Gere a chave com
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` e guarde-a no Coolify (nunca no repositório;
  trocar a chave desconecta todos).
- **Sair de todos os dispositivos** (`POST /sessao/sair-de-todos`, no menu do dono e no portal do locatário): revoga todos os tokens
  do usuário no Supabase (escopo global) e encerra as sessões do servidor, então nenhum cookie `lembrar` volta a funcionar. Se o
  Supabase falhar, nada muda e a tela avisa. No Supabase, mantenha **sem** limite de sessão (Authentication > Sessions: time-box e
  inactivity timeout desligados ou de 90 dias ou mais), senão ele derruba a sessão antes.
- **Rode com um único worker** (`uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers`
  atrás do proxy, com `--forwarded-allow-ips` restrito ao proxy). Com 2 workers cada um teria as suas
  sessões e o usuário seria deslogado ao acaso.
- Todo POST exige token CSRF (campo `csrf_token` ou cabeçalho `X-CSRF-Token`, que o HTMX envia sozinho).
- Login limitado a 5 falhas por e-mail/CPF e 20 por IP em 15 min (também em memória).
- Cabeçalhos de segurança (CSP sem inline, HSTS em HTTPS, `X-Frame-Options`) saem da aplicação. Por
  causa da CSP não há `style=` nem `<script>` inline nos templates; há testes que garantem isso.

## Padrões de interface

Validados na migração do frontend; reutilize nas telas novas.

- **Lista** (`rotas/motos.py`, `templates/motos/`): filtro, busca e página na URL (`?situacao=&q=&pagina=&por_pagina=`);
  o HTMX troca só `#resultado` (e a restauração do histórico recebe a página inteira); chips são links, então
  funcionam sem JS. A tabela vira cartões conforme a largura **da própria caixa** (container query), não da tela.
- **Nome que leva à ficha** (como no cell-pag): em qualquer lista ou ficha, o nome do cliente e a placa do veículo são
  links para a ficha de cada um. Em tabela recolhível use `rc_titulo(classe, href=..., estica=...)`: a célula leva o
  link (só a partir de 720 px) e o botão que abre/fecha o cartão (só no celular), porque link não pode ficar dentro de
  botão; no celular tocar no nome continua abrindo o cartão. Com `<tr class="linha-link">` o link do título (ou o botão
  "Abrir ficha" com a classe `link-linha`, quando o título leva a outra ficha) estica e a linha inteira abre a ficha
  (Clientes, Veículos e Contratos). Fora do título, use `link_nome(href)` (ou `<a class="link-nome">`). As linhas
  precisam trazer `cliente_id` e `moto_id` (a camada de dados é quem os passa). No Dashboard não há link com "ocultar
  dados" ligado.
- **Ficha com abas** (`macros.abas_remotas`): cada aba carrega o painel por HTMX, com URL própria
  (`/motos/{id}?aba=plano`); o servidor devolve as abas junto do painel (swap fora de banda), então o botão
  voltar do navegador fica coerente. Setas movem o foco, Enter abre.
- **Falha de rede do HTMX** (`static/js/app.js`): `htmx:sendError` e `htmx:timeout` (limite de 60 s, em `htmx-config`)
  mostram um aviso de erro em `#avisos` (ou dentro do diálogo aberto) e ele some na próxima requisição bem-sucedida.
- **Confirmação de ações destrutivas** (`#dlg-confirmar` em `layout_painel.html`, lógica em `static/js/app.js`): em vez do
  `confirm()` do navegador, `hx-confirm="texto"` (HTMX) e `data-confirmar="texto"` (formulário comum) abrem um diálogo próprio;
  `data-confirmar-titulo`, `data-confirmar-rotulo` e `data-confirmar-neutro` personalizam. Usado em: gerar nova senha e remover
  acesso do portal, inativar moto e cancelar o novo contrato.
- **Formulário em diálogo seguro** (`#dlg-form`, `static/js/app.js`): qualquer alteração marca `data-alterado` no diálogo; fechar
  (Cancelar, X, fundo ou Esc) com alterações pede "Descartar alterações?" no diálogo de confirmação. No envio, `form_dialogo` usa
  `hx-sync="this:drop"` e `hx-disabled-elt` (ignora cliques repetidos); formulários comuns recebem `data-enviando` (bloqueio por
  10 s, para não travar downloads) e o botão mostra um anel girando.
- **Ordenação por coluna** (Motos, Clientes e Contratos): `?ordem=campo` (crescente) ou `?ordem=-campo` (decrescente); cada clique no
  cabeçalho cicla crescente → decrescente → ordem padrão. Regras puras em `src/domain/ordenacao.py` (valores ausentes ficam no
  fim) e `COLUNAS_ORDENAVEIS` de cada `*_lista.py`; a macro `tabela(..., ordenacao=)` põe `aria-sort` e o link no `<th>`. O
  cabeçalho some em cartões, então no celular a ordem só vem da URL. Busca, chips e paginação preservam a ordem.
- **Filtros lembrados** (Motos, Clientes, Contratos, Vistorias e Documentos; `<form id="filtros" data-lembrar-filtros>`): o `app.js`
  guarda na aba (`sessionStorage`) a query da URL (busca, filtro, ordem, "por página"). Voltar da ficha pelo "Voltar" ou pelo menu
  para o endereço puro da lista reabre com ela. "Limpar filtros" apaga o guardado; sair da conta apaga tudo.
  Quando a lista está filtrada, o resultado mostra o indicador **Filtro ativo: N de total** com o botão "Limpar filtros" (macro `aviso_filtro`); o
  cabeçalho "N cadastrados" continua sendo o total geral. O servidor não guarda filtro: só o endereço com `?q=` aparece filtrado.
- **Atalhos de teclado** (`static/js/app.js` e `static/js/interativo.js`): `/` foca a busca da página (e, em páginas sem busca própria, abre a busca global),
  `n` aciona o botão marcado com `data-atalho-novo` (o "Novo ..." das listas; `aria-keyshortcuts="n"`), `Ctrl+K` abre a busca global, `g` e depois uma letra
  vai a uma página (`g i` Dashboard, `g o` Contratos, `g b` Cobranças, `g v` Veículos, `g c` Clientes, `g m` Manutenção, `g d` Documentos, `g r` Relatórios; a lista
  fica em `navegacao.ATALHOS_IR` e é lida da própria janela de atalhos) e `?` abre essa janela (também no menu da conta). Só valem sem Ctrl/Alt/Cmd, fora de
  campos de texto e com nenhum diálogo aberto (exceto `Ctrl+K`, que funciona até dentro de um campo).
- **Interatividade** (redesign, Fase 4; JS novo em `static/js/interativo.js`, carregado só no layout do painel; tudo é melhoria progressiva):
  - **Busca global** (`Ctrl+K`, `/` ou o botão "Buscar"): paleta em `<dialog id="dlg-busca">` que consulta `GET /busca?q=` (rota -> `dados_busca` -> serviços;
    regra pura em `src/domain/busca_global.py`: placa com ou sem hífen, modelo, nome e CPF; arquivados ficam de fora; até 5 por grupo; mínimo 2 letras).
    Setas navegam (combobox com `aria-activedescendant`), Enter abre a ficha, Esc fecha e o foco volta ao que estava. Com `?ocultar=1` na URL (modo "ocultar dados
    pessoais" do Dashboard) os resultados saem mascarados. Sem JavaScript, `/busca` abre como página.
  - **Filtros instantâneos**: Veículos, Clientes e Contratos já trocavam só `#resultado` (debounce de 300 ms, `hx-push-url`); **Cobranças** ganhou a busca por cliente ou
    placa, que troca só o painel da aba, mantém `aba` e `q` na URL e filtra as contagens das abas (o resumo de atraso do cabeçalho segue sobre tudo).
  - **Gaveta de pré-visualização**: o botão do olho em cada linha de Veículos, Clientes e Contratos (`GET /motos|clientes|contratos/{id}/previa`, rotas em
    `src/web/rotas/previa.py`; o botão usa `hx-push-url="false"` porque o `#resultado` fica dentro do `<form hx-push-url="true">` e o HTMX herda o atributo; aberta direto, sem `HX-Request`, a rota redireciona para a ficha) carrega os dados principais num diálogo que desliza da direita (`#dlg-gaveta`), com link para a ficha. O foco vai ao título e volta ao botão ao fechar.
  - **Abas e ordenação**: continuam trocando só o painel; o traço da aba aberta entra suave. Tudo com `prefers-reduced-motion`.
  - **Ações em linha**: pagar e cancelar uma cobrança a partir de `/cobrancas` atualizam a lista no lugar (`rotas/cobrancas_na_lista.py`): a resposta traz fora de banda o
    aviso, o resumo, as abas e o painel e fecha o diálogo (`HX-Trigger: dialogo-concluido`). Vindo de outra tela (Dashboard) ou sem JS, segue o redirecionamento de antes.
    Regras e RPCs não mudaram. "Mensagem" já abre num diálogo sem sair da lista (é só texto para copiar/enviar).
- **App instalável (PWA básico)**: `static/manifest.webmanifest` (modo `standalone`, `start_url` `/`), ícones em `static/icones/`
  (gerados por `python scripts/gerar_icones_pwa.py`, com Pillow; versionados) e, no `<head>` de `base.html`, `manifest`,
  `apple-touch-icon`, `theme-color` claro/escuro e as metas do iPhone (`apple-mobile-web-app-capable`, `-title` "LA Locadora" e `-status-bar-style`; 16/11/2026). **Nome do app: "LA Locadora"** (manifest, `<title>`, marca do login/menu/portal, monograma "LA" no favicon e nos ícones; 16/11/2026). **Sem service worker**: a sessão fica na memória do servidor, então o app não
  funciona offline e não há cache de páginas autenticadas. No Android/Chrome aparece "Instalar app"; no iOS, "Adicionar à Tela de Início" (Safari > Compartilhar). No iPhone o app instalado guarda os cookies separados do Safari: entre uma vez de novo dentro dele.
- **Aviso de sessão** (`data-sessao-limite` no `<body>`, `static/js/app.js`): 5 minutos antes do fim do prazo (só para prazos de até 1 dia; com a sessão de 90 dias o aviso fica desligado) abre o diálogo de
  confirmação com "Continuar conectado" (`POST /sessao/renovar`, 204, exige CSRF); passado o prazo, avisa que expirou e leva ao login.
  Requisições do HTMX bem-sucedidas reiniciam a contagem.
- **Indicadores (KPIs)** (macro `kpi` em `componentes/macros.html`; redesign, Fase 2): rótulo pequeno e cinza, valor grande com números tabulares
  (o tamanho acompanha a largura do cartão, `cqi`), ícone em círculo suave (`icone_nome`) e `texto=True` para valores em palavras ou datas. O tom vem de
  `src/domain/painel.py` (`tons_kpis_hoje`, `tons_kpis_dinheiro`, `tom_tempo_parado`): `critico` (vermelho) só para o que pede ação e no máximo um por linha;
  `aviso` (âmbar) para o que preocupa sem pedir ação. Colunas de dinheiro das tabelas usam `num mono` (alinhadas à direita, `tabular-nums`).
- **Listas e fichas** (redesign, Fase 3): nas listas de Veículos, Contratos e Clientes a linha inteira leva à ficha (link esticado, acessível por teclado; o botão
  "Abrir ficha" só aparece no cartão do celular). Em Cobranças, "Pagar" é o botão primário, "Mensagem" o secundário e "Cancelar" usa a variante `discreto` do macro
  `botao`. Selos de status maiores, com ponto colorido e texto. A coluna Km de Veículos some quando todos os veículos listados têm km 0
  (`motos_lista.mostrar_coluna_km`). Campo vazio usa o macro `sem_dado()` (traço apagado; leitor de tela ouve "não informado") e grupos inteiros vazios da ficha do
  cliente viram uma linha só. A barra superior do desktop mostra seção / página atual e o atalho "Novo contrato". Nomes longos na tabela ficam em até duas linhas.
- **Impressão** (`@media print` no fim de `src/web/estilos/app.css`): papel sempre claro (os tokens do tema escuro são refeitos), sem menus, botões,
  filtros, abas, paginação nem diálogos; cartões, KPIs e linhas não quebram entre páginas; selos e barras mantêm a cor.
- **Acessibilidade (auditoria de 23/10/2026)**: contraste AA conferido nos dois temas (texto, selos, botões e menu); contorno de campos com
  3:1 (`--borda-campo`); alvos de toque ≥ 44 px medidos em 13 páginas (390 e 1280 px), sem exceções; `/favicon.ico` deixou de dar 404.
- **Variação mês a mês no Dashboard** ("Recebido no mês" e "Manutenção no mês"; **saiu do Dashboard na Fase 1 do redesenho e volta na Fase 2**, as regras de `painel.py` continuam): compara o acumulado do mês (dia 1 até hoje) com o *mesmo
  intervalo* do mês anterior (`painel.periodo_anterior`: em 31/10 compara 01–30/09). Regras puras em `src/domain/painel.py`
  (`variacao`, `descrever_variacao`); recebido sobe = verde, manutenção sobe = vermelho, e o texto sempre diz "a mais"/"a menos". Sem
  base de comparação (mês anterior zerado) mostra o aviso; os dois zerados, nada. "Em atraso" e ocupação não têm variação: são fotos do
  momento e o sistema não guarda histórico.
- **Feedback de carregamento** (`static/js/app.js`): enquanto há requisição do HTMX, o `<html>` ganha a classe
  `carregando` (barra fina no topo, `#barra-carregamento`) e o alvo da troca recebe `aria-busy="true"` (`#resultado` e
  `#painel-aba` esmaecem após 150 ms). Respeita `prefers-reduced-motion`.
- **Animações e feedback** (redesign, Fase 5; CSS em `src/web/estilos/app.css`, JS em `static/js/app.js`; tudo respeita `prefers-reduced-motion`, que mostra só o
  estado final):
  - **Entrada curta**: blocos, cartões e as primeiras linhas das tabelas entram em 180 a 200 ms, com atraso de no máximo ~175 ms. A grade de KPIs e o
    `<main>` não animam por si (a opacidade de pai e filho se multiplica; era isso que deixava a página desbotada por mais de um segundo).
  - **Números que contam**: o macro `kpi` marca o valor com `data-contar`; o JS sobe de 0 até o número (700 ms) e devolve o texto original no fim. O HTML já traz o valor
    final, então sem JS o número está certo. Só conta quando há um único número no texto. Barras e colunas dos gráficos crescem por CSS.
  - **Toasts**: `#avisos` é uma pilha fixa no canto (sem JS já funciona). O JS acrescenta o botão Fechar e o fechamento automático (sucesso 5 s, informação 6 s,
    atenção 9 s, erro 12 s; pausa com mouse ou foco), no máximo 4 ao mesmo tempo. `role`/`aria-live` vêm do macro `aviso`. Erros HTMX usam `HX-Reswap: beforeend` e as
    respostas fora de banda preservam os toasts na tela, então eles empilham. Dentro de diálogo, o aviso de falha de rede continua inline no diálogo.
  - **Skeleton** (≥ 720 px): enquanto `#resultado`/`#painel-aba` estão com `aria-busy`, as células viram barras cinzas depois de 150 ms (respostas rápidas não piscam).
  - **Estados vazios**: `estado_vazio(titulo, texto, icone_nome=...)` mostra ícone em placa, título, texto e, no bloco `{% call %}`, a ação sugerida (`.vazio-acoes`).
  - **Microinterações**: faixa de foco na linha sob o ponteiro, resposta ao clique em botões, chips e cartões.
  - **Transição entre páginas**: View Transitions entre documentos (`@view-transition`), com o menu lateral e as barras parados; navegador sem suporte navega normalmente.
  - Testes: `tests/test_animacoes_feedback.py` (contratos do CSS/JS/templates). A conferência visual no app logado é manual.
- **Formulários e celular** (redesign, Fase 6; CSS em `src/web/estilos/app.css`, JS em `static/js/app.js`):
  - **Seções**: o macro `secao(titulo, descricao=None)` (`componentes/macros.html`) agrupa campos com o mesmo traço amarelo dos grupos da ficha e uma grade de
    duas colunas (uma no celular); `largo=True` ocupa a linha inteira. Aplicado em veículo (Identificação, Características, Aquisição), cliente, documento, dívida e
    compra parcelada, sem mudar campos, nomes, rotas nem validações. Texto de ajuda em 13 px com o contraste do texto secundário.
  - **Validação imediata**: o `app.js` põe `novalidate` nos formulários com `.formulario` ou `#form-dialogo` e confere o óbvio (obrigatório, e-mail, data, padrão,
    tamanho) ao sair do campo e ao enviar: borda, ícone e mensagem (`aria-invalid` e `aria-describedby`; o campo certo ganha borda e ícone de sucesso), foco no
    primeiro inválido e o envio não sai. O erro some assim que o valor passa na conferência. As regras de verdade continuam no servidor (`src/domain`).
  - **Celular (< 720 px)**: no formulário em tela cheia, uma faixa mostra "Seção X de Y", barra de progresso e um botão por seção (ponto vermelho nas seções com
    erro), com o rodapé fixo; KPIs em duas colunas (uma só abaixo de 360 px; o último ímpar ocupa a linha); botões do cabeçalho/ficha em grade compacta; "Opções"
    do Dashboard pequeno à direita; na aba Dinheiro o título ocupa a linha e o seletor de mês, a largura toda; áreas seguras laterais/topo no formulário e campos em
    16 px (sem zoom do iOS); `overflow-x: clip` na página. Telefone usa `type="tel"`; números e valores já usam `inputmode`.
  - Testes: `tests/test_formularios_celular.py`. A conferência visual no app logado (gaveta de pré-visualização e cartões recolhíveis no celular incluídos) é do dono.
- **Formulário em diálogo** (`macros.form_dialogo`, `rotas/motos_formularios.py`): o diálogo `#dlg-form` abre ao
  chegar o conteúdo; a validação é no servidor, campo a campo (`src/domain/formulario_moto.py`): com erro o mesmo
  formulário volta com a mensagem ao lado do campo; com sucesso vem `HX-Redirect` e um aviso de confirmação
  (uma vez só, guardado na sessão). Operações repetíveis levam `chave_operacao`.

## Estilização do painel

Os tokens (cores, espaçamento, tipografia, modo escuro) e as regras ficam em `src/web/estilos/app.css`; `static/css/app.css` é o arquivo
gerado por `python scripts/construir_css.py` (Tailwind), então edite só o de `src/web/estilos`. Fontes locais em `static/fontes`. Regras
novas devem usar `var(--…)`, nunca cores fixas. O contraste mínimo de 4,5:1 dos tokens nos dois temas é protegido por
`tests/test_contraste_tokens.py`. Os componentes são macros Jinja em `src/web/templates/`.

## Contrato em PDF

A ficha do contrato tem o botão **Contrato em PDF** (rota `/contratos/{id}/pdf`, só para o dono), que gera o contrato com os dados do
cliente, da moto e do contrato (valor e caução por extenso, datas, km inicial). O PDF só é montado no clique.

- **Um template, duas variantes** (`src/domain/contrato_la.py` para o texto e `src/services/contrato_la_pdf.py` para o visual), escolhidas
  pelo `tipo_contrato`. O visual é o do contrato de exemplo de 16/11/2026: faixa preta com a logo (`static/contrato/`), linha vermelha,
  marca d'água, quadros de partes, veículo e preço, resumo de multas, rubricas no rodapé, assinaturas e duas testemunhas.
  - **Promessa de compra:** 13 cláusulas, com propriedade futura, quitação e transferência (cláusula 12) e quadro de preço com entrada,
    parcelas, total e datas da agenda (1ª e última parcela, dia da semana).
  - **Locação simples:** o mesmo documento sem o que é da promessa (12 cláusulas, partes só "LOCADOR" e "LOCATÁRIO", sem direito à
    aquisição) e quadro de preço por período (periodicidade, valor, vencimento, primeiro pagamento, vigência, caução). O texto antigo de
    10 cláusulas deixou de existir (está no histórico do git).
- **Valores fixos:** as multas e prazos ficam em `TERMOS` (um lugar só, para revisão com o advogado) e o **resumo de multas sai de
  `TERMOS`**, então nunca destoa das cláusulas. A fonte é a padrão do PDF (Helvetica), não a Poppins do exemplo.
- **Arquivo baixado:** `Contrato_<Cliente>_<PLACA>.pdf` nos contratos de promessa; `contrato_<PLACA>_<data>.pdf` nos de locação.
- **Dados da empresa (LOCADOR):** variáveis `LOCADOR_NOME`, `LOCADOR_CNPJ` etc. (lista completa em `.env.example`; em produção, no Coolify), fora do git. Sem elas o contrato sai com linhas em branco no lugar do locador. Locador pessoa física (sem `LOCADOR_CNPJ`, usa o representante) ou jurídica (com CNPJ). Cidade e foro vêm de `LOCADOR_CIDADE` e `LOCADOR_FORO` (sem eles, o foro padrão é Crato/CE) e a linha de contato do cabeçalho, de `LOCADOR_CIDADE` e `LOCADOR_TELEFONES`.
- **Contrato com várias motos:** cada moto ganha o seu quadro (a quilometragem inicial é a da principal; as outras saem em branco).
- **Dados do contrato no cadastro (migration `20261117120000_dados_do_contrato.sql`):** cliente com data de nascimento, nacionalidade,
  naturalidade, estado civil, profissão, RG e órgão, CEP e referências; moto com motor e combustível. Todos opcionais: o que faltar sai
  como linha em branco para preencher à mão.
- **Fora do contrato gerado:** a multa e os juros por atraso (cláusula 8.2) e a multa de R$ 10,00 por erro na troca de óleo (5.13.1)
  usam os valores fixos de `TERMOS`, não os da tela Configurações; se a operação mudar de regra, ajuste `TERMOS` ou passe a usar a
  configuração.
- Modelo padrão de contrato: revise o texto final com um advogado antes de usar.

## Cancelamento de cobrança

**Cancelar cobrança (12/11/2026).** Em Cobranças, o botão **Cancelar** (abas Hoje, Atrasadas e Próximos 7 dias) abre um diálogo
que pede o **motivo** (3 a 200 caracteres) e, sem JavaScript, o mesmo formulário abre como página (`rotas/cobrancas_cancelamento.py`).
Regra confirmada com o dono: só cobrança em aberto **e sem nenhum pagamento registrado** pode ser cancelada (`src/domain/cancelamento_cobranca.py`);
com pagamento, parcial que seja, o botão some e o estorno continua sendo feito no banco. Cancelada, a cobrança sai da dívida, das listas e dos avisos de WhatsApp
e não é gerada de novo. A gravação é a RPC `rpc_cancelar_cobranca` (migration `20261112140000_cancelar_cobranca.sql`, que acrescenta
`cobrancas.motivo_cancelamento` e `cancelada_em`; só o dono; roteiro `supabase/verificar_cancelar_cobranca.sql`, só em dev, termina em ROLLBACK).

## Dashboard

O Dashboard (`/`) tem três abas, cada uma com URL própria e sem JavaScript: **Hoje** (`/`), **Dinheiro** (`/?aba=dinheiro`) e **Frota** (`/?aba=frota`).
Cada aba lê só o que mostra, e todas leem das mesmas fontes (`src/services/financeiro.py`): um indicador, uma definição, um lugar.

- **Hoje:** quatro indicadores (A cobrar = vencido + vence hoje; Em atraso, com os contratos e os inadimplentes pelo corte configurável; Frota, com a
  ocupação sobre as motos ativas; Caixa do mês, dizendo quanto é investimento em veículos), a lista **Cobrar agora** (uma linha por contrato, do maior
  atraso para o menor, com **Pagar** e **WhatsApp**, que abre a mensagem de cobrança) e a lista **Atenção** (manutenção, documentos, CNH, WhatsApp e
  pendências de dinheiro, com o que está em perigo na frente). O que vence hoje leva a multa do dia, como na tela de pagamento.
- **Dinheiro:** o mês escolhido em `?mes=aaaa-mm` (só aqui há seletor de mês): receita contra o previsto, despesas, resultado, caixa, investimento,
  parcelas de dívida, retiradas e aportes, receita estimada, dívidas em aberto, os últimos 6 meses, as entradas por conta e as despesas por categoria.
- **Frota:** ocupação (rosca e legenda), motos em manutenção, o gasto com manutenção do mês (o mesmo valor da categoria Manutenção em Dinheiro) e o
  resultado por veículo.
- **Menu Opções** (no cabeçalho): **Modo compacto** (`?compacto=1`: só os indicadores e a atenção) e **Ocultar dados pessoais** (`?ocultar=1`: valores,
  nomes, placas e descrições saem trocados por pontos já no servidor, nem vão no HTML, e os gráficos somem). A aba e os dois modos seguem na navegação.
- Se a leitura de uma aba falhar (migration pendente, banco fora do ar), só aquela aba mostra "indisponível" e o erro vai para o log; na aba Hoje, se
  falhar só o caixa do mês, a cobrança e a frota continuam. **Sem as migrations `20261104120000` e `20261104130000` a aba Dinheiro e o caixa ficam indisponíveis.**
- Os totais vêm de duas RPCs de leitura: `rpc_resumo_financeiro` (migration `20261104120000_resumo_financeiro.sql`, roteiro `supabase/verificar_resumo_financeiro.sql`)
  e `rpc_detalhe_financeiro` (migration `20261104130000_detalhe_financeiro.sql`, roteiro `supabase/verificar_detalhe_financeiro.sql`). Os roteiros terminam em ROLLBACK.
  As regras ficam em `src/domain/financeiro.py` e `src/domain/cobrar_agora.py`.
- O corte entre "em atraso" e "inadimplente" é o parâmetro **Inadimplente a partir de (dias de atraso)** em Configurações (padrão 15, mínimo 1; migration `20261104140000_corte_inadimplencia.sql`, que deve ser aplicada antes de publicar o app novo).
- Caixa = receita - despesas - investimento - parcelas de dívida - retiradas + aportes; a receita não inclui caução nem abatimento.
- Os gráficos são SVG sem script e sem estilo inline (a política de conteúdo só aceita CSS do próprio site); a tabela ao lado traz os mesmos números.
- **Fase 2 (contexto nos cartões, 09/11/2026):** *Em atraso* ganha a barra e a legenda por faixa (1 a 6, 7 a 14, 15 a 30 e 31 dias ou mais, pelo maior atraso do
  contrato; a soma é o total em atraso); *Frota* troca a rosca por uma barra segmentada (na aba Hoje e na aba Frota); *Caixa do mês* ganha a sparkline dos últimos 6 meses;
  em Dinheiro, *Receita* mostra um bullet contra o previsto, com a marca do esperado até hoje (as cobranças que já venceram), e os quatro cartões mostram a variação contra o
  mês anterior **só em mês fechado** (mês inteiro contra mês inteiro, colorida pelo resultado e sempre dita em texto); no mês corrente aparece o mês anterior, sem variação.
  Tudo é SVG sem script e sem estilo inline, com texto alternativo; com "ocultar dados" nenhum desenho aparece. Regras em `domain/cobrar_agora.py` e `domain/financeiro.py`.
- **Fase 3 (o que faltava, 09/11/2026):** na aba Hoje, **Próximos 7 dias** (entra = cobranças abertas de amanhã em diante, sem caução; sai = parcelas de dívida a vencer, inclusive as de hoje;
  saldo previsto). Na aba Frota, **Receita por moto** (receita do mês ÷ motos ativas), **Tempo parado no mês** (dias de moto na oficina ÷ motos ativas × dias do mês até hoje; alerta acima de 5%)
  e **Motos paradas** (em manutenção desde a ordem aberta mais antiga, ou disponíveis desde o último contrato encerrado). Regras em `domain/frota_parada.py` e `domain/cobrar_agora.py`.
- **Saiu do Dashboard na Fase 1:** o cálculo antigo (`services/dashboard`), que dava números diferentes dos do financeiro (receita, manutenção, atraso). Com ele saiu a
  variação mês a mês dos cartões, que voltou na Fase 2 com a base certa (só mês fechado).

## Dívidas (telas)

Menu **Dívidas** (só o dono): `/dividas` lista cada dívida com saldo, próxima parcela e situação; `/dividas/{id}` mostra parcelas e pagamentos;
`/dividas/parcelas/{id}/pagar` registra o pagamento de uma parcela (total ou parcial); `/dividas/nova` cadastra uma compra parcelada com
conferência do total, do saldo e do calendário antes de gravar. Usam as RPCs e views das migrations 6 e 7 (não há migration nova). O contrato com
várias motos já tem tela desde 03/11/2026 (etapa Moto do novo contrato, lista e ficha). `/dividas/nova-divida` cadastra moto fiado, financiamento, fornecedor, rastreador e empréstimo (inserção direta em `dividas`, sem RPC, porque mexe em uma tabela só) e `/dividas/{id}/pagar` registra pagamento de dívida sem parcelas (insere em `pagamentos_divida`). A ficha também tem **Editar** (na compra parcelada só credor, moto, descrição e observações, porque o total e as parcelas seguem o calendário gerado), **Confirmar saldo** (o saldo informado pelo responsável, com data, vale sobre o calculado; dá para remover a confirmação) e **Apagar** (página de confirmação; parcelas e pagamentos saem junto, em cascata, e não há como desfazer). **Editar** também troca o tipo da dívida entre moto fiado, financiamento, fornecedor, rastreador e empréstimo (a compra parcelada não troca). Cada parcela tem **Editar** (vencimento, que pode ficar vazio, e o valor, só se ainda não houve pagamento) e cada pagamento tem **Corrigir** (data, com opção de data aproximada, valor até o que falta, conta e observações); os gatilhos do banco reavaliam sozinhos se a parcela está paga.

## Contrato com várias motos e promessa de compra (telas)

**Telas (novo contrato):** o assistente de `/contratos/novo` aceita até 4 motos vinculadas na etapa Moto (a principal fica com a parcela e
a receita), o tipo "Promessa de compra" na etapa Condições (entrada, número de parcelas, parcelas já pagas, dia e primeira cobrança) e mostra
o total e a prévia da agenda na confirmação. A lista de contratos exibe "+N motos" e "Promessa de compra"; a ficha mostra as motos do contrato
e o total, a entrada e as parcelas pagas/restantes.

## Vistoria por moto (contrato com várias motos)

**Parte 1, banco, regras e serviços.** Migration `20261105130000_vistoria_por_moto.sql`: a entrega e a devolução passam a ser **uma por moto do contrato** (`unique (contrato_id, moto_id, tipo)`); `rpc_registrar_vistoria` aceita a moto principal ou uma vinculada e um gatilho recusa moto de fora do contrato; `rpc_criar_contrato_com_vistoria` e `rpc_encerrar_contrato_com_vistoria` recebem `p_vistorias_vinculadas` (opcional, as chamadas antigas valem) e gravam o km de cada moto, então o `km_atual` e os alertas de manutenção das vinculadas acompanham. Regras puras em `src/domain/vistorias_por_moto.py`; os serviços de contratos aceitam `vistorias_vinculadas` e `exigir_todas`. As leituras de vistoria por contrato devolvem por padrão a da moto principal. Roteiro de teste: `supabase/verificar_vistoria_por_moto.sql` (só em dev, termina em ROLLBACK).

**Parte 2, telas.** Com a migration aplicada:
- **Novo contrato (etapa Confirmar)** e **encerramento**: um bloco de vistoria por moto vinculada (campos `vinc<n>_...`, regras em `src/domain/formulario_vistoria_por_moto.py`), **obrigatório**: o contrato só é criado ou encerrado se todas as vistorias forem válidas (km não menor que o da moto). O texto digitado volta em caso de erro. As fotos continuam só na moto principal; as das outras entram depois, em Vistorias.
- **Vistorias**: a lista mostra a placa da moto da própria vistoria; a comparação ganha um grupo de entrega e devolução por moto vinculada; **Registrar vistoria** lista cada par contrato-moto que ainda não tem as duas vistorias (o campo `contrato` vale o id do contrato ou `contrato:moto`) e registra na moto escolhida. É por aqui que os contratos já carregados (ex.: Plano Conquista do Yangry) ganham a **entrega retroativa** da moto vinculada.
- **Ficha do contrato, aba Vistorias**: um grupo por moto do contrato.
- Contrato de uma moto só fica exatamente como era. Desenho: seção 19 de `Arquivos/Projeto_Locação.md`.

## Arquivamento de veículos vendidos e ex-locatários

Nada é apagado: o dono **arquiva** pela ficha, e só quando não há pendências (contrato ativo, manutenção aberta ou cobrança em aberto, inclusive o débito de contratos encerrados). O veículo pede o motivo («Vendido», com a data, ou «Outro motivo») e fica inativo. Arquivados saem de «Todos» nas listas e ficam no filtro «Arquivados»; dá para desarquivar (o veículo continua inativo até ser reativado). Contrato novo não aceita veículo nem cliente arquivado. Banco: migration `20261119120000_arquivamento.sql` (RPCs `rpc_arquivar_*` e `rpc_desarquivar_*`); regra em `src/domain/arquivamento.py`.

Atualização de uma instalação existente: aplicar a migration; rodar `supabase/verificar_arquivamento.sql` no **dev** (desfaz tudo no fim); `supabase/consultar_candidatos_arquivamento.sql` (somente leitura) lista quem já pode ser arquivado. No SQL Editor do Supabase só o resultado da **última** consulta aparece: rode as duas consultas do arquivo uma de cada vez. Detalhes na seção 23, item 10, do plano.

## Convenções dos relatórios

Receita usa a data de pagamento e exclui caução. Custo de manutenção considera
serviços concluídos, pela data de entrada. Documentos entram na data de regularização.
Essas datas representam o controle disponível no sistema; não há uma tabela separada
de pagamentos a fornecedores. O custo/km representa manutenção dividida pela distância
registrada. Os cálculos financeiros usam `Decimal`; as células do Excel são numéricas.

## Portal do locatário

O locatário entra com **e-mail + senha** no padrão `nome.sobrenome@locadora.com` (homônimos: `nome.sobrenome2@...`; ele pode
digitar só `nome.sobrenome`; o domínio é só um rótulo, nenhum e-mail é enviado; o dono continua entrando com o e-mail dele) e vê só a tela
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
(e-mail `nome.sobrenome@locadora.com` e **senha padrão** = primeiro nome minúsculo e sem acento + **6 últimos dígitos do
CPF**, por exemplo `joao224725`; decisão do dono em 16/11/2026, pois o sistema não guarda a data de nascimento e o locatário
esquece senhas) e o vincula ao cliente. O app mostra o e-mail e a senha ao criar: entregue-os ao locatário. Ele pode trocar a
senha no portal ("Alterar minha senha"), mas não é obrigado. "Gerar nova senha" volta a senha para a padrão e "Remover acesso" exclui o login.
**Padronizar os acessos existentes.** Configurações > «Acessos dos locatários» > «Padronizar acessos de todos os locatários»
(só o dono, com confirmação): a Edge Function troca o e-mail e a senha de todos os acessos que já existem para o padrão (a ordem do cadastro
decide quem fica sem sufixo). Não devolve senhas e não avisa ninguém por WhatsApp. Depois de publicar a função e aplicar a migration
`20261116120000_vincular_locatario_por_email.sql` (a função e a migration andam juntas: aplique as duas antes de criar acessos novos).
**Esqueci minha senha (12/11/2026).** O e-mail do portal é fictício, então não há link de redefinição: na tela de login, «Peça uma senha nova»
(`/login/esqueci-senha`, `rotas/esqueci_senha.py`) pede só o **CPF** e registra um **pedido** para o dono. A resposta ao locatário é sempre a mesma para
qualquer CPF válido (ninguém descobre quem é cliente), cada pedido conta no limite por IP (20 em 15 min) e o CSRF usa o cookie do login. O dono vê o pedido
em **duas** telas: o alerta «Nova senha do portal pedida» no Dashboard (aba Hoje, lista Atenção) e o aviso no topo da aba Portal da ficha do cliente, com **Descartar
pedido** (para quando não foi o locatário que pediu). **Gerar nova senha** (ou remover o acesso) fecha o pedido; o dono continua entregando a senha pessoalmente.
Migration `20261112150000_pedidos_senha_portal.sql` (tabela `pedidos_senha_portal`, no máximo um pedido aberto por cliente, só o dono lê; RPC
`rpc_portal_pedir_redefinicao`, a única chamada **sem login**, papel `anon`); roteiro `supabase/verificar_pedidos_senha_portal.sql` (só em dev, termina em ROLLBACK).
Sem a migration, a tela de pedido mostra um erro genérico e o Dashboard e a ficha seguem normais. O bloqueio de tentativas do Supabase
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
Configurações > "Multa por troca de óleo fora do intervalo". O valor padrão é R$ 12,50;
valor 0,00 desativa a cobrança da multa. Se a foto não confirmar o km, o dono cancela a
multa em Cobranças (botão **Cancelar**, veja «Cancelamento de cobrança»).

### Comprovante de documento enviado pelo locatário

O locatário pode mandar pelo portal a foto ou o PDF do comprovante de um documento da moto (IPVA, licenciamento, seguro...). O envio **não regulariza** nada: fica aguardando o dono, que aceita ou recusa.
- Migration `20261112120000_comprovantes_documentos.sql`: tabela `documento_comprovantes` (aguardando, aceito ou recusado com motivo; no máximo um aguardando por documento; só o dono lê), política do Storage (o locatário só **envia** para `portal/<cliente_id>/` do bucket `documentos`, sem listar nem ler) e as RPCs `rpc_portal_documentos` (documentos pendentes das motos dos contratos ativos, principal e vinculada), `rpc_portal_enviar_comprovante` (confere documento, pasta e arquivo) e `rpc_aceitar_comprovante_documento` (regulariza o documento com o arquivo do envio e fecha o envio, numa transação). Roteiro: `supabase/verificar_comprovantes_documentos.sql` (só em dev, termina em ROLLBACK).
- **Portal:** seção «Documentos da moto» com a situação de cada documento, o último comprovante e, quando não há um aguardando, o formulário (PDF, JPG ou PNG de até 10 MB; foto perde GPS e dados do aparelho; observação opcional de até 200 caracteres). Recusado, o locatário vê o motivo e pode enviar outro.
- **Dono:** em Documentos, o selo «Comprovante a conferir» e o botão **Conferir comprovante** abrem a página de conferência (quem enviou, quando, observação, arquivo por URL assinada de 5 minutos, histórico) com **Aceitar e regularizar** (data não futura; pode seguir para o cadastro do ano seguinte) e **Recusar** (motivo de 3 a 200 letras). O Dashboard avisa «Comprovante a conferir».
- **WhatsApp:** migration `20261112130000_whatsapp_comprovante_enviado.sql` (roteiro `supabase/verificar_whatsapp_comprovante.sql`): enquanto há comprovante aguardando, o aviso daquele documento **pausa**; recusado, volta. Com `PORTAL_URL` definido, o texto do aviso de documento pede o comprovante pelo portal (sem ela, no grupo).
- Se a migration ainda não foi aplicada, o portal, a lista de Documentos e o Dashboard seguem funcionando, só sem esta parte (o erro vai para o log).

### Arquivos órfãos do portal

O locatário envia as fotos da troca de óleo e o comprovante de documento ao Storage **antes** de registrar a operação. Se o registro falha (hodômetro
menor que o anterior, troca repetida, documento já regularizado), o arquivo fica no Storage sem nenhuma linha que o referencie: um **arquivo órfão**.
Em **Configurações > Arquivos órfãos do portal** o dono clica em **Procurar arquivos órfãos**, confere a lista (tipo, caminho, tamanho e data) e só então
**Apaga**, com confirmação. Regras (`src/domain/arquivos_orfaos.py`, `src/services/arquivos_orfaos.py`):

- só entram arquivos **do portal**: o bucket `trocas_oleo` e a pasta `portal/` do bucket `documentos`; vistorias e os arquivos que o próprio dono enviou nunca são tocados;
- só entram arquivos com **mais de 24 horas** e que **nenhuma linha referencia** (foto do painel ou nota fiscal de troca; comprovante de envio, inclusive recusado; arquivo de documento da moto);
- a lista vem da RPC `rpc_listar_arquivos_orfaos` (só o dono; migration `20261112160000_arquivos_orfaos_portal.sql`, roteiro `supabase/verificar_arquivos_orfaos_portal.sql`, só em dev, termina em ROLLBACK), com no máximo 1000 por vez;
- quem apaga é o app, pela **API do Storage** (que remove o arquivo de verdade, não só a linha), em lotes de 100 e com a sessão do dono. A lista é **recalculada na hora de apagar**:
  nada que vem do navegador define o que é removido. Uma falha em um lote não impede os outros: a mensagem diz quantos foram apagados e quantos não puderam ser.

## Envio automático por WhatsApp

Desenho e decisões: seção 20 de [Projeto_Locação.md](Projeto_Locação.md). O envio nasce **desligado**.

### Banco

Migration `20261106120000_whatsapp_base.sql` (compatível com a versão anterior do app):
- `clientes` ganha `nao_enviar_whatsapp`, `motivo_bloqueio_whatsapp` e `bloqueio_whatsapp_em` (o bloqueio exige motivo e data; só o dono liga, na ficha do cliente).
- `mensagens_whatsapp` é a fila e o histórico; `mensagens_whatsapp_itens` lista os assuntos de cada mensagem e a chave única (tipo, referência, data) impede o mesmo aviso de sair duas vezes no mesmo dia. Só administradores enxergam as duas tabelas.
- `servico_mensagens (user_id)` é o usuário de serviço (o robô do script agendado). Ele não lê nenhuma tabela: só chama `rpc_whatsapp_enfileirar` (pula duplicadas e clientes bloqueados; sem número válido grava `ignorada`), `rpc_whatsapp_reservar` (entrega as pendentes e as reserva por 10 min; cancela as de cliente bloqueado depois) e `rpc_whatsapp_registrar_resultado` (enviada, ignorada ou falha, com até 3 tentativas e espera de 30 min x tentativa). A `service_role` não é usada.

Para criar o usuário de serviço: crie o usuário em Authentication > Users (com "Auto Confirm User") e rode no SQL Editor `insert into servico_mensagens (user_id) select id from auth.users where email = 'robo@exemplo.com';`. Para remover o acesso: `delete from servico_mensagens where user_id = (select id from auth.users where email = 'robo@exemplo.com');`. Roteiro de teste: `supabase/verificar_whatsapp_base.sql` (só em dev, termina em ROLLBACK). Nunca coloque senhas ou e-mails reais no repositório.

### Regras e textos

Regras puras em `src/domain` (sem banco, sem rede), com testes em `tests/`:
- `feriados.py`: feriados nacionais por ano (fixos, Carnaval, Sexta-feira Santa, Corpus Christi).
- `janela_envio.py`: três disparos por dia, às 7:30, 11:30 e 15:00 (America/Sao_Paulo; cada um aberto por 1 hora), segunda a sábado, sem feriado nacional; leva o que cair fora para o próximo disparo (era 8h às 19h até 17/11/2026).
- `numero_whatsapp.py`: transforma o que está em `clientes.whatsapp` em `55` + DDD + número; fixo ou número estranho vira `None` (aviso `ignorada`).
- `avisos_whatsapp.py`: quais avisos são devidos no dia de envio (lembrete de véspera e de vencimento, atraso, inadimplência, recibo, CNH, documentos, óleo, portal). Atraso, CNH vencida, documento vencido e óleo vencida seguem a escala 1º, 3º e 7º dia e depois a cada 3 dias, com teto de 10 avisos por assunto (`ConfigAvisos.max_repeticoes`). Contrato diário só recebe o lembrete do dia.
- `textos_whatsapp.py`: os textos (fixos no código) e o agrupamento dos assuntos de um cliente em uma mensagem, em tom leve (26/11/2026), com uma saudação («Aqui é da LA Locadora»). **Cobranças e recibos** abrem a mensagem: recibos primeiro, valores um por linha (ou uma linha por cobrança e o «Total destas parcelas/cobranças», que soma só as listadas: as com aviso devido no dia), pedido do comprovante no grupo e «se já pagou, pode desconsiderar»; todas entram, sem teto. Atraso e inadimplência da mesma cobrança aparecem uma vez só (os dois assuntos são marcados como enviados); a inadimplência é mais séria, sem ameaça. **CNH, documentos, óleo e portal** vêm depois, um parágrafo cada; o que passar de 5 assuntos vai em outra mensagem (a rodada seguinte já a monta). `montar_payload` devolve o formato de `rpc_whatsapp_enfileirar`.

### Leitura, Evolution e rodada agendada

O envio é **desligado por padrão** (chave geral em `configuracoes.whatsapp_ativo`, ligada em Configurações; ver «Telas do dono»).
- Migration `20261106130000_whatsapp_leitura.sql`: controles em `configuracoes` (`whatsapp_ativo` desligado, `whatsapp_modo_teste` ligado, `whatsapp_numero_teste`, `whatsapp_max_repeticoes`) e `rpc_whatsapp_dados`, a leitura única que alimenta as regras (documentos e troca de óleo vão ao locatário do contrato ativo, inclusive de moto vinculada). Roteiro: `supabase/verificar_whatsapp_leitura.sql` (só em dev, termina em ROLLBACK).
- `src/services/evolution.py`: cliente HTTP da Evolution (estado da instância, número tem WhatsApp, envio de texto; corpos da v1 e da v2). `src/services/whatsapp.py`: uma rodada = ler, aplicar as regras, enfileirar (a qualquer hora) e enviar dentro da janela, com pausa aleatória de 20 a 60 s entre mensagens. Cada rodada pega no máximo 5 mensagens, com tempo limite de 20 s por chamada, e para antes de passar dos 10 minutos de reserva (se a Evolution estiver lenta, o resto volta para a fila). Limite de requisições (429) e tempo esgotado (408) da Evolution não derrubam a mensagem: ela volta para a fila e a rodada para. No **modo teste** tudo vai só ao número de teste.
- `python -m src.enviar_mensagens_whatsapp` é o comando da Tarefa Agendada do Coolify; as variáveis e o passo a passo estão em `Arquivos/Deploy_VPS.md`, seção 8.1.
- Conferido contra um Postgres do Supabase em Docker: a saída real de `rpc_whatsapp_dados` alimenta as regras, a mensagem gerada entra em `rpc_whatsapp_enfileirar` e uma segunda rodada não duplica nada.

### Telas do dono

Migration `20261106140000_whatsapp_painel.sql` (compatível com a versão anterior do app): `configuracoes` guarda quando a rodada rodou pela última vez, o estado da instância e o resumo (`rpc_whatsapp_registrar_rodada`, só usuário de serviço e administradores). Roteiro: `supabase/verificar_whatsapp_painel.sql` (só em dev, termina em ROLLBACK). A rodada agora confere a instância a cada execução e grava esse estado.
- **Configurações > Envio automático por WhatsApp**: liga/desliga, modo teste ou envio aos clientes (este exige confirmação), número de teste e máximo de avisos por assunto, com o estado da instância e a hora da última rodada. É aqui que o envio se liga; nasce desligado.
- **Mensagens** (menu Operação): lista das mensagens recentes com os filtros Com problema, Aguardando, Enviadas e Todas; mostra situação, motivo e tentativas, e abre o texto. **Reenviar** devolve à fila o que falhou; **Cancelar** vale para pendente ou falhada.
- **Ficha do cliente, aba WhatsApp**: para onde as mensagens vão, histórico do cliente e o bloqueio. Só o dono para o envio de um cliente (com motivo; fica a data); o cliente não consegue pedir isso pelo WhatsApp.
- **Dashboard, Precisa de atenção**: envio automático parado (sem rodada há mais de 1h30), WhatsApp desconectado, Evolution fora do ar, modo teste ligado e clientes cuja mensagem mais recente não foi entregue. Sem o envio ligado, nenhum desses alertas aparece.
- As tabelas `mensagens_whatsapp*` não entram no backup manual (é histórico derivado, com dados pessoais).

### Envio ao grupo do locatário

Migration `20261117130000_whatsapp_grupo.sql` (roteiro `supabase/verificar_whatsapp_grupo.sql`, só em dev, termina em ROLLBACK). Cada locatário tem um
grupo de WhatsApp (ele, o dono, o financeiro e o número do envio automático). As mensagens automáticas vão **para o grupo**, não para `clientes.whatsapp`:
- `clientes.whatsapp_grupo_id` (formato `...@g.us`, único por cliente). `mensagens_whatsapp.numero` continua sendo o destino e passa a aceitar o ID do grupo.
- Desde 26/11/2026 vão ao grupo **todos os avisos** (`TIPOS_NO_GRUPO` em `src/domain/grupo_whatsapp.py`): cobranças, recibos, CNH, documentos do veículo,
  troca de óleo e portal (de 17 a 26/11/2026 iam só cobranças e recibos).
- Cliente sem grupo: a mensagem fica `ignorada`, com o motivo «Cliente sem grupo de WhatsApp cadastrado.». O envio ao grupo não confere se o número tem WhatsApp.
- Cada rodada, com a instância conectada, grava a lista de grupos da Evolution (`whatsapp_grupos`, `GET /group/fetchAllGroups`). Na ficha do cliente (aba WhatsApp)
  o dono escolhe o grupo na lista ou cola o ID. Como a lista pode ter dezenas de grupos (a instância é compartilhada com o negócio de celulares), há uma **caixa de busca** acima de uma **lista aberta** (8 linhas) de grupos (`data-filtrar-opcoes` em `static/js/app.js`). Cada palavra digitada vale um ponto (sem diferenciar maiúsculas nem acentos; "hyf1f47" acha "HYF-1F47"), e os grupos com mais pontos vêm primeiro: "Gabriel Santos HYF1F47" acha o grupo "Gabriel - [HYF-1F47]" mesmo sem o sobrenome. O grupo atual do cliente fica sempre no topo (salvar sem querer não o remove) e, se só um grupo tem todas as palavras, ele é selecionado. O site não fala com a Evolution (a chave dela fica só na tarefa agendada).
- Em modo teste tudo continua indo só para o número de teste, com o aviso «iria para o grupo do cliente».

### Aviso de senha do portal alterada

Migration `20261109120000_portal_eventos_senha.sql` (compatível com a versão anterior do app): a troca de senha acontece no Supabase Auth e não deixava registro, então o aviso não tinha de onde nascer. Agora `portal_eventos` guarda cada troca feita pelo locatário e `rpc_whatsapp_dados` a entrega ao envio (o evento mais recente de cada cliente, dos últimos dias).
- O **locatário** troca a própria senha no portal: o app chama `rpc_portal_registrar_troca_senha()` (no máximo um evento a cada 10 minutos por cliente; quem chama é identificado por `auth.uid()`).
- O **dono** gerar uma senha nova na aba Portal da ficha do cliente **não** gera aviso: ele entrega a senha pessoalmente (decisão do dono em 09/11/2026). A RPC `rpc_portal_registrar_redefinicao_senha`, criada na migration, fica sem uso.
- O registro é o melhor possível: se falhar, a senha já trocada continua valendo e o erro só vai para o log. Senha recusada pelo Supabase não registra nada.
- O texto ao locatário diz que a senha foi alterada e pede que avise o dono se não foi ele (a nova senha nunca vai na mensagem). Acesso novo continua sendo avisado a partir da criação do login. Só o dono lê `portal_eventos`. Roteiro: `supabase/verificar_portal_eventos_senha.sql` (só em dev, termina em ROLLBACK).

## Backup manual

- **Backup completo (17/11/2026).** O backup manual passou de 15 para 29 tabelas (32 desde 25/11/2026, com a caixa do histórico dos chats): além das originais, traz `despesas`, `multas_transito`, `dividas`, `dividas_vencimentos`, `pagamentos_divida`, `movimentos_socio`, `contas`, `fornecedores`, `contrato_motos`, `documento_comprovantes`, `importacoes_lote`, `whatsapp_grupos`, `pedidos_senha_portal` e `portal_eventos`. Ficam de fora só `administradores`, `servico_mensagens` (nem o dono as lê) e a fila `mensagens_whatsapp*`. Antes, conferir multas, despesas e dívidas contra planilha ou chats não era possível. O ZIP agora tem mais dados pessoais e financeiros: guarde-o em local privado.

## Conector do claude.ai

`POST /mcp` é um servidor MCP remoto (JSON-RPC sobre HTTP) com OAuth 2.1: registro dinâmico de cliente (`/oauth/register`), PKCE S256 e callback
fixo do claude.ai (`src/web/rotas/conector.py`, regras puras em `src/domain/conector_oauth.py` e `conector_mcp.py`). O dono entra com o login do
app e autoriza o Claude numa tela de consentimento (só donos; o CSP libera o destino do Claude apenas nessa tela). Os tokens são **sem estado**
(Fernet com `CONECTOR_CHAVE`; trocar a chave revoga tudo; sem a chave o conector fica desligado e todas as rotas dão 404). Variáveis e como
conectar: [README](../README.md#conector-do-claudeai).

O chat **grava direto** o que está limpo e, na dúvida, **não grava** e devolve o motivo; ele nunca edita nem apaga. Tetos: pagamento até
**R$ 10.000,00** (e só com cobrança identificada, valor igual ao saldo, sem duplicidade nem data futura); despesa até **R$ 5.000,00** (exige o
veículo ou a descrição dele). Tudo o que o chat grava fica em `pendencias_lancamento` (histórico e auditoria), e o dono pode desfazer um
lançamento automático em até **7 dias** (`rpc_pendencia_desfazer`). As regras completas estão em `src/domain/pendencias.py`; a evolução, no
[histórico](Historico_Desenvolvimento.md).

- **Ferramentas do chat.** O claude.ai usa 8 ferramentas (`src/domain/conector_mcp.py`):
  `consultar_cobrancas_abertas`, `buscar_veiculos` e `listar_ultimos_lancamentos` (só leitura) e `registrar_pagamento`, `registrar_despesa`,
  `cadastrar_cliente` e `cadastrar_veiculo` (gravam, nunca editam nem apagam), além do `ping`. Cada ferramenta valida os argumentos
  (`src/domain/pendencias.py`), chama a RPC do banco (`src/services/conector.py`, `src/repositories/conector.py`) e devolve ao Claude um texto:
  **«Gravado: ...»** ou **«NÃO GRAVADO (motivo): ... Pergunte ao usuário o que falta e tente de novo.»**, que o Claude resolve na conversa. O app
  entra no Supabase como o **usuário de serviço do conector** (`SERVICO_CONECTOR_EMAIL` e `SERVICO_CONECTOR_SENHA`; ele só executa as RPCs `rpc_conector_*`
  e fica registrado em `servico_conector`); sem essas variáveis só o `ping` funciona. Erros inesperados nunca vão em detalhe para o chat. As gravações
  descartam o cache de leituras das telas. Criar o usuário: Supabase > Authentication > Users (com «Auto Confirm User»), depois
  `insert into servico_conector (user_id) select id from auth.users where email = 'o-email-do-usuario';`.
- **Histórico dos chats pelo conector (25/11/2026; seção 24.9 do plano).** O Claude dos chats «Locadora - Acompanhamento Financeiro» e «Contratos
  Locadora» entrega o histórico em **lotes de até 50 registros** para uma **caixa de rascunho**, sem gravar nada no financeiro. Ferramentas:
  `entregar_lote_historico`, `resumo_do_historico` e `listar_historico_a_conferir` (`src/domain/historico_chat.py`, `src/services/conector.py`).
  Cada registro leva tipo, data, dados e o **trecho do chat** que o originou; cada lote informa o **período que cobre**, e o resumo mostra os
  **buracos** entre os lotes (para saber se o chat foi lido inteiro). O banco compara cada registro com o sistema (pagamento, despesa, multa,
  cliente, veículo e contrato) e marca `ja_existe`, `nova` ou `diverge`; o mesmo registro entregue duas vezes não duplica. Migration
  `20261125120000_historico_chats.sql` (roteiro `supabase/verificar_historico_chats.sql`, só em dev, termina em ROLLBACK): tabelas
  `historico_chat_lotes` e `historico_chat_registros` (só o dono lê; ninguém grava direto; o backup as inclui, junto com `pendencias_lancamento`) e as
  RPCs `rpc_conector_entregar_lote_historico`, `rpc_conector_resumo_historico`, `rpc_conector_historico_a_conferir` e `rpc_historico_descartar_lote`
  (só dono, não apaga lote com registro aplicado). **Aplicar** o que for novo ou divergente continua sendo uma carga SQL aprovada pelo dono (sessão de
  sincronização, dev antes de produção, ver `Arquivos/dados/Sincronizacao_Chats.md`).
- **Histórico dos chats, versão 2 (25/11/2026).** Depois da primeira entrega real dos dois chats: a lista `listar_historico_a_conferir` ganhou **página e total** (cortava em 50
  de 55 sem avisar) e filtro por tipo; a comparação de **multa** olha também o valor atualizado e reconhece o valor com **20% de desconto** (as 8 «divergências» eram isso); `dados.data_estimada`
  abre uma janela de datas (±7 dias; ±30 no contrato); `dados.finalidade` (semana, caução, multa...) faz o pagamento composto casar com o tipo da cobrança; `inferido`, `faltando` e
  `ocorrencia` (segundo fato igual no mesmo dia) são aceitos, e a entrega avisa quando um registro «igual» já entregue veio com **outro trecho** do chat. Migration
  `20261125130000_historico_v2.sql` (o roteiro `verificar_historico_chats.sql` cobre as duas). **A planilha de conferência é gerada pelo app** (Configurações > «Histórico dos chats»; só o
  dono; `src/services/historico_chat.py`): Resumo, Conferência (id, motivo, trecho e coluna Decisão com lista) e Lotes. O histórico anterior ao que o chat enxerga vem da **exportação oficial**
  do claude.ai: `python scripts/extrair_chat_exportado.py EXPORTACAO.zip PASTA_FORA_DO_REPOSITORIO --titulo "..."` (ver `Arquivos/dados/Sincronizacao_Chats.md`, seções 12 e 13).

## Testes de navegador (UI/UX)

`e2e/` contém a suíte Playwright do `Arquivos/interface/Plano_Melhorias_UI_UX.md` (Etapa 0), separada
de `tests/`: mede overflow, alvos de toque, diálogos e erros de console em cinco larguras,
dois temas e Chromium/Firefox/WebKit, contra o projeto Supabase de **desenvolvimento**.
`pytest` roda só `tests/`; `pytest e2e` roda a suíte de navegador. Instalação, variáveis de
ambiente e opções em `e2e/README.md`; inventário em `Arquivos/interface/Inventario_UI_UX.md`;
achados curados em `Arquivos/interface/Achados_UI_UX.md`; massa de dados extremos em
`supabase/seed_e2e.sql`.

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
10. Gere e baixe o backup. Confira as 32 tabelas e as contagens em `manifesto.json`.
    O ZIP não inclui os binários de fotos/comprovantes nem usuários do Auth. Evite
    alterações durante a geração, pois as leituras não formam um snapshot transacional.
11. Confira os formulários e tabelas em celular. Saia da conta e verifique que os dados
    deixam de aparecer. A sessão dura 90 dias sem uso: para testar a expiração, use os testes automatizados (`tests/web/test_autenticacao_web.py`).
