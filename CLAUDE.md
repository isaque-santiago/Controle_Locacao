# Regras de trabalho

- Interface, nomes de tabelas/colunas, mensagens e comentários em português (pt-BR).
- Siga o Arquivos/Projeto_Locação.md fase por fase. Não avance de fase sem cumprir os critérios de aceite.
- Ao alterar um arquivo, entregue o arquivo COMPLETO (não trechos soltos).
- Regras de negócio ficam em src/domain (funções puras) com testes em tests/.
- Páginas não acessam o banco direto: página -> service -> repository/RPC.
- Operações em mais de uma tabela devem ser RPC PL/pgSQL (transação única).
- Dinheiro sempre com Decimal / numeric(12,2); nunca float.
- Datas no fuso America/Sao_Paulo; formatos dd/mm/aaaa e R$ 1.234,56.
- Nunca commitar segredos. Nunca usar a service_role key no app.
- Ao terminar cada fase: rodar pytest, atualizar o README e fazer commit com mensagem descritiva.
- Se uma regra do plano for ambígua, pergunte antes de decidir.
