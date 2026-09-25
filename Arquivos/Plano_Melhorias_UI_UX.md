# Plano de Melhorias de UI/UX

> Plano incremental para evolução do frontend do Controle de Locação.
> Complementa `Design_UI.md` e `Projeto_Locação.md`; não substitui as decisões
> visuais ou as regras de negócio desses documentos.

## 1. Objetivo

Melhorar a usabilidade operacional, a acessibilidade e a consistência do sistema
sem descaracterizar o conceito visual de **painel de instrumentos** já adotado.

As prioridades são:

1. tornar as ações confortáveis e compreensíveis em desktop e celular;
2. permitir navegação adequada por teclado e tecnologias assistivas;
3. reduzir diferenças de comportamento entre páginas;
4. melhorar filtros, formulários e feedback de operações;
5. diminuir a fragilidade causada por seletores dependentes do DOM do Streamlit.

## 2. Princípios da evolução

- Preservar a paleta, tipografia, linguagem visual e componentes definidos em
  `Design_UI.md`.
- Priorizar os fluxos mais frequentes: consultar pendências, localizar registros,
  abrir fichas, criar contratos e registrar pagamentos.
- Nenhuma informação deve depender apenas de cor, ícone ou tooltip.
- Manter a interface simples: uma ação primária evidente por contexto.
- Tratar celular como ambiente operacional, não apenas como versão reduzida do
  desktop.
- Implementar e validar uma fase por vez.

## 3. Diagnóstico resumido

### Pontos fortes

- Design system centralizado em tokens CSS.
- Hierarquia visual consistente e identidade adequada ao domínio de locação de
  motos.
- Modo claro e modo escuro próprios.
- Estados acompanhados por texto, sem depender exclusivamente de cor.
- Estados vazios, cartões, KPIs e formatação brasileira reutilizáveis.
- Adaptação mobile existente para diversas tabelas e fichas.
- Fluxo de novo contrato dividido em etapas.

### Oportunidades principais

- Ações por ícone possuem áreas clicáveis de 32 a 34 px.
- Símbolos como `→`, `✓`, `✎` e `›` dependem de tooltip para explicar a ação.
- Algumas listas simulam tabelas com `st.columns`, sem semântica de tabela ou de
  cartão para tecnologias assistivas.
- Cabeçalhos, mensagens de sucesso e estados vazios não seguem um único padrão em
  todas as páginas.
- A navegação lateral possui dez destinos no mesmo nível.
- Filtros em colunas e conjuntos grandes de abas podem ficar comprimidos no
  celular.
- Campos monetários, percentuais e numéricos são frequentemente campos de texto
  comuns.
- O modo escuro do `st.dataframe` depende de inversão visual por CSS.
- Parte relevante do CSS depende de `data-testid`, `nth-child` e da estrutura
  interna do Streamlit.

## 4. Fase 1 — Acessibilidade e ações operacionais

**Prioridade:** crítica

### Trabalho previsto

1. Aumentar para pelo menos 44 × 44 px a área clicável das ações por linha.
2. Manter o desenho do ícone compacto, ampliando apenas a área de interação.
3. Substituir símbolos Unicode por ícones consistentes do mesmo conjunto visual.
4. Garantir nome acessível e explicação textual para todas as ações.
5. No celular, exibir texto junto ao ícone quando a intenção não for óbvia:
   `Pagar`, `Editar`, `Abrir`, `Concluir` e `Regularizar`.
6. Separar ações semanticamente diferentes. Um botão não deve significar
   simultaneamente “concluir ou cancelar”.
7. Verificar ordem de tabulação, foco visível e ativação por teclado.
8. Verificar contraste dos estados nos modos claro e escuro.

### Áreas afetadas

- Dashboard: registrar pagamento.
- Motos: atualizar quilometragem e abrir ficha.
- Clientes e contratos: abrir ficha.
- Cobranças: copiar mensagem e registrar pagamento.
- Manutenção: concluir, cancelar e editar item.
- Documentos: editar, ver comprovante e regularizar.
- Vistorias: abrir comparação.

### Critérios de aceite

- Toda ação interativa possui alvo de pelo menos 44 × 44 px.
- Toda ação possui nome compreensível sem depender de hover.
- É possível percorrer e acionar os controles usando apenas teclado.
- O foco permanece visível nos dois temas.
- A mesma ação usa o mesmo ícone, texto e tratamento visual em todas as páginas.
- Nenhuma operação ambígua permanece representada por um único botão.

## 5. Fase 2 — Componentes e estrutura consistentes

**Prioridade:** alta

### Trabalho previsto

1. Adotar `cabecalho_pagina` em todas as páginas.
2. Evoluir o componente para receber:
   - título;
   - descrição ou resumo contextual;
   - ação primária;
   - sobretítulo ou breadcrumb opcional;
   - indicador contextual opcional.
3. Posicionar a ação principal à direita no desktop e em largura total no celular.
4. Padronizar estados vazios com título, explicação e ação de recuperação quando
   aplicável.
