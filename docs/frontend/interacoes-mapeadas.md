# Interações mapeadas — Gabarito Vivo GUI

Ultracave. Frente 1.

## Método

- App: NiceGUI `http://127.0.0.1:8765/`
- Projeto filled: `/mnt/c/Users/lucas/Documents/Concursos` (candidato `lucas`)
- Empty: `/tmp/concursos-empty`
- Ferramenta: Playwright (Chromium cache). MCP `plugin-playwright-playwright` falhou sem `/opt/google/chrome/chrome` (sudo); mapeamento via Playwright API + CDP — mesmo motor, não browser-use.
- Viewports: 1440×900, 768×1024, 375×812
- Artefatos brutos: `mapa-bruto-real.json`, `mapa-bruto-empty.json`, `screenshots/` (gitignored)
- Capturado: real 2026-11-25T11:38:07.128Z; empty 2026-11-25T11:44:41.147Z

## Contagem por atividade

| Atividade | Cliques | Inputs | Decisões | Passos totais | Observação |
|---|---:|---:|---:|---:|---|
| Abrir projeto / onboarding | 3 | 2 | 2 | 7 | Escolher pasta → nome → pastas → primeiro resultado |
| Cadastrar / abrir prova | 4 | 1 | 2 | 7 | Minhas Provas → Novo → upload/papel → salvar |
| Digitar respostas | N alternativas | 0 | N questões | varia | 362 alvos em desktop (1 por alternativa/controle); alto custo de interação |
| Rodar análise | 2 | 0 | 1 | 3 | Disparar análise → aguardar progresso → ir a Resultados |
| Ver resultados consolidados | 3 | 0 | 1 | 4 | Aba Relatório/Tópicos + export + abrir no navegador |
| Importar prática TEC | 4 | 2 | 2 | 8 | Aba TEC → escolher arquivo → mapear colunas → importar |
| Estudar (livros / perguntar / simulado / prática) | 5 | 1 | 2 | 8 | Trocar abas + CTA por painel; prática lê CSVs gerados |
| Concursos PCI | 3 | 2 | 1 | 6 | Encontrar/Provas; empty se integração off |
| Configurar preferências | 4 | 3 | 3 | 10 | Sliders/toggles + disciplinas/temas (67 alvos) |
| Conferir tópicos/edital | 3 | 2 | 2 | 7 | Drawer/página de conferência por concurso |

## Resumo por tela (desktop filled)

| Tela | Rota | Interações únicas | Alvos <44px | Screenshot desktop |
|---|---|---:|---:|---|
| home | `/` | 17 | 3 | `screenshots/real_home_desktop.png` |
| home-tec | `/?aba=tec` | 21 | 12 | `screenshots/real_home-tec_desktop.png` |
| inicio | `/inicio` | 11 | 3 | `screenshots/real_inicio_desktop.png` |
| novo | `/novo` | 15 | 5 | `screenshots/real_novo_desktop.png` |
| respostas | `/respostas` | 17 | 8 | `screenshots/real_respostas_desktop.png` |
| analise | `/analise` | 12 | 2 | `screenshots/real_analise_desktop.png` |
| resultados | `/resultados` | 14 | 4 | `screenshots/real_resultados_desktop.png` |
| estudar | `/estudar` | 15 | 6 | `screenshots/real_estudar_desktop.png` |
| estudar-livros | `/estudar?aba=livros` | 15 | 6 | `screenshots/real_estudar-livros_desktop.png` |
| estudar-perguntar | `/estudar?aba=perguntar` | 14 | 4 | `screenshots/real_estudar-perguntar_desktop.png` |
| estudar-simulado | `/estudar?aba=simulado` | 12 | 3 | `screenshots/real_estudar-simulado_desktop.png` |
| estudar-pratica | `/estudar?aba=pratica` | 14 | 2 | `screenshots/real_estudar-pratica_desktop.png` |
| concursos | `/concursos` | 12 | 3 | `screenshots/real_concursos_desktop.png` |
| concursos-encontrar | `/concursos?aba=encontrar` | 12 | 3 | `screenshots/real_concursos-encontrar_desktop.png` |
| concursos-provas | `/concursos?aba=provas` | 12 | 3 | `screenshots/real_concursos-provas_desktop.png` |
| projeto | `/projeto` | 12 | 4 | `screenshots/real_projeto_desktop.png` |
| configuracoes | `/configuracoes` | 23 | 14 | `screenshots/real_configuracoes_desktop.png` |
| conferir | `/conferir` | 12 | 3 | `screenshots/real_conferir_desktop.png` |
| disciplinas | `/disciplinas` | 67 | 57 | `screenshots/real_disciplinas_desktop.png` |
| sobre | `/sobre` | 10 | 3 | `screenshots/real_sobre_desktop.png` |

