# Controle de Locação e Manutenção de Motos

Sistema web para controlar locação, manutenção, documentação e vistorias de uma frota de motos de aluguel.

Ver plano completo em [Arquivos/Projeto_Locação.md](Arquivos/Projeto_Locação.md).

## Stack

Python 3.11+, Streamlit, Supabase (PostgreSQL + Auth + Storage), Plotly, pytest.

## Setup

1. Crie um projeto no Supabase e aplique as migrations em `supabase/migrations/` (0001 a 0003), na ordem, e depois `supabase/seed.sql`.
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