5. Padronizar confirmações, alertas e erros.
6. Substituir listas construídas como “tabelas visuais” por:
   - tabela HTML semântica, quando o conteúdo for somente leitura; ou
   - cartões de registro, quando houver ações por item.
7. Preservar a densidade adequada ao uso operacional, sem introduzir cartões
   excessivamente altos.

### Critérios de aceite

- Todas as páginas possuem o mesmo alinhamento e espaçamento de cabeçalho.
- Cada página apresenta no máximo uma ação primária no cabeçalho.
- Listas somente leitura usam cabeçalhos e células semanticamente relacionados.
- Listas interativas apresentam título, metadados e grupo de ações identificável.
- Estados vazios informam o motivo e, quando possível, o próximo passo.

## 6. Fase 3 — Navegação e localização

**Prioridade:** alta

### Trabalho previsto

1. Agrupar a navegação lateral sem alterar as rotas:
   - **Operação:** Dashboard, Contratos, Cobranças;
   - **Cadastros:** Motos, Clientes;
   - **Frota:** Manutenção, Documentos, Vistorias;
   - **Gestão:** Relatórios;
   - **Sistema:** Configurações.
2. Avaliar uma ação rápida persistente para `Novo contrato`.
3. Manter claramente visível a página ativa.
4. Nas fichas, apresentar retorno contextual: `Voltar para motos`, `Voltar para
   clientes` ou `Voltar para contratos`.
5. Preservar busca, filtros e página da lista quando o usuário abrir uma ficha e
   voltar.
6. Manter o estado da aba ativa durante atualizações que não representem mudança
   de contexto.

### Critérios de aceite

- Um usuário identifica o grupo funcional de cada página sem precisar percorrer
  toda a barra lateral.
- Voltar de uma ficha restaura a posição e os filtros anteriores.
- O item ativo e a localização atual são perceptíveis nos dois temas.
- A ação rápida não compete visualmente com alertas ou ações destrutivas.

## 7. Fase 4 — Busca, filtros, abas e paginação

**Prioridade:** alta

### Trabalho previsto

1. Substituir filtros em colunas rígidas por chips com quebra de linha no desktop.
2. No celular, usar um seletor compacto ou um painel `Filtros`.
3. Mostrar filtros ativos e oferecer `Limpar filtros`.
4. Exibir quantidade de resultados após busca e filtragem.
5. Aplicar atraso curto à busca ou executá-la explicitamente para evitar
   atualizações excessivas a cada tecla.
6. Para conjuntos grandes de abas, usar rolagem horizontal sinalizada ou seletor
   compacto no celular.
7. Padronizar paginação com `Anterior`, informação da página e `Próxima`.
8. Quando apropriado, permitir escolher a quantidade de registros por página.

### Critérios de aceite

- Nenhum filtro tem texto truncado ou alvo de toque reduzido entre 320 e 1920 px.
- Filtros selecionados permanecem identificáveis sem depender apenas da cor.
- A limpeza de filtros exige uma única ação.
- A busca informa claramente quando não há resultados.
- A paginação mantém o usuário na mesma visão e não perde filtros.

## 8. Fase 5 — Formulários, validação e prevenção de erros

**Prioridade:** alta

### Trabalho previsto

1. Aplicar comportamento adequado ao tipo do dado:
   - moeda com prefixo `R$` e formatação brasileira;
   - percentuais com sufixo `%`;
   - dias, quilômetros e quantidades com entrada numérica;
   - CPF, telefone e placa com máscara ou normalização previsível.
2. Validar campos o mais próximo possível da entrada incorreta.
3. Preservar todos os valores quando houver erro.
4. Exibir texto de ajuda apenas quando ele orientar uma decisão real.
5. Identificar campos obrigatórios antes do envio.
6. Desabilitar a ação de confirmação enquanto os requisitos mínimos não forem
   atendidos.
7. Em ações destrutivas, explicar o impacto e solicitar confirmação explícita.
8. No assistente de contrato, permitir revisar dados anteriores sem perder o
   progresso.

### Critérios de aceite

- Valores monetários são exibidos e editados no padrão `R$ 1.234,56`.
- Mensagens de validação identificam o campo e como corrigir o problema.
- Nenhum formulário é apagado após erro de validação ou falha do serviço.
- Operações destrutivas informam quais registros serão afetados.
- O botão principal comunica claramente quando está indisponível e por quê.

## 9. Fase 6 — Feedback, carregamento e recuperação

**Prioridade:** média

### Trabalho previsto

1. Substituir a confirmação genérica `Alterações salvas.` por mensagens específicas,
   por exemplo:
   - `Moto cadastrada.`;
   - `Pagamento de R$ 450,00 registrado.`;
   - `Contrato encerrado.`
2. Usar toast para confirmações simples e alerta persistente para situações que
   exigem atenção.
3. Durante operações, trocar o rótulo do botão por um estado como `Salvando…` e
   impedir envios duplicados.
4. Usar spinner ou skeleton apenas quando a espera for perceptível.
5. Oferecer nova tentativa quando uma consulta falhar.
6. Diferenciar erro de validação, indisponibilidade do serviço, sessão expirada e
   falta de permissão.

