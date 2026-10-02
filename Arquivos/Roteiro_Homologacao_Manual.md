# Roteiro de homologação manual (Etapa 9)

O que a automação **não** consegue provar: gravação real nos dez fluxos, aparelho físico, leitor de tela e a
sensação de uso. Faça este roteiro no projeto Supabase de **desenvolvimento** (dados fictícios), nunca na produção.
Marque cada item e anote o aparelho, o navegador e a data no fim.

## Preparação

1. `.streamlit/secrets.toml` apontando para o projeto de desenvolvimento (guarde antes o de produção fora do repositório).
2. `streamlit run app.py` e, para abrir no celular na mesma rede, `streamlit run app.py --server.address 0.0.0.0`
   (o celular acessa `http://<IP do computador>:8501`; libere a porta no firewall só durante o teste).
3. Dados: `supabase/seed.sql` + `supabase/seed_exemplos.sql`; para listas extensas, `supabase/seed_e2e.sql`.

## Aparelhos mínimos

| Aparelho | Navegador | Obrigatório |
|---|---|---|
| Android (qualquer, 360–412 px) | Chrome | sim |
| iPhone ou iPad | Safari | se houver |
| Desktop 1440×900 | Chrome ou Edge | sim |
| Desktop | Firefox | recomendado |

## Fluxos (concluir **gravando**, no desktop e no celular)

Para cada fluxo, confira: nenhum botão fora da tela, mensagem de sucesso que diz o que mudou, nenhuma rolagem
horizontal da página, e que o clique duplo não grava duas vezes.

- [ ] **1. Entrar e navegar** — login; abrir as 10 páginas pelo menu (no celular, pelo botão do menu); sair.
- [ ] **2. Dashboard e alertas** — cartões Hoje e Alertas; abrir um item de alerta.
- [ ] **3. Buscar, filtrar, paginar e abrir** — em Motos e Clientes: buscar, filtrar por situação, trocar de página,
  abrir a ficha e voltar (a lista mantém busca, filtro e página).
- [ ] **4. Contrato completo** — novo contrato pelo assistente (moto, cliente, condições, vistoria de entrega),
  revisar a prévia da agenda, criar; abrir a ficha do contrato.
- [ ] **5. Pagamento** — em Cobranças, `Pagar` numa cobrança: pagamento parcial e depois a quitação; o saldo e a
  situação mudam; o toast mostra o valor.
- [ ] **6. Manutenção** — registrar manutenção, concluir, conferir o plano da moto.
- [ ] **7. Documento** — cadastrar documento com vencimento; anexar comprovante; regularizar.
- [ ] **8. Vistorias** — registrar uma vistoria de entrega e uma de devolução com fotos; abrir; comparar as duas.
- [ ] **9. Relatórios** — trocar o período, percorrer as abas, exportar (Excel/CSV) e abrir o arquivo baixado.
- [ ] **10. Configurações e backup** — alterar um parâmetro e salvar; gerar e baixar o backup.

## Teclado e leitor de tela (desktop)

- [ ] Percorrer cada página só com Tab/Shift+Tab/Enter/Espaço/Esc: o foco aparece sempre e a ordem é lógica; Esc
  fecha diálogos e o foco volta ao botão que os abriu.
- [ ] Zoom do navegador em 200% e depois 400% (equivale a 320 px): nada some, nada rola na horizontal.
- [ ] Leitor de tela (NVDA com Firefox/Chrome, ou VoiceOver): ouvir o menu, um botão de ação por ícone, um campo com
  erro e um toast de sucesso.

## Celular

- [ ] Retrato e paisagem em todos os fluxos acima; teclado virtual aberto não cobre o botão de confirmar.
- [ ] Alvos de toque confortáveis (sem acertar o vizinho) nas listas e nos diálogos.
- [ ] Conexão ruim (modo avião por 5 s e volta): a mensagem de falha é compreensível e há `Tentar novamente`.

## Registro

| Data | Aparelho / navegador | Fluxos 1–10 | Teclado | Zoom | Problemas encontrados |
|---|---|---|---|---|---|
| | | | | | |
