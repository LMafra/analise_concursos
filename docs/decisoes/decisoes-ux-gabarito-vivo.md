# Decisões de UX — Gabarito Vivo

Consolida o diagnóstico UI/UX, as respostas NotebookLM (blocos A–E) e o grill (Q1–Q13). Alternativas descartadas ficam registradas para não reabrir o escopo sem motivo.

## Entrega

- **Leva única** do diagnóstico §1–§8 + rename, em **5 PRs** com gate (tokens/relatório → chrome/IA → padrões → rename → aceite).
- Pacote Python `concursos` permanece; pasta de dados e projeto é `.gabarito-vivo/` (migração única a partir de `.concurso/`).
- Distribuição PyPI/uv e comando: `gabarito-vivo`. Sem alias legado.
- Aceite: `docs/produto/checklist-aceite-gabarito-vivo.md`.

## Navegação

| Item | Papel |
|---|---|
| Minhas Provas | Organizar, corrigir, Importar TEC, CTA Analisar |
| Resultados | Relatório + Tópicos; Exportar utilitário |
| Estudar | Livros, perguntar, simulado, prática TEC, disciplinas |
| Concursos | PCI / prazos |

Home recorrente: **Minhas Provas**. Sem “Dashboard Geral”. Breadcrumb + ← Voltar em profundidade > 3.

## Relatório (`index.html`)

Primeira dobra: diagnóstico da última prova → ≤3 cards (corte, tendência, nota) → “O que fazer agora” (ganho de pontos; urgência desempata; esforço = badge).

Progressive disclosure: top 3–5 fracos por impacto; disciplinas em `<details>`; 1 gráfico nota×corte; demais figuras em `<details>`; PCI fora do HTML; simulado/recomendações/TEC = cards-atalho; jargão estatístico só no apêndice.

`relatorio.html` por concurso: herda tokens/CSS/selos, sem nova hierarquia de primeira dobra.

## Fluxos

- Onboarding ≤3 passos; sem área de foco no schema; aterrissagem: há diagnóstico → Resultados, senão Minhas Provas + CTA.
- Loading: etapas leigas + skeleton + log em accordion; botão **Cancelar análise** (corte cooperativo entre etapas; pasta temporária).
- Conferir + edital a confirmar: master-detail + sticky; novo concurso: wizard.
- Excluir concurso / livro / Salvar: Undo via toast e lixeira de sessão; modal de confirmação na exclusão do concurso.
- On-blur + inline; sumário se >7 campos; dirty nav com “Continuar editando”.
- Falha parcial PCI/IA: banner no bloco; ≤1 toast consolidado.
- Toasts: sucesso 4–6 s; erro persistente + `aria-live`.

## A11y

Alvos ≥44×44; focus trap; Esc; ARIA nos selos; `prefers-reduced-motion` = sem animar.

## Aceite (§8)

Tokens `:root` sem hex solto no corpo HTML; sidebar 4; segmented tema; `@media print`; selos redundantes; on-blur; Undo; banners de falha parcial; 44 px; foco em modais.

## Validação com usuários (§7)

Cinco tarefas think-aloud (diagnóstico, estudo da semana, lacuna, tendência, treino a partir do relatório). Métricas: &lt;5 s até primeira ação; ≤2 cliques até tópico fraco; SEDQ ≥ 6. Sem telemetria no app.

## Fora de escopo desta leva

Telemetria; nuvem; rename do repositório GitHub / pacote Python `concursos`; tipografia display; motion fino; visual-regression automatizada NiceGUI; área de foco modelada.

## Protótipos HTML — o que não entra

Cruzamento com `Protótipo_Interativo_—_Gabarito_Vivo.html` e `Guia_Prático_para_Criar_um_Sistema_de_Design.html`. Aproveitamos layout (banner de status, medidor de corte, marca no drawer, seletor de concurso em Resultados). **Não** entram:

| Protótipo / guia | Motivo |
|---|---|
| Card percentil / “Top N%” / posição estimada | Fora de escopo (não estimar colocação) |
| Rótulo “KPI” | Anti-padrão da marca → “indicadores” / “ganho de pontos” |
| Escuro primary `#63C2CF` | Marca e `tema.py` usam `#4ADE80` |
| Nomes Material `--primary` / `--surface-container-*` | Tokens só via `--ca-*` / `tema.py` / `design_tokens.py` |
| IBM Plex via Google Fonts | Rede sem opt-in |
| Tema segmentado na sidebar | Configurações > Aparência |
| Home padrão = Resultados | Home recorrente = Minhas Provas |
| Motion scale (`--dur-micro`) + tipografia display | Dívida / leva futura |
| Delete só com confirm, toast sem Desfazer | Undo via toast |

Texto suave canônico: `#475569` (código e marca alinhados; o guia usava `#64748B`).