### Critérios de aceite

- Toda operação iniciada informa progresso, sucesso ou falha.
- Cliques repetidos não geram registros duplicados.
- Mensagens de sucesso descrevem o que foi alterado.
- Erros recuperáveis apresentam uma ação clara de nova tentativa.

## 10. Fase 7 — Robustez visual e manutenção do frontend

**Prioridade:** média

### Trabalho previsto

1. Remover gradualmente a inversão global usada no `st.dataframe` em modo escuro.
2. Preferir tabelas HTML do design system ou configuração de tema nativa.
3. Reduzir seletores baseados em `nth-child` e na estrutura interna do Streamlit.
4. Encapsular padrões complexos em componentes com chaves e classes estáveis.
5. Eliminar estilos inline novos; migrar estilos existentes para classes quando o
   componente for alterado.
6. Avaliar o empacotamento local das fontes para evitar flash de tipografia,
   indisponibilidade de rede e dependência externa.
7. Documentar componentes e variantes no `Design_UI.md` após estabilização.

### Critérios de aceite

- Tabelas continuam legíveis nos dois temas sem filtros CSS de inversão.
- Mudanças na ordem de colunas não quebram o layout mobile.
- Componentes alterados não adicionam novos valores visuais fora dos tokens.
- A interface mantém aparência utilizável quando as fontes externas não carregam.

## 11. Fase 8 — Validação e testes de experiência

**Prioridade:** necessária para encerrar o plano

### Matriz mínima

Validar as telas principais nas larguras:

- 320 px;
- 390 px;
- 768 px;
- 1024 px;
- 1440 px.

Executar em modo claro e escuro, com dados normais, textos longos, listas vazias e
listas extensas.

### Fluxos mínimos

1. Entrar no sistema.
2. Localizar e abrir uma moto.
3. Localizar e abrir um cliente.
4. Criar um contrato completo.
5. Registrar um pagamento.
6. Registrar e concluir uma manutenção.
7. Cadastrar e regularizar um documento.
8. Registrar e comparar vistorias.
9. Alterar configurações.
10. Gerar e baixar backup.

### Verificações

- Navegação completa por teclado.
- Foco visível e ordem lógica.
- Nomes acessíveis para botões e campos.
- Contraste mínimo de 4,5:1 para texto comum.
- Zoom de navegador em 200% sem perda de funcionalidade.
- Ausência de rolagem horizontal na página; tabelas podem possuir rolagem interna
  quando realmente necessário.
- Mensagens compreensíveis sem conhecimento técnico.
- Ausência de erros relevantes no console e nos logs do Streamlit.

### Critérios de aceite

- Todos os fluxos mínimos são concluídos em desktop e celular.
- Não existem bloqueios críticos encontrados por uma auditoria automatizada de
  acessibilidade.
- Não há regressão visual nas páginas autenticadas e na tela de login.
- O resultado da validação é registrado com capturas das larguras principais.

## 12. Ordem sugerida de implementação

| Ordem | Entrega | Resultado esperado |
|---:|---|---|
| 1 | Ações e acessibilidade | Uso confortável por toque e teclado |
| 2 | Cabeçalhos, listas e feedback | Consistência entre páginas |
| 3 | Navegação e preservação de contexto | Menos esforço para circular no sistema |
| 4 | Filtros, abas e paginação | Melhor uso em telas estreitas |
| 5 | Formulários e validação | Menos erros de entrada e retrabalho |
| 6 | Carregamento e recuperação | Operações mais previsíveis |
| 7 | Robustez do CSS e modo escuro | Menor custo de manutenção |
| 8 | Testes visuais e de acessibilidade | Evidência de qualidade e ausência de regressão |

## 13. Indicadores de sucesso

- Todas as ações por linha atingem 44 × 44 px.
- 100% dos controles possuem nome acessível.
- 100% das páginas usam o cabeçalho padronizado.
- Busca e filtros são preservados ao retornar de uma ficha.
- Nenhuma tabela depende de inversão global no modo escuro.
- Todos os fluxos mínimos funcionam entre 320 e 1440 px.
- Nenhum problema crítico ou grave na auditoria de acessibilidade.
- Redução de seletores dependentes de `nth-child` e do DOM interno do Streamlit.

## 14. Fora do escopo

- Alteração das regras de negócio.
- Mudança da identidade visual ou da paleta principal.
- Reescrita do sistema em outro framework frontend.
- Inclusão de funcionalidades comerciais não previstas no projeto.
- Mudança da arquitetura página → serviço → repositório.

## 15. Definição de pronto por fase

Uma fase só deve ser considerada concluída quando:

1. os critérios de aceite da fase forem atendidos;
2. os testes existentes passarem;
3. o comportamento for validado nos modos claro e escuro;
4. o comportamento mobile for verificado em 390 px;
5. não houver regressão nos fluxos diretamente relacionados;
6. a documentação visual for atualizada quando surgir ou mudar um padrão;
7. as mudanças forem registradas em commit descritivo, conforme as regras do
   projeto.
