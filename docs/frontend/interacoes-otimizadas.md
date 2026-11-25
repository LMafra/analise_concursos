# Interações otimizadas — Frente 3

DS manda: `docs/marca-gabarito-vivo.md` + `src/concursos/gui/tema.py`.  
Mobbin: autenticado mas **plano pago exigido** — indisponível nesta corrida (Q8).

## Antes → depois (atividades)

| Atividade | Interações antes | Interações depois | O que muda | Ref |
|---|---:|---:|---|---|
| Ver KPIs de desempenho | ~7 (abrir Resultados + scroll + Estudar + TEC) | 1 clique no KPI na home | Dashboard 3 fontes no topo de `/` | DS + F5 |
| Analisar provas | 2–3 (lista → Analisar → Resultados) | 2 (Analisar → Resultados); atalho KPI “última análise” | Sem remoção | DS |
| Digitar respostas | N×5 cliques em alvos 17px | N×5 em alvos ≥44px; colunas empilhadas no mobile | BUG-01 | DS `ALVO_MINIMO` |
| Navegar no mobile | drawer permanente + conteúdo estreito | hamburger; drawer fechado &lt;1024px | BUG-02 | Quasar `show-if-above` |
| Importar TEC | 4–6 | 3–4 (CTA na home TEC + empty KPI) | Atalho no sub-dashboard TEC | F5 |
| Ver tópicos fracos | scroll longo no `index.html` | 1 clique → `topicos.html` / aba | Relatório por tópico | F5 |
| Prática TEC por assunto | abrir MD/CSV, caçar `cad` | lista `mat`→`ass` + filtros `tipo`/`banca` + `url` | `cad` filtro opcional | F5 / contrato TEC |
| Configurar | 4+ | 4 (mesmos controles, alvos 44px) | Só DS | BUG-03/10 |

Regra: atalho ≠ remoção.

## Wireframe — Home `/` (após F5)

```
[ header: menu | marca | busca | pasta abreviada ]
[ drawer: só ≥1024px permanente ]

┌─ Dashboard ─────────────────────────────────────┐
│ Concursos │ TEC prática │ Simulados             │  ← 1 col mobile / 3 desktop
│ KPI×≤3    │ KPI×≤3      │ KPI×≤3                │
│ (empty+CTA por fonte sem dado)                  │
│ cada KPI → âncora/rota (Resultados / TEC / Sim) │
└─────────────────────────────────────────────────┘
[ abas: Minhas provas | Importar do TEC ]
[ lista de provas … ]
[ + Novo | Analisar ]
```

## Wireframe — Estudar > TEC

```
Filtros: [tipo▾] [banca▾] [caderno▾ opcional]
Agrupadores: mat → ass (expansível)
Linha questão: resultado-selo | enunciado curto | [abrir no TEC url]
```

## Wireframe — `index.html` 1ª dobra

Igual composição do dashboard GUI; links âncora (sem CTAs de app); `@media print` ok.

## Decisões de layout (DS)

- Tokens só via `tema.py` / `design_tokens.py`.
- Selos: ícone + texto + ARIA (nunca só cor).
- Alvos: `.ca-alvo` com min 44×44 **efetivo** (CSS precisa vencer Quasar dense).
- Empty: frase + CTA único por sub-dashboard.
