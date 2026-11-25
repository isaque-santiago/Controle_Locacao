# Documentação do projeto

Índice dos documentos em `Arquivos/`. O plano mestre e os três guias de uso corrente ficam aqui na raiz (o `CLAUDE.md` aponta para eles); o resto está em subpastas por tema.

## Essenciais (nesta pasta)

| Documento | Para que serve |
|---|---|
| [Projeto_Locação.md](Projeto_Locação.md) | **Plano mestre**: fases, regras de negócio, decisões do dono e o feedback pós-entrega (seção 23). |
| [Analise_Migracao_Frontend.md](Analise_Migracao_Frontend.md) | Decisões e histórico da migração da interface (Streamlit para FastAPI, Jinja2, HTMX e Tailwind). |
| [Deploy_VPS.md](Deploy_VPS.md) | Guia de implantação na VPS (Coolify): variáveis, tarefa agendada de WhatsApp, verificação pós-deploy. |
| [Revisao_Seguranca.md](Revisao_Seguranca.md) | Revisão de segurança do app web e requisitos para o deploy; riscos aceitos pelo dono. |

## `interface/`: design e experiência de uso

| Documento | Para que serve |
|---|---|
| [Design_UI.md](interface/Design_UI.md) | Referência de design: tokens, componentes e decisões visuais. |
| [Plano_Melhorias_UI_UX.md](interface/Plano_Melhorias_UI_UX.md) | Plano de melhorias de UI/UX e responsividade (etapas 0 a 9). |
| [Plano_Redesign_Visual.md](interface/Plano_Redesign_Visual.md) | Auditoria do frontend (23/11/2026) e plano de melhoria visual. |
| [Achados_UI_UX.md](interface/Achados_UI_UX.md) | Registro curado dos achados da suíte `e2e/`, com a etapa que resolve cada um. |
| [Inventario_UI_UX.md](interface/Inventario_UI_UX.md) | Mapa de páginas, visões e diálogos (base da suíte `e2e/`). |
| [Estudo_Dashboard.md](interface/Estudo_Dashboard.md) | Estudo e proposta de redesenho do Dashboard, com as decisões do dono. |

## `dados/`: carga e conciliação de dados

| Documento | Para que serve |
|---|---|
| [Importacao_Dados_Reais.md](dados/Importacao_Dados_Reais.md) | Modelo de dados e plano de carga da planilha "PAGAMENTO MOTOS"; situação em dev e produção. |
| [Sincronizacao_Chats.md](dados/Sincronizacao_Chats.md) | Protocolo para conciliar o sistema com os chats "Acompanhamento Financeiro" e "Contratos Locadora". |

## `homologacao/`: testes de aceite

| Documento | Para que serve |
|---|---|
| [Roteiro_Homologacao_Manual.md](homologacao/Roteiro_Homologacao_Manual.md) | O que a automação não prova: uso real dos fluxos, aparelho físico e câmera. |

## `conferencia/` (fora do git)

Conferências de dados de produção, com nomes de clientes. A pasta é ignorada pelo `.gitignore`: nada dela vai para o repositório.
