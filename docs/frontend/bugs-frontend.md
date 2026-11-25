# Bugs de frontend — Gabarito Vivo

Frente 2. Evidência: Playwright map F1 (`mapa-bruto-*.json`, `screenshots/`, `interacoes-mapeadas.md`) + inspeção de `tema.py` (`ALVO_MINIMO=44px`, `.ca-alvo`).

Severidade: crítica / alta / média / baixa.  
Esforço: S (&lt;2h) / M (2–8h) / L (&gt;8h).

## Top 10 (prioridade de correção)

| # | ID | Severidade |
|---|---|---|
| 1 | BUG-01 | crítica |
| 2 | BUG-02 | crítica |
| 3 | BUG-03 | alta |
| 4 | BUG-04 | alta |
| 5 | BUG-05 | alta |
| 6 | BUG-06 | alta |
| 7 | BUG-07 | alta |
| 8 | BUG-08 | média |
| 9 | BUG-09 | média |
| 10 | BUG-10 | média |

## Tabela completa

| ID | Tela | Categoria | Severidade | Descrição | Evidência | Impacto | Esforço |
|---|---|---|---|---|---|---|---|
| BUG-01 | `/respostas` | Responsividade / Interação | crítica | Alternativas A–E medem ~17×32px (≪44). Em mobile 375px a grade fica inutilizável. | `real_respostas_*`; 353/362 under44 @desktop | Impede marcar respostas no touch | M |
| BUG-02 | Shell (todas) | Responsividade | crítica | Em 375×812 o drawer esquerdo permanece aberto e consome ~metade da largura; conteúdo principal espremido. Menu hamburger existe (`aria-label="Abrir menu"`) mas drawer não colapsa no breakpoint. | `real_home_mobile.png`, `real_respostas_mobile.png` | App desktop-only de fato | M |
| BUG-03 | Shell | Responsividade / DS | alta | CTAs primários (CONTINUAR, CADASTRAR, SALVAR, ABRIR NO NAVEGADOR, etc.) com altura ~36px apesar de `ALVO_MINIMO=44px` / `.ca-alvo` em `tema.py`. Classe `ca-alvo` pouco aplicada. | map under44 em quase todas as telas | Touch impreciso; DS não cumprido | S |
| BUG-04 | `/?aba=tec`, `/novo`, `/estudar` | Interação / a11y | alta | Controle "Escolher arquivos" 32×32px. | map home-tec / novo / estudar | Fácil errar o alvo; a11y | S |
| BUG-05 | `/` home | Usabilidade / produto | alta | Sem dashboard KPI (concursos/TEC/simulados). Home = só lista. Objetivo F5; trata-se como gap bloqueador da visão do produto. | `real_home_desktop.png`; 0 KPI no DOM | Usuário abre N telas para ver desempenho | L |
| BUG-06 | Estudar > TEC / prática | Usabilidade / produto | alta | Prática TEC não agrupa `mat`→`ass` na GUI; `url` por questão ausente; `cad` ainda aparece como eixo em CSVs/resumo. | map estudar-pratica; código `pratica/` | Estudo por assunto difícil | L |
| BUG-07 | `/resultados` | a11y / Integração | alta | Relatório vive em iframe; crawler só vê ~14 controles do chrome. Sem atalho nativo para seções do `index.html` (dashboard/tópicos). | map resultados; `relatorio.py` | Leitor de tela / teclado pobres na análise | M |
| BUG-08 | `/` lista | Visual / Usabilidade | média | Item incompleto exibe slug cru (`camara_dos_deputados_2002_pci…`) em vez de nome amigável. | `real_home_desktop.png` | Confunde; quebra linguagem leiga | S |
| BUG-09 | Header | Usabilidade / Privacidade UI | média | Path absoluto WSL (`/mnt/c/Users/...`) sempre visível no header. | screenshots home | Expõe estrutura do SO; ruído | S |
| BUG-10 | `/configuracoes` | Responsividade | média | 14/23 alvos under44; sliders/selects densos (altura 28px). | map configuracoes | Touch difícil | S |
| BUG-11 | `/disciplinas` | Responsividade | média | 57/67 alvos under44 (chips/linhas densas). | map disciplinas | Edição penosa no mobile | M |
| BUG-12 | Shell | Interação | média | Busca global altura 40px (&lt;44). | todas as telas | Inconsistente com ALVO_MINIMO | S |
| BUG-13 | `/concursos` | Integração / Empty | média | Com PCI off, tela = só consentimento; empty state sem preview do valor da feature além do texto legal. | map concursos; screenshot consent | Onboarding PCI pobre | S |
| BUG-14 | Diálogos ⋯ | Interação | média | Menu `more_vert` existe (`concursos.py`); validar stopPropagation + foco de retorno em testes (risco de clique no card). | código `paginas/concursos.py:219` | Clique no ⋯ pode acionar card | S |
| BUG-15 | Toasts | Estado | média | Sem verificação automatizada de toast duplicado / `aria-live` nesta leva de map estático — flag para teste F4. | `componentes/toasts.py` | Erros silenciosos ou spam | S |
| BUG-16 | HTML `index.html` | Produto | alta | Sem 1ª dobra dashboard 3 fontes; sem `topicos.html` / `tec.html`. | as-is `relatorio_html_secoes.py` | Relatório monolítico | L |
| BUG-17 | `/inicio` | Usabilidade | baixa | CONTINUAR 36px. | map inicio | Touch | S |
| BUG-18 | `/sobre` | Usabilidade | baixa | CONFERIR O AMBIENTE 36px. | map sobre | Touch | S |
| BUG-19 | Empty home | Empty state | média | Empty `/tmp/concursos-empty` ainda mostra chrome completo; validar CTA de onboarding vs lista vazia. | `empty_home_desktop.png` | Risco de dead-end | S |
| BUG-20 | Hover/focus | a11y | média | Map estático não capturou :focus-visible / prefers-reduced-motion — cobrir com axe na F4. | — | a11y incompleta | M |

## Notas

- Tokens já definem 44px; bug é **aplicação**, não ausência de DS.
- BUG-05/06/16 são gaps de produto cobertos pela Frente 5; F4 foca shell/touch/respostas/mobile drawer/slug/path.
- PII: evidências em `screenshots/` gitignored; não colar nomes/CPF neste doc além de slugs já públicos no UI.

## Ordem F4

1. BUG-02 drawer mobile  
2. BUG-01 + BUG-03 + BUG-04 + BUG-12 alvos ≥44  
3. BUG-08 slug + BUG-09 path  
4. BUG-10/11/13/14/15/17/18/19/20  
5. BUG-05/06/07/16 → Frente 5  