## Empty states (desktop)

| Tela | Interações | Screenshot |
|---|---:|---|
| home empty | 12 | `screenshots/empty_home_desktop.png` |
| home-tec empty | 18 | `screenshots/empty_home-tec_desktop.png` |
| resultados empty | 10 | `screenshots/empty_resultados_desktop.png` |
| estudar empty | 15 | `screenshots/empty_estudar_desktop.png` |
| estudar-pratica empty | 10 | `screenshots/empty_estudar-pratica_desktop.png` |
| projeto empty | 12 | `screenshots/empty_projeto_desktop.png` |

## Tabelas por tela (desktop filled, deduplicado)

### home (`/`)

Screenshots: desktop `screenshots/real_home_desktop.png`; tablet/mobile em `screenshots/real_home_*.png`.
Aria: `screenshots/real_home_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| home-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| home-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| home-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| home-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| home-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| home-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| home-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| home-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| home-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| home-10 | TROCAR | button | — | click | enabled ⚠️62x32 | ação in-page |
| home-11 | MINHAS PROVAS | tab | — | click | enabled 143x48 | ação in-page |
| home-12 | TELEBRAS 2025 — Especialista em Gestão de Telecomunicações – Analista de Tecnologia da Informação Telecomunicações Brasi | tabpanel | — | click | enabled 1136x794 | ação in-page |
| home-13 | insights VER RESULTADO | button | — | click | enabled 143x44 | ação in-page |
| home-14 | Mais ações | button | Mais ações | click | enabled 44x44 | ação in-page |
| home-15 | upload_file ADICIONAR O EDITAL E A PROVA | button | — | click | enabled 246x44 | ação in-page |
| home-16 | add NOVO CONCURSO | button | — | click | enabled 183x44 | ação in-page |
| home-17 | play_arrow ANALISAR | button | — | click | enabled 135x44 | ação in-page |

### home-tec (`/?aba=tec`)

Screenshots: desktop `screenshots/real_home-tec_desktop.png`; tablet/mobile em `screenshots/real_home-tec_*.png`.
Aria: `screenshots/real_home-tec_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| home-tec-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| home-tec-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| home-tec-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| home-tec-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| home-tec-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| home-tec-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| home-tec-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| home-tec-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| home-tec-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| home-tec-10 | TROCAR | button | — | click | enabled ⚠️62x32 | ação in-page |
| home-tec-11 | IMPORTAR DO TEC | tab | — | click | enabled 152x48 | ação in-page |
| home-tec-12 | Solte a planilha que você exportou do TEC (.csv ou .xlsx) ou os arquivos tec-erros-*.json da captura (computador e table | tabpanel | — | click | enabled 1136x935 | ação in-page |
| home-tec-13 | Escolher arquivos | button | Escolher arquivos | click | enabled ⚠️32x32 | ação in-page |
| home-tec-14 | flag VER PRIORIDADES | button | — | click | enabled ⚠️185x36 | ação in-page |
| home-tec-15 | quiz VER SIMULADO COM MEUS ERROS | button | — | click | enabled ⚠️290x36 | ação in-page |
| home-tec-16 | lightbulb EXPLICAR ERROS NO CADERNO DE ESTUDO | button | — | click | enabled ⚠️347x36 | ação in-page |
| home-tec-17 | search BUSCAR PROVAS NO PCI | button | — | click | enabled ⚠️227x36 | ação in-page |
| home-tec-18 | replay REPETIR ERROS | button | — | click | enabled ⚠️170x36 | ação in-page |
| home-tec-19 | folder_open ABRIR A PASTA DA EXTENSÃO | button | — | click | enabled ⚠️262x36 | ação in-page |
| home-tec-20 | folder_open ABRIR A PASTA DOS ARQUIVOS | button | — | click | enabled ⚠️269x36 | ação in-page |
| home-tec-21 | menu_book ABRIR O CADERNO DE ERROS | button | — | click | enabled ⚠️256x36 | ação in-page |

### inicio (`/inicio`)

Screenshots: desktop `screenshots/real_inicio_desktop.png`; tablet/mobile em `screenshots/real_inicio_*.png`.
Aria: `screenshots/real_inicio_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| inicio-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| inicio-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| inicio-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| inicio-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| inicio-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| inicio-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| inicio-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| inicio-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| inicio-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| inicio-10 | seu nome | textbox | seu nome | type | enabled 768x56 | input |
| inicio-11 | arrow_forward CONTINUAR | button | — | click | enabled ⚠️146x36 | ação in-page |

### novo (`/novo`)

Screenshots: desktop `screenshots/real_novo_desktop.png`; tablet/mobile em `screenshots/real_novo_*.png`.
Aria: `screenshots/real_novo_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| novo-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| novo-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| novo-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| novo-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| novo-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| novo-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| novo-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| novo-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| novo-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| novo-10 | Minhas Provas | button | — | click | enabled 101x44 | ação in-page |
| novo-11 | Escolher arquivos | button | Escolher arquivos | click | enabled ⚠️32x32 | ação in-page |
| novo-12 | nome do candidato | textbox | nome do candidato | type | enabled 768x56 | input |
| novo-13 | Expandir "Mensagens do cadastro" | button | Expandir "Mensagens do cadastro" | click | enabled 768x48 | ação in-page |
| novo-14 | check CADASTRAR | button | — | click | enabled ⚠️149x36 | ação in-page |
| novo-15 | CANCELAR | button | — | click | enabled ⚠️103x36 | ação in-page |

### respostas (`/respostas`)

Screenshots: desktop `screenshots/real_respostas_desktop.png`; tablet/mobile em `screenshots/real_respostas_*.png`.
Aria: `screenshots/real_respostas_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| respostas-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| respostas-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| respostas-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| respostas-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| respostas-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| respostas-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| respostas-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| respostas-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| respostas-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| respostas-10 | Minhas Provas | button | — | click | enabled 101x44 | ação in-page |
| respostas-11 | nome do candidato | textbox | nome do candidato | type | enabled 896x56 | input |
| respostas-12 | A | button | — | click | enabled ⚠️17x32 | ação in-page |
| respostas-13 | B | button | — | click | enabled ⚠️17x32 | ação in-page |
| respostas-14 | C | button | — | click | enabled ⚠️17x32 | ação in-page |
| respostas-15 | D | button | — | click | enabled ⚠️17x32 | ação in-page |
| … | +2 elementos omitidos (ver JSON) | | | | | |

### analise (`/analise`)

Screenshots: desktop `screenshots/real_analise_desktop.png`; tablet/mobile em `screenshots/real_analise_*.png`.
Aria: `screenshots/real_analise_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| analise-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| analise-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| analise-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| analise-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| analise-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| analise-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| analise-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| analise-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| analise-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| analise-10 | Minhas Provas | button | — | click | enabled 101x44 | ação in-page |
| analise-11 | Expandir "Ver detalhes técnicos de processamento" | button | Expandir "Ver detalhes técnicos de processamento" | click | enabled 896x48 | ação in-page |
| analise-12 | play_arrow ANALISAR | button | — | click | enabled 135x44 | ação in-page |

### resultados (`/resultados`)

Screenshots: desktop `screenshots/real_resultados_desktop.png`; tablet/mobile em `screenshots/real_resultados_*.png`.
Aria: `screenshots/real_resultados_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| resultados-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| resultados-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| resultados-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| resultados-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| resultados-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| resultados-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| resultados-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| resultados-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| resultados-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| resultados-10 | insights RELATÓRIO | tab | — | click | enabled 105x72 | ação in-page |
| resultados-11 | Concurso analisado Visão geral arrow_drop_down open_in_new ABRIR NO NAVEGADOR download quiz SIMULADO E PRÁTICA | tabpanel | — | click | enabled 1136x783 | ação in-page |
| resultados-12 | open_in_new ABRIR NO NAVEGADOR | button | — | click | enabled ⚠️216x36 | ação in-page |
| resultados-13 | Exportar | button | Exportar | click | enabled 44x44 | ação in-page |
| resultados-14 | quiz SIMULADO E PRÁTICA | button | — | click | enabled ⚠️210x36 | ação in-page |

### estudar (`/estudar`)

Screenshots: desktop `screenshots/real_estudar_desktop.png`; tablet/mobile em `screenshots/real_estudar_*.png`.
Aria: `screenshots/real_estudar_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| estudar-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| estudar-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| estudar-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| estudar-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| estudar-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| estudar-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| estudar-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| estudar-10 | menu_book MEUS LIVROS | tab | — | click | enabled 121x72 | ação in-page |
| estudar-11 | download Prepare a biblioteca uma vez Para estudar com seus livros, o app precisa preparar o open-notebook no seu comput | tabpanel | — | click | enabled 1024x739 | ação in-page |
| estudar-12 | download PREPARAR AGORA | button | — | click | enabled ⚠️188x36 | ação in-page |
| estudar-13 | disciplina do livro | combobox | disciplina do livro | select | enabled ⚠️220x24 | input |
| estudar-14 | Escolher arquivos | button | Escolher arquivos | click | enabled ⚠️32x32 | ação in-page |
| estudar-15 | upload_file ADICIONAR MEU PRIMEIRO LIVRO | button | — | click | enabled ⚠️284x36 | ação in-page |

### estudar-livros (`/estudar?aba=livros`)

Screenshots: desktop `screenshots/real_estudar-livros_desktop.png`; tablet/mobile em `screenshots/real_estudar-livros_*.png`.
Aria: `screenshots/real_estudar-livros_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| estudar-livros-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| estudar-livros-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| estudar-livros-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| estudar-livros-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| estudar-livros-10 | menu_book MEUS LIVROS | tab | — | click | enabled 121x72 | ação in-page |
| estudar-livros-11 | download Prepare a biblioteca uma vez Para estudar com seus livros, o app precisa preparar o open-notebook no seu comput | tabpanel | — | click | enabled 1024x739 | ação in-page |
| estudar-livros-12 | download PREPARAR AGORA | button | — | click | enabled ⚠️188x36 | ação in-page |
| estudar-livros-13 | disciplina do livro | combobox | disciplina do livro | select | enabled ⚠️220x24 | input |
| estudar-livros-14 | Escolher arquivos | button | Escolher arquivos | click | enabled ⚠️32x32 | ação in-page |
| estudar-livros-15 | upload_file ADICIONAR MEU PRIMEIRO LIVRO | button | — | click | enabled ⚠️284x36 | ação in-page |

### estudar-perguntar (`/estudar?aba=perguntar`)

Screenshots: desktop `screenshots/real_estudar-perguntar_desktop.png`; tablet/mobile em `screenshots/real_estudar-perguntar_*.png`.
Aria: `screenshots/real_estudar-perguntar_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| estudar-perguntar-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| estudar-perguntar-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| estudar-perguntar-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| estudar-perguntar-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| estudar-perguntar-10 | search PERGUNTAR | tab | — | click | enabled 112x72 | ação in-page |
| estudar-perguntar-11 | search PERGUNTAR Procurar em: Meus livros Minhas análises Tudo Disciplina Todas arrow_drop_down Para uma resposta escrit | tabpanel | — | click | enabled 1024x228 | ação in-page |
| estudar-perguntar-12 | pergunta | textbox | pergunta | type | enabled 836x56 | input |
| estudar-perguntar-13 | search PERGUNTAR | button | — | click | enabled ⚠️148x36 | ação in-page |
| estudar-perguntar-14 | Meus livros | radio | Meus livros | click | enabled ⚠️111x40 | ação in-page |

### estudar-simulado (`/estudar?aba=simulado`)

Screenshots: desktop `screenshots/real_estudar-simulado_desktop.png`; tablet/mobile em `screenshots/real_estudar-simulado_*.png`.
Aria: `screenshots/real_estudar-simulado_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| estudar-simulado-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| estudar-simulado-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| estudar-simulado-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| estudar-simulado-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| estudar-simulado-10 | quiz SIMULADO | tab | — | click | enabled 102x72 | ação in-page |
| estudar-simulado-11 | quiz VER SIMULADO COM MEUS ERROS DO TEC Simulado focado  0 questões de provas anteriores nos tópicos em que você ficou a | tabpanel | — | click | enabled 1024x280 | ação in-page |
| estudar-simulado-12 | quiz VER SIMULADO COM MEUS ERROS DO TEC | button | — | click | enabled ⚠️341x36 | ação in-page |

### estudar-pratica (`/estudar?aba=pratica`)

Screenshots: desktop `screenshots/real_estudar-pratica_desktop.png`; tablet/mobile em `screenshots/real_estudar-pratica_*.png`.
Aria: `screenshots/real_estudar-pratica_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| estudar-pratica-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| estudar-pratica-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| estudar-pratica-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| estudar-pratica-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| estudar-pratica-10 | school PRÁTICA NO TEC | tab | — | click | enabled 141x72 | ação in-page |
| estudar-pratica-11 | Prática no TEC  2 erros registrados (0 repetidos, errado 2 vezes ou mais); 168 questões resolvidas nos cadernos acompanh | tabpanel | — | click | enabled 1024x781 | ação in-page |
| estudar-pratica-12 | Expandir "Desempenho por disciplina" | button | Expandir "Desempenho por disciplina" | click | enabled 992x48 | ação in-page |
| estudar-pratica-13 | Expandir "Erros" | button | Expandir "Erros" | click | enabled 992x48 | ação in-page |
| estudar-pratica-14 | Expandir "Cadernos" | button | Expandir "Cadernos" | click | enabled 992x48 | ação in-page |

### concursos (`/concursos`)

Screenshots: desktop `screenshots/real_concursos_desktop.png`; tablet/mobile em `screenshots/real_concursos_*.png`.
Aria: `screenshots/real_concursos_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| concursos-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| concursos-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| concursos-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| concursos-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| concursos-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| concursos-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| concursos-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| concursos-10 | ENCONTRAR CONCURSOS | tab | — | click | enabled 200x48 | ação in-page |
| concursos-11 | Desligada. Ao ligar: warning O que sai do computador A busca de concursos consulta o PCI Concursos pela internet (https: | tabpanel | — | click | enabled 1136x304 | ação in-page |
| concursos-12 | check CONCORDO E LIGAR | button | — | click | enabled ⚠️197x36 | ação in-page |

### concursos-encontrar (`/concursos?aba=encontrar`)

Screenshots: desktop `screenshots/real_concursos-encontrar_desktop.png`; tablet/mobile em `screenshots/real_concursos-encontrar_*.png`.
Aria: `screenshots/real_concursos-encontrar_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| concursos-encontrar-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| concursos-encontrar-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| concursos-encontrar-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| concursos-encontrar-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| concursos-encontrar-10 | ENCONTRAR CONCURSOS | tab | — | click | enabled 200x48 | ação in-page |
| concursos-encontrar-11 | Desligada. Ao ligar: warning O que sai do computador A busca de concursos consulta o PCI Concursos pela internet (https: | tabpanel | — | click | enabled 1136x304 | ação in-page |
| concursos-encontrar-12 | check CONCORDO E LIGAR | button | — | click | enabled ⚠️197x36 | ação in-page |

### concursos-provas (`/concursos?aba=provas`)

Screenshots: desktop `screenshots/real_concursos-provas_desktop.png`; tablet/mobile em `screenshots/real_concursos-provas_*.png`.
Aria: `screenshots/real_concursos-provas_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| concursos-provas-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| concursos-provas-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| concursos-provas-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| concursos-provas-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| concursos-provas-10 | PROVAS ANTERIORES | tab | — | click | enabled 172x48 | ação in-page |
| concursos-provas-11 | Desligada. Ao ligar: warning O que sai do computador A busca de concursos consulta o PCI Concursos pela internet (https: | tabpanel | — | click | enabled 1136x304 | ação in-page |
| concursos-provas-12 | check CONCORDO E LIGAR | button | — | click | enabled ⚠️197x36 | ação in-page |

### projeto (`/projeto`)

Screenshots: desktop `screenshots/real_projeto_desktop.png`; tablet/mobile em `screenshots/real_projeto_*.png`.
Aria: `screenshots/real_projeto_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| projeto-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| projeto-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| projeto-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| projeto-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| projeto-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| projeto-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| projeto-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| projeto-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| projeto-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| projeto-10 | pasta do projeto | textbox | pasta do projeto | type | enabled 672x56 | input |
| projeto-11 | folder_open ESCOLHER PASTA… | button | — | click | enabled ⚠️194x36 | ação in-page |
| projeto-12 | check USAR ESTA PASTA | button | — | click | enabled ⚠️187x36 | ação in-page |

### configuracoes (`/configuracoes`)

Screenshots: desktop `screenshots/real_configuracoes_desktop.png`; tablet/mobile em `screenshots/real_configuracoes_*.png`.
Aria: `screenshots/real_configuracoes_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| configuracoes-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| configuracoes-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| configuracoes-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| configuracoes-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| configuracoes-10 | Quando considerar uma leitura confiável | slider | Quando considerar uma leitura confiável | click | enabled ⚠️580x28 | ação in-page |
| configuracoes-11 | Quando considerar um tópico fraco | slider | Quando considerar um tópico fraco | click | enabled ⚠️580x28 | ação in-page |
| configuracoes-12 | save SALVAR | button | — | click | enabled ⚠️119x36 | ação in-page |
| configuracoes-13 | arrow_forward ABRIR | button | — | click | enabled ⚠️108x36 | ação in-page |
| configuracoes-14 | arrow_forward VER DETALHES | button | — | click | enabled ⚠️165x36 | ação in-page |
| configuracoes-15 | folder_open TROCAR | button | — | click | enabled ⚠️122x36 | ação in-page |
| configuracoes-16 | AUTO | button | — | click | enabled ⚠️68x36 | ação in-page |
| configuracoes-17 | CLARO | button | — | click | enabled ⚠️77x36 | ação in-page |
| configuracoes-18 | ESCURO | button | — | click | enabled ⚠️85x36 | ação in-page |
| configuracoes-19 | Usar inteligência artificial para ler editais | checkbox | — | toggle | enabled ⚠️292x40 | ação in-page |
| configuracoes-20 | Escolher arquivos | button | Escolher arquivos | click | enabled ⚠️32x32 | ação in-page |
| configuracoes-21 | respostas para a calibração | textbox | respostas para a calibração | type | enabled 160x56 | input |
| configuracoes-22 | tune CALIBRAR | button | — | click | enabled ⚠️134x36 | ação in-page |
| configuracoes-23 | Expandir "Avançado" | button | Expandir "Avançado" | click | enabled 672x48 | ação in-page |

### conferir (`/conferir`)

Screenshots: desktop `screenshots/real_conferir_desktop.png`; tablet/mobile em `screenshots/real_conferir_*.png`.
Aria: `screenshots/real_conferir_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| conferir-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| conferir-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| conferir-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| conferir-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| conferir-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| conferir-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| conferir-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| conferir-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| conferir-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| conferir-10 | Minhas Provas | button | — | click | enabled 101x44 | ação in-page |
| conferir-11 | ← Voltar para Minhas Provas | button | — | click | enabled 188x44 | ação in-page |
| conferir-12 | arrow_forward VER CONCURSOS | button | — | click | enabled ⚠️180x36 | ação in-page |

### disciplinas (`/disciplinas`)

Screenshots: desktop `screenshots/real_disciplinas_desktop.png`; tablet/mobile em `screenshots/real_disciplinas_*.png`.
Aria: `screenshots/real_disciplinas_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| disciplinas-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| disciplinas-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| disciplinas-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| disciplinas-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| disciplinas-10 | Configurações | button | — | click | enabled 99x44 | ação in-page |
| disciplinas-11 | voltar às configurações | button | voltar às configurações | click | enabled ⚠️42x42 | ação in-page |
| disciplinas-12 | category DISCIPLINAS | tab | — | click | enabled 115x72 | ação in-page |
| disciplinas-13 | Cada concurso escreve o nome da disciplina de um jeito. Junte os nomes que são a mesma disciplina, para comparar a sua e | tabpanel | — | click | enabled 896x2730 | ação in-page |
| disciplinas-14 | Administração Geral | checkbox | — | toggle | enabled ⚠️167x40 | ação in-page |
| disciplinas-15 | Administração Pública | checkbox | — | toggle | enabled ⚠️180x40 | ação in-page |
| disciplinas-16 | Análise de Sistemas | checkbox | — | toggle | enabled ⚠️166x40 | ação in-page |
| disciplinas-17 | Análise e Desenvolvimento de Sistemas | checkbox | — | toggle | enabled ⚠️288x40 | ação in-page |
| disciplinas-18 | Atualidades | checkbox | — | toggle | enabled ⚠️114x40 | ação in-page |
| disciplinas-19 | Auditoria Governamental | checkbox | — | toggle | enabled ⚠️194x40 | ação in-page |
| disciplinas-20 | Bancos de Dados | checkbox | — | toggle | enabled ⚠️149x40 | ação in-page |
| disciplinas-21 | Cargo 4: Perito Criminal Federal – Área 3: Informática Forense | checkbox | — | toggle | enabled ⚠️425x40 | ação in-page |
| disciplinas-22 | Computação em Nuvem | checkbox | — | toggle | enabled ⚠️191x40 | ação in-page |
| disciplinas-23 | Conhecimentos Gerais | checkbox | — | toggle | enabled ⚠️181x40 | ação in-page |
| disciplinas-24 | Contratações de TI | checkbox | — | toggle | enabled ⚠️158x40 | ação in-page |
| disciplinas-25 | Controle Externo | checkbox | — | toggle | enabled ⚠️144x40 | ação in-page |
| disciplinas-26 | Desenvolvimento de Sistemas | checkbox | — | toggle | enabled ⚠️227x40 | ação in-page |
| disciplinas-27 | Direito Administrativo | checkbox | — | toggle | enabled ⚠️174x40 | ação in-page |
| disciplinas-28 | Direito Constitucional | checkbox | — | toggle | enabled ⚠️174x40 | ação in-page |
| disciplinas-29 | Direitos Humanos | checkbox | — | toggle | enabled ⚠️152x40 | ação in-page |
| disciplinas-30 | Eixo Temático 1 - Ciência, Tecnologia e Sociedade (CTS) | checkbox | — | toggle | enabled ⚠️388x40 | ação in-page |
| disciplinas-31 | Eixo Temático 2 - Políticas Públicas de Ciência, Tecnologia e Inovação (CT&I) | checkbox | — | toggle | enabled ⚠️517x40 | ação in-page |
| disciplinas-32 | Eixo Temático 3 - Gestão de Projetos em Ciência, Tecnologia e Inovação (CT&I) | checkbox | — | toggle | enabled ⚠️529x40 | ação in-page |
| disciplinas-33 | Eixo Temático 4 - Tecnologias da Informação e Comunicação (TICs) & Ciência de Dados | checkbox | — | toggle | enabled ⚠️586x40 | ação in-page |
| disciplinas-34 | Eixo Temático 5 - Metodologia da Pesquisa Científica | checkbox | — | toggle | enabled ⚠️370x40 | ação in-page |
| disciplinas-35 | Engenharia de Dados | checkbox | — | toggle | enabled ⚠️172x40 | ação in-page |
| disciplinas-36 | Engenharia de Software | checkbox | — | toggle | enabled ⚠️188x40 | ação in-page |
| disciplinas-37 | Fiscalização de Contratos de TI | checkbox | — | toggle | enabled ⚠️235x40 | ação in-page |
| disciplinas-38 | Gestão de Tecnologia da Informação | checkbox | — | toggle | enabled ⚠️269x40 | ação in-page |
| disciplinas-39 | Governança de TI | checkbox | — | toggle | enabled ⚠️148x40 | ação in-page |
| disciplinas-40 | Informática | checkbox | — | toggle | enabled ⚠️112x40 | ação in-page |
| disciplinas-41 | Infraestrutura de TI | checkbox | — | toggle | enabled ⚠️159x40 | ação in-page |
| disciplinas-42 | Inteligência Artificial | checkbox | — | toggle | enabled ⚠️167x40 | ação in-page |
| disciplinas-43 | Inteligência de Negócios | checkbox | — | toggle | enabled ⚠️193x40 | ação in-page |
| disciplinas-44 | Legislação | checkbox | — | toggle | enabled ⚠️107x40 | ação in-page |
| disciplinas-45 | Legislação Específica do Setor de Telecomunicações Brasileiro | checkbox | — | toggle | enabled ⚠️432x40 | ação in-page |
| disciplinas-46 | Licitações e Contratos | checkbox | — | toggle | enabled ⚠️179x40 | ação in-page |
| disciplinas-47 | Língua Inglesa | checkbox | — | toggle | enabled ⚠️130x40 | ação in-page |
| disciplinas-48 | Língua Portuguesa | checkbox | — | toggle | enabled ⚠️157x40 | ação in-page |
| disciplinas-49 | Mitre ATT&CK, Cis | checkbox | — | toggle | enabled ⚠️153x40 | ação in-page |
| disciplinas-50 | Noções de Administração Orçamentária e Financeira | checkbox | — | toggle | enabled ⚠️368x40 | ação in-page |
| … | +17 elementos omitidos (ver JSON) | | | | | |

### sobre (`/sobre`)

Screenshots: desktop `screenshots/real_sobre_desktop.png`; tablet/mobile em `screenshots/real_sobre_*.png`.
Aria: `screenshots/real_sobre_desktop.aria.yml`.

| ID | Elemento | Role | Aria-label | Ação | Estado | Destino |
|---|---|---|---|---|---|---|
| sobre-1 | Abrir menu | button | Abrir menu | click | enabled 44x44 | ação in-page |
| sobre-2 | Buscar concurso ou tópico | textbox | — | type | enabled ⚠️232x40 | input |
| sobre-3 | assignment MINHAS PROVAS | button | — | click | enabled 207x44 | ação in-page |
| sobre-4 | insights RESULTADOS | button | — | click | enabled 207x44 | ação in-page |
| sobre-5 | menu_book ESTUDAR | button | — | click | enabled 207x44 | ação in-page |
| sobre-6 | travel_explore CONCURSOS | button | — | click | enabled 207x44 | ação in-page |
| sobre-7 | settings CONFIGURAÇÕES | button | — | click | enabled 207x44 | ação in-page |
| sobre-8 | info SOBRE | button | — | click | enabled 207x44 | ação in-page |
| sobre-9 | power_settings_new FECHAR O APP | button | — | click | enabled ⚠️207x36 | ação in-page |
| sobre-10 | fact_check CONFERIR O AMBIENTE | button | — | click | enabled ⚠️219x36 | ação in-page |

## Achados rápidos (insumo F2)

- `respostas`: 362 alvos — densidade extrema; muitos <44px prováveis.
- Drawer/nav presente em quase todas as telas (~8–12 links fixos).
- Sem dashboard KPI na home filled (só lista de provas + abas).
- TEC em `/?aba=tec`: ~21 alvos; empty TEC ~18.
- Resultados ~14 alvos (iframe relatório = pouca superfície acessível ao crawler fora do iframe).
- Disciplinas: 67 alvos (lista/edição densa).
- Concursos PCI ~12 alvos (integração provavelmente off/empty).

## Inventário de rotas cobertas

- `/` → 34 els @desktop
- `/?aba=tec` → 21 els @desktop
- `/inicio` → 11 els @desktop
- `/novo` → 15 els @desktop
- `/respostas` → 362 els @desktop
- `/analise` → 12 els @desktop
- `/resultados` → 14 els @desktop
- `/estudar` → 15 els @desktop
- `/estudar?aba=livros` → 15 els @desktop
- `/estudar?aba=perguntar` → 14 els @desktop
- `/estudar?aba=simulado` → 12 els @desktop
- `/estudar?aba=pratica` → 14 els @desktop
- `/concursos` → 12 els @desktop
- `/concursos?aba=encontrar` → 12 els @desktop
- `/concursos?aba=provas` → 12 els @desktop
- `/projeto` → 12 els @desktop
- `/configuracoes` → 23 els @desktop
- `/conferir` → 12 els @desktop
- `/disciplinas` → 67 els @desktop
- `/sobre` → 10 els @desktop