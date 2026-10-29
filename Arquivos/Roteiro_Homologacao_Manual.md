# Roteiro de homologação manual (Fase 4, parte E)

O que a automação **não** prova: uso real dos 10 fluxos, aparelho físico, câmera de verdade e a sensação de uso. Faça tudo no
projeto Supabase de **desenvolvimento** (dados fictícios), nunca no de produção. Marque cada item e preencha o registro no fim.

Combinado com o proprietário (13/10/2026): só Android (Xiaomi POCO M6 Pro, Chrome); **sem** leitor de tela nesta rodada (fica
como melhoria futura); EXIF das fotos já tratado no servidor (ver E6).

## 1. Preparação

1. **Banco de dev novo:** cole o `recriar_banco_dev.sql` (entregue pela IA, fora do repositório) no SQL Editor do projeto de
   **desenvolvimento**. Ele recusa rodar em outro banco (confere o UUID do usuário de teste na `is_dono()`).
2. **Referência da regressão visual** (antes de qualquer fluxo, com o banco recém-criado):

   ```powershell
   .\.venv\Scripts\python.exe -m pytest e2e -k visual --perfil chromium-desktop --perfil chromium-movel --capturas
   ```

   A primeira execução grava `e2e/referencia/web/...`; uma segunda compara.
3. **Subir o app:** no computador, `.venv\Scripts\python.exe executar_web.py` (desktop) ou, para o celular na mesma rede Wi-Fi,
   `.venv\Scripts\python.exe executar_web.py --rede` (mostra o endereço, algo como `http://192.168.0.16:8000`). No Windows,
   libere a porta 8000 no firewall **só durante o teste** e feche-a depois.
4. **Dados:** banco criado a partir de `supabase/seed.sql` + `supabase/seed_exemplos.sql`. O acesso de locatário se cria pelo app,
   na ficha do cliente, aba Portal (anote o CPF e a senha gerada; use-os no celular).

## 2. Aparelhos

| Aparelho | Navegador | Obrigatório |
|---|---|---|
| Desktop 1440×900 | Chrome ou Edge | sim |
| Desktop | Firefox | recomendado |
| Xiaomi POCO M6 Pro (Android) | Chrome | sim |

## 3. Fluxos (concluir **gravando**, no desktop e no celular)

Em cada fluxo confira: nenhum botão fora da tela, mensagem de sucesso que diz o que mudou, nenhuma rolagem horizontal da
página e que o clique duplo não grava duas vezes (a IA já testa o duplo clique do pagamento por automação).

- [x] **1. Entrar e navegar** (desktop, 13/10/2026, relato do proprietário; sem evidência de console): login; abrir as 10 páginas pelo menu (no celular, pela barra inferior e pelo botão «Mais»); sair.
- [x] **2. Dashboard e alertas** (desktop, 13/10/2026, relato do proprietário): cartões e alertas; abrir um item de alerta e voltar.
- [x] **3. Buscar, filtrar, paginar e abrir** (desktop, 13/10/2026, relato do proprietário): em Motos e Clientes, buscar, filtrar pelos chips, trocar de página, abrir a
  ficha e voltar (a lista mantém busca, filtro e página).
- [x] **4. Contrato completo** (desktop, 13/10/2026, relato do proprietário): novo contrato pelo assistente (cliente, moto, condições, vistoria de entrega); revisar a
  prévia da agenda; criar; abrir a ficha; encerrar com vistoria de devolução.
- [x] **5. Pagamento** (desktop, 13/10/2026, relato do proprietário): em Cobranças, «Pagar» numa cobrança: pagamento parcial e depois a quitação; saldo e situação mudam e o
  aviso mostra o valor.
- [x] **6. Manutenção** (desktop, 13/10/2026, relato do proprietário): registrar uma manutenção, concluí-la e conferir o plano da moto.
- [x] **7. Documento** (desktop, 13/10/2026, relato do proprietário): cadastrar documento com vencimento e comprovante (foto ou PDF); regularizar.
- [x] **8. Vistorias** (desktop, 13/10/2026, relato do proprietário): registrar vistoria de entrega e de devolução **com fotos**; abrir; comparar as duas.
- [x] **9. Relatórios** (desktop, 13/10/2026, relato do proprietário; arquivos abertos no Excel): trocar o período, percorrer as quatro abas, exportar CSV e Excel e **abrir os arquivos** (no Excel).
- [x] **10. Configurações e backup** (desktop, 13/10/2026, relato do proprietário): alterar um parâmetro e salvar (depois restaurar o valor); gerar e baixar o backup.

## 4. Teclado e zoom (desktop)

