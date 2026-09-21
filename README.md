# Controle de Locação e Manutenção de Motos

Sistema web para controlar locação, manutenção, documentação e vistorias de uma frota de motos de aluguel.

Ver plano completo em [Arquivos/Projeto_Locação.md](Arquivos/Projeto_Locação.md).

## Stack

Python 3.11+, Streamlit, Supabase (PostgreSQL + Auth + Storage), Plotly, pytest.

## Setup

1. Crie um projeto no Supabase e aplique as migrations em `supabase/migrations/` (0001 a 0004), na ordem, e depois `supabase/seed.sql`.
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

## Status

Divisão de trabalho: backend (`src/domain`, `src/repositories`, `src/services`,
`supabase/migrations`, testes) e frontend (`pages/`, `src/ui`) em paralelo.

- [x] **Fase 0 — Fundação:** estrutura de pastas, login/logout com sessão
      Supabase (`src/auth.py`, `src/db.py`).
- [ ] **Fase 1 — Cadastros de motos e clientes:** validadores de CPF, placa e
      telefone prontos e testados (`src/domain/validadores.py`); repositórios
      e services de Motos e Clientes prontos, com validação, normalização de
      placa/CPF e atualização de km com confirmação quando o valor é menor
      que o atual. Falta a interface (`pages/2_Motos.py`, `pages/3_Clientes.py`).
- [ ] **Fase 2 — Contratos e cobranças:** `domain/agenda_cobrancas.py` e
      `domain/encargos.py` prontos e testados (encargos de 2% multa + 1%/mês
      pro rata; 1ª cobrança antecipada na data de início; contratos sempre com
      prazo definido). RPCs `rpc_criar_contrato`, `rpc_encerrar_contrato` e
      `rpc_gerar_cobrancas_pendentes` em `supabase/migrations/0004_rpc.sql`,
      com repositórios e services de Contratos e Cobranças prontos. Falta
      aplicar a migration num projeto Supabase real, rodar o roteiro manual
      de verificação (seção 9 do plano) e a interface
      (`pages/4_Contratos.py`, `pages/5_Cobrancas.py`).
