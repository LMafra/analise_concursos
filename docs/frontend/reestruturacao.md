# Reestruturação — Frente 6

## Contexto

CC/ciclos já verdes antes desta leva (`verificar_arquitetura.py`: 0 falhas). F6 = não reabrir dívida + documentar + ub-mode soft.

## ponytail-audit (escopo: mudanças F1–F5)

Load assumida: 1 usuário local (NiceGUI + HTML estático).

### Should fix

1. **`gui/componentes/dashboard.py` KPIs de concursos são proxy** — conta `relatorio.md`, não `painel.kpis` (acima do corte / melhor nota). Funciona como atalho; Resultados tem o número certo. Próximo passo: `aplicacao/` carregar painel leve ou ler campos do `index.html` gerado.
2. **`_gravar_relatorios_por_topico` em `relatorio_html_secoes.py`** — acrescenta I/O na geração do index. Testado indiretamente pelo smoke; vale teste unitário que falha se `tec.html`/`topicos.html` sumirem.
3. **Playwright MCP vs Chromium cache** — F1 usou Playwright API porque MCP pedia `/opt/google/chrome` sem sudo. Manter script `/tmp/map-gui.mjs` fora do repo ou mover para `scripts/` se for repetir auditoria.

### Delete / lean

- Nada a deletar nesta leva além de não versionar `screenshots/` e `mapa-bruto-*.json` (gitignore).

## Simplification (top itens)

| Item | Ação |
|---|---|
| CSS `ca-alvo` | Reforço em `@layer overrides` (já feito F4) — não criar wrapper extra |
| Dashboard HTML | `html_dashboard()` puro — sem template engine novo |
| Título pasta | `titulo_amigavel_da_pasta` — stdlib `re`, sem lib |

## ub-mode (Q16)

| Gate | Esta leva |
|---|---|
| CRAP (CC × cobertura) | Hard via `scripts/verificar_arquitetura.py` (CC≤15 + cobertura) |
| dryer (duplicação) | Soft — pendente instalar dryer no CI |
| mutator | Soft/informativo — não bloqueia merge |

Skill `ub-mode` ainda não instalada no ambiente; próximo passo: copiar SKILL + job CI informativo.

## CC antes/depois (desta leva)

| Métrica | Antes | Depois |
|---|---|---|
| Funções CC>15 (gate) | 0 | 0 |
| Ciclos AST | 0 | 0 |
| `verificar_arquitetura` | verde | verde |

## Gaps frontend fechados parcialmente

- Dashboard 3 fontes: sim (HTML + GUI)
- `topicos.html` / `tec.html`: sim
- TEC `mat`→`ass` no HTML: sim; filtros interativos GUI: backlog
- Bugs F4 shell/touch/path/slug: sim; restantes em `bugs-frontend.md`