- [x] (13/10/2026, só por automação, aceita pelo proprietário: `e2e/test_homologacao.py`, 14 aprovados em modo estrito; não prova a visibilidade do foco a olho nem o retorno do foco após Esc) Percorrer cada página só com Tab, Shift+Tab, Enter, Espaço e Esc: o foco aparece sempre e a ordem é lógica; Esc fecha
  diálogos e o foco volta ao botão que os abriu.
- [x] (13/10/2026, só por automação: zoom 200% e reflow a 320 px, sem achados) Zoom do navegador em 200% e depois 400% (equivale a 320 px): nada some e nada rola na horizontal.

## 5. Celular (Android, Chrome)

- [x] (13/10/2026, POCO M6 Pro, relato do proprietário) Retrato e paisagem em todos os fluxos; o teclado virtual aberto não cobre o botão de confirmar.
- [x] (13/10/2026, POCO M6 Pro, relato do proprietário) Alvos de toque confortáveis (sem acertar o vizinho) nas listas, nos chips e nos diálogos.
- [x] (13/10/2026, POCO M6 Pro, relato do proprietário) Conexão ruim (modo avião por 5 s e volta): a mensagem de falha é compreensível e dá para tentar de novo.
- [x] (13/10/2026, POCO M6 Pro, relato do proprietário) **Fotos de câmera de verdade** (tirar na hora, sem usar a galeria) em: vistoria (entrega e devolução), comprovante de
  documento e portal do locatário. Anote para cada uma: se o envio terminou, quanto tempo levou, se a foto aparece de pé
  (orientação) e se o tamanho passou do limite de 10 MB (a mensagem de erro deve explicar).
- [x] (13/10/2026, POCO M6 Pro, relato do proprietário) **Portal do locatário** (CPF e senha de locatário): ver o contrato e a situação do óleo; reportar uma troca de óleo com a
  foto do painel e a da nota fiscal; trocar a senha.

## 6. Privacidade das fotos (a IA confere)

As fotos são guardadas **sem localização (GPS) e sem os dados do aparelho** (marca, modelo, número de série); ficam a data e a
orientação. Depois dos envios de câmera do item 5, abra a foto enviada em cada tela (galeria da vistoria, «Comprovante» do documento), salve-a
na pasta Downloads do computador e avise a IA com o nome dos arquivos: ela confere os metadados deles (sem GPS, sem aparelho).

## 7. Registro

| Data | Aparelho / navegador | Fluxos 1–10 | Teclado e zoom | Celular e fotos | Problemas encontrados |
|---|---|---|---|---|---|
| 13/10/2026 | Desktop (aba embutida/Chrome) e POCO M6 Pro (Chrome, Android) | 1–10 feitos no desktop e no celular (relato do proprietário); clique duplo no pagamento por automação | Teclado e zoom 200%/400% só por automação (aceito) | Fotos de câmera e Portal feitos; metadados conferidos em 3 fotos guardadas pelo app (13/10/2026): sem GPS, sem aparelho, sem XMP; só data e fuso (e orientação 0). Achado: blocos Xiaomi (APP3/APP4) sobreviviam à limpeza; corrigido | Nenhum relatado. Celular: bloqueio do firewall do Windows (regras de bloqueio do python.exe) resolvido fora do app |

### Aceite do Supabase Storage em produção (26/10/2026, `https://lamotos.duckdns.org`)

Feito com moto, cliente e contrato de teste (TESTE / ABC-1D23), no Chrome em que o proprietário fez o login; a automação enviou os
arquivos pelos formulários do app. Arquivos de teste: JPEG com GPS, marca, modelo e série falsos, e um PDF.

| Verificação | Resultado |
|---|---|
| Comprovante PDF e JPEG no bucket `documentos` (Documentos > Novo) | Cadastrados; link «Comprovante» responde 303 para URL assinada do Supabase |
| Foto de vistoria no bucket `vistorias` (Vistorias > Registrar, devolução) | Registrada; a foto carrega na página sob a CSP (640×480) |
| URL assinada baixa o arquivo | 200, `application/pdf` e `image/jpeg`; o PDF é idêntico (SHA-256) ao original |
| Acesso sem a assinatura | `/object/public/...` e o caminho sem token: 400 nos dois buckets |
| Expiração (5 min) | Após 316–319 s: 400 `InvalidJWT` (`exp` vencido) |
| Rota do comprovante sem login | 303 para `/login?proximo=...` |
| Privacidade das fotos guardadas | JPEG baixado dos dois buckets sem GPS, marca, modelo ou série |

Não coberto nesta primeira rodada: bucket `trocas_oleo` (feito logo abaixo) e envio pelo celular.

### Aceite do bucket `trocas_oleo` pelo portal do locatário (26/10/2026)

Moto, cliente e contrato de teste novos, acesso criado pela aba Portal da ficha do cliente (Edge Function `criar-locatario` em produção) e
login do locatário por CPF em um segundo Chrome, com perfil separado do dono. Troca de óleo enviada com km 500 (abaixo do intervalo, sem multa) e
duas fotos JPEG com GPS, marca, modelo e série falsos.

