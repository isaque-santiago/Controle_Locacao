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

- [ ] **1. Entrar e navegar:** login; abrir as 10 páginas pelo menu (no celular, pela barra inferior e pelo botão «Mais»); sair.
- [ ] **2. Dashboard e alertas:** cartões e alertas; abrir um item de alerta e voltar.
- [ ] **3. Buscar, filtrar, paginar e abrir:** em Motos e Clientes, buscar, filtrar pelos chips, trocar de página, abrir a
  ficha e voltar (a lista mantém busca, filtro e página).
- [ ] **4. Contrato completo:** novo contrato pelo assistente (cliente, moto, condições, vistoria de entrega); revisar a
  prévia da agenda; criar; abrir a ficha; encerrar com vistoria de devolução.
- [ ] **5. Pagamento:** em Cobranças, «Pagar» numa cobrança: pagamento parcial e depois a quitação; saldo e situação mudam e o
  aviso mostra o valor.
- [ ] **6. Manutenção:** registrar uma manutenção, concluí-la e conferir o plano da moto.
- [ ] **7. Documento:** cadastrar documento com vencimento e comprovante (foto ou PDF); regularizar.
- [ ] **8. Vistorias:** registrar vistoria de entrega e de devolução **com fotos**; abrir; comparar as duas.
- [ ] **9. Relatórios:** trocar o período, percorrer as quatro abas, exportar CSV e Excel e **abrir os arquivos** (no Excel).
- [ ] **10. Configurações e backup:** alterar um parâmetro e salvar (depois restaurar o valor); gerar e baixar o backup.

## 4. Teclado e zoom (desktop)

- [ ] Percorrer cada página só com Tab, Shift+Tab, Enter, Espaço e Esc: o foco aparece sempre e a ordem é lógica; Esc fecha
  diálogos e o foco volta ao botão que os abriu.
- [ ] Zoom do navegador em 200% e depois 400% (equivale a 320 px): nada some e nada rola na horizontal.

## 5. Celular (Android, Chrome)

- [ ] Retrato e paisagem em todos os fluxos; o teclado virtual aberto não cobre o botão de confirmar.
- [ ] Alvos de toque confortáveis (sem acertar o vizinho) nas listas, nos chips e nos diálogos.
- [ ] Conexão ruim (modo avião por 5 s e volta): a mensagem de falha é compreensível e dá para tentar de novo.
- [ ] **Fotos de câmera de verdade** (tirar na hora, sem usar a galeria) em: vistoria (entrega e devolução), comprovante de
  documento e portal do locatário. Anote para cada uma: se o envio terminou, quanto tempo levou, se a foto aparece de pé
  (orientação) e se o tamanho passou do limite de 10 MB (a mensagem de erro deve explicar).
- [ ] **Portal do locatário** (CPF e senha de locatário): ver o contrato e a situação do óleo; reportar uma troca de óleo com a
  foto do painel e a da nota fiscal; trocar a senha.

## 6. Privacidade das fotos (a IA confere)

As fotos são guardadas **sem localização (GPS) e sem os dados do aparelho** (marca, modelo, número de série); ficam a data e a
orientação. Depois dos envios de câmera do item 5, abra a foto enviada em cada tela (galeria da vistoria, «Comprovante» do documento), salve-a
na pasta Downloads do computador e avise a IA com o nome dos arquivos: ela confere os metadados deles (sem GPS, sem aparelho).

## 7. Registro

| Data | Aparelho / navegador | Fluxos 1–10 | Teclado e zoom | Celular e fotos | Problemas encontrados |
|---|---|---|---|---|---|
| | | | | | |
