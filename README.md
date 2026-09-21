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
      `rpc_gerar_cobrancas_pendentes` em
      `supabase/migrations/20260921120300_rpc.sql`, aplicadas no Supabase, com
      repositórios e services de Contratos e Cobranças prontos. Falta rodar o
      roteiro manual de verificação (seção 9 do plano) e a interface
      (`pages/4_Contratos.py`, `pages/5_Cobrancas.py`).
- [ ] **Fase 3 — Manutenção:** `domain/manutencao_regras.py` pronto e testado
      (próxima km/data e situação em_dia/proxima/vencida, o que vencer
      primeiro). RPCs `rpc_aplicar_plano_padrao` e `rpc_registrar_manutencao`
      em `supabase/migrations/20260921130000_rpc_manutencao.sql` (aplicar no
      Supabase), com repositórios e services de catálogo, plano por moto,
      alertas e registro de manutenção prontos. Falta aplicar a migration,
      rodar o roteiro manual e a interface (`pages/6_Manutencao.py`, aba de
      plano na ficha da moto).
- [ ] **Fase 4 — Documentos e vencimentos:** `domain/documentos.py` pronto e
      testado (sugestão do documento do ano seguinte ao regularizar um
      documento de renovação anual: IPVA, licenciamento, seguro). Repositório
      e service de `documentos_moto` prontos, com upload de comprovante e URL
      assinada de curta duração no bucket privado `documentos`. Alertas de
      documentos e CNH já cobertos por `services/alertas.py` (Fase 3). Falta a
      interface (`pages/7_Documentos.py`).
- [ ] **Fase 5 — Vistorias:** `domain/vistorias.py` pronto e testado
      (checklist padrão de 15 itens e comparação entrega x devolução, item a
      item). RPC `rpc_registrar_vistoria` em
      `supabase/migrations/20260921140000_rpc_vistoria.sql` (aplicar no
      Supabase) grava a vistoria e o km no histórico numa transação; o índice
      único (contrato_id, tipo) garante uma vistoria de cada tipo por
      contrato. Repositórios e service prontos, com upload de fotos e URL
      assinada no bucket privado `vistorias`. Falta aplicar a migration,
      rodar o roteiro manual e a interface (`pages/8_Vistorias.py`).