| Verificação | Resultado |
|---|---|
| Envio pelo portal («Enviar troca de óleo») | «Troca de óleo registrada»; hodômetro, última troca e próxima troca atualizados |
| Fotos do painel e da nota abertas pelo dono (ficha do cliente, aba Portal) | 303 para URL assinada; download 200, `image/jpeg` |
| Acesso sem a assinatura | `/object/public/...` e o caminho sem token: 400 |
| Expiração (5 min) | Após 319–321 s: 400 `InvalidJWT` (`exp` vencido) |
| Privacidade das fotos guardadas | Sem GPS, marca, modelo ou série |
| Isolamento do locatário (sessão dele) | 403 em `/motos`, `/contratos`, `/configuracoes`, no comprovante de documento e na foto da troca pela rota do dono; `/` redireciona para `/portal` |

Não coberto: leitura direta do Storage pelo locatário com a chave anônima (o app não a expõe) e envio pelo celular.

### Roteiro de aceite no app publicado (26/10/2026, `https://lamotos.duckdns.org`)

Fluxos 1 a 10 do roteiro conduzidos por automação no Chrome em que o proprietário fez o login, com registros de teste (moto TST-1E55, cliente
TESTE ROTEIRO, contrato 12/10/2026, semanal, R$ 100,00, caução R$ 200,00). Os envios de arquivo do Storage estão na seção anterior.

| Fluxo | Resultado |
|---|---|
| 1. Sem login | As 11 páginas do menu e a ficha de moto redirecionam para `/login`; `/saude` 200; `/componentes` 404 |
| 2. Cadastro | Placa inválida e CPF inválido recusados com mensagem; placa e CPF duplicados recusados; plano automático (9 itens) criado; CPF mascarado na lista |
| 3. Km | 500 km registrado; leitura 300 km exige confirmação e não reduz o km atual (continua 500) |
| 4. Contrato | Prévia (caução + 5 parcelas) igual às cobranças geradas; moto sai das disponíveis (aparece como «Alugada») |
| 5. Pagamentos | Em dia (R$ 100 + multa R$ 15), parcial (R$ 40; saldo R$ 60 em aberto), restante com R$ 64 de encargos (15 + 7×7) e atraso de 14 dias com R$ 113 (15 + 7×14); principal maior que o saldo recusado; caução sem encargos |
| 6. Manutenção | Alerta de óleo vencida a 1.100 km; manutenção aberta (moto em manutenção, custo R$ 75,00) e concluída; só o item de óleo reiniciou (próxima troca em 2.150 km); moto voltou a «Alugada» |
| 7. Documento | IPVA vencido aparece no Dashboard; regularizado com comprovante PDF; cadastro do próximo ano aberto com vencimento em branco e criado |
| 8. Encerramento | Devolução com avaria e danos de R$ 120: «Devolver R$ 80,00 de caução», 2 cobranças futuras canceladas, parcelas pagas preservadas, moto «Disponível», km rodados 660; comparação entrega × devolução marca o farol como alterado |
| 9. Dashboard e relatórios | Recebido R$ 612 = R$ 300 de principal + R$ 192 de encargos + R$ 120 de danos retidos (a caução de R$ 200 não é receita); manutenção R$ 75; resultado R$ 487. CSV (BOM, `;`, vírgula decimal) e Excel das 4 abas abrem com acentos corretos |
| 10. Backup | ZIP com as 15 tabelas, `manifesto.json` (contagens iguais às linhas dos CSV) e `LEIA-ME.txt`; resposta `no-store` |

Não feito neste ambiente: alterar parâmetros em Configurações (afetaria os encargos reais), cobrança do excedente quando o dano passa da caução
(só a prévia, «devolver R$ 0,00»; a regra é coberta por `tests/test_caucao.py`), Firefox e celular (com o proprietário).

Achados (corrigidos no código depois da rodada, ainda sem deploy; o terceiro vem do Lighthouse de 26/10/2026):

- Console: no diálogo «Encerrar contrato», cada alteração dos campos que recalculam a prévia registra `error: The selector "find button[type=submit]" on
  hx-disabled-elt returned no matches!`. O atributo do formulário é herdado pelos campos que disparam a prévia; a prévia funciona. Corrigir com
  `hx-disabled-elt="unset"` nesses campos.
- Mensagem do fluxo 3: «Quilometragem registrada: 300 km» não diz que o km atual da moto segue em 500 km.
- Estado vazio de Cobranças: o título era um `<h3>` logo depois do `<h1>` (axe `heading-order`, acessibilidade 98). O macro `estado_vazio` agora usa `<h2>`.
- Correções: `hx-disabled-elt="unset"` nos campos da prévia do encerramento e do pagamento (reproduzido e confirmado com o htmx 2.0.11 do projeto); a mensagem do km passa a dizer «Leitura de 300 km registrada no histórico... O km atual continua 500 km».

### Rodada no celular e no app publicado (27/10/2026, POCO M6 Pro, Chrome, `https://lamotos.duckdns.org`)

Feita pelo proprietário, com o app já com as dependências novas. Resultado de cada item do checklist:

| Item | Resultado |
|---|---|
| Acesso e HTTPS | OK |
| Instalar como app (PWA) | OK; abre sem a barra do navegador |
| Fotos enviadas pelo celular (vistoria e portal) | Envio funcionou. A foto da **entrega** não tinha como ser anexada (ver achados) |
| Teclado virtual aberto | Não cobriu nenhum botão |
| Conexão ruim (modo avião por 5 s) | OK |
| Aviso de sessão («Continuar conectado») | OK |
| Retrato e paisagem | OK |
| Privacidade das fotos guardadas (2 JPEG baixadas do site, conferidas pela IA) | Sem GPS, marca, modelo, `Software` nem blocos da Xiaomi/MediaTek; só Orientação e data. Tamanho de 3,16 MB contra 3,19 MB do original (só os blocos saíram; os pixels não mudam) |

Foto original de 11,9 MB (6944×9248, 64 MP) passa do limite de 10 MB e não foi guardada; o envio de uma foto menor funcionou.

Achados e o que foi feito (branch `feat/fotos-entrega-e-camera`):

- **Foto da entrega sem caminho para anexar.** O assistente de contrato não tinha campo de foto, e Vistorias > Registrar só oferece os tipos
  pendentes (depois do assistente sobra só a devolução). A mensagem de «Adicionar fotos» já existia, mas nenhuma rota a usava. Agora: campo de
  fotos na etapa 4 do assistente; ação **Adicionar fotos** em cada vistoria da comparação (`/vistorias/{id}/fotos`, diálogo ou página); a mensagem
  do contrato criado diz onde adicionar, e a de falha parcial manda abrir Vistorias.
- **Câmera.** No portal do locatário os campos da foto do painel e da nota usam `accept="image/*"`; o `capture="environment"` da primeira
  versão forçava só a câmera e tirava a opção de enviar da galeria, então foi removido (o seletor do celular oferece as duas). Nas vistorias
  (campo múltiplo, onde `capture` não vale) o `accept` passou a `image/*`. No POCO isso abriu só a galeria (campo múltiplo usa o seletor de fotos
  do sistema, sem câmera); por isso cada campo múltiplo (registrar vistoria, fotos da entrega e Adicionar fotos) ganhou um segundo campo `fotos`
  «Tirar foto agora» com `capture="environment"`, que sempre abre a câmera. **A conferir no aparelho depois do deploy.**
- **Alerta «Mude sua senha»** do Gerenciador de senhas do Google ao entrar como dono: a senha apareceu em lista pública de vazamentos.
  Não é falha do app; a senha do dono foi apontada para troca (Supabase, Authentication > Users).
- Fica como decisão: fotos de câmera de 64 MP podem passar de 10 MB; avaliar redução no navegador antes do envio.

Conferência no POCO depois dos PRs #122 e #123 (27/10/2026, Chrome): portal do locatário (câmera ou galeria nos dois campos), Registrar vistoria,
fotos da entrega no assistente de contrato e Adicionar fotos (galeria múltipla + «Tirar foto agora», com fotos dos dois campos chegando juntas):
**todos ok.** Pendentes: a revisão no Firefox desktop, a troca da senha do dono e o Dependabot alerts (precisa do dono do repositório).

### Revisão no Firefox desktop (29/10/2026, Firefox 154)

Feita pelo proprietário no app publicado, com gravação de tela. Navegação e visual, fluxos que gravam, teclado e zoom, e console: **ok**.
Downloads: ok. **Impressão (Ctrl+P) nas listas: problema** — o PDF saía só com o título e a contagem, sem a tabela (Motos, Clientes e as demais
listas com busca). Causas (reproduzidas com o Firefox 154 via Selenium, imprimindo o HTML real das páginas):

1. A folha de impressão escondia `form[role="search"]`, mas esse formulário embrulha a barra de filtros **e** o `#resultado` com a lista. Agora só a
   `.barra-filtros` some.
2. No Firefox, a tabela dentro de `.tabela-caixa` (`container-type: inline-size` com rolagem) não é impressa. Na folha o contêiner passa a
   `overflow: visible; container-type: normal`.

Depois da correção o PDF do Firefox traz as linhas das listas (conferido pelo texto do PDF em Motos e Clientes). **A conferir no aparelho depois do deploy:** o
visual da folha no Firefox e no Chrome.

