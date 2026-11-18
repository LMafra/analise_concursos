# Checklist de aceite — Gabarito Vivo (§8 + roteiro §7)

Marque no PR de release. Critérios derivados de `docs/decisoes-ux-gabarito-vivo.md` e do diagnóstico.

## §8 — Design system / produto

- [ ] Tokens em `:root` (CSS do relatório e `tema.py`); nenhum hex solto no corpo do HTML gerado
- [ ] Tema claro / escuro / automático (segmented) na Configuração
- [ ] `@media print` com fundo `#FAFAFA` e texto legível
- [ ] Sidebar com exatamente 4 itens: Minhas Provas, Resultados, Estudar, Concursos
- [ ] Home recorrente = Minhas Provas (sem “Dashboard Geral”)
- [ ] Relatório: primeira dobra com diagnóstico → ≤3 cards → “O que fazer agora”; top-N fracos; 1 gráfico principal
- [ ] Banner de status da última prova (selo + título + margem para o corte) e medidor de corte no card de nota
- [ ] Drawer com marca gráfica + tagline “diagnóstico pós-prova” (sem tema na sidebar)
- [ ] Resultados: seletor de concurso analisado (visão geral × `relatorio.html`)
- [ ] Selos com texto + ícone (não só cor); contraste AA nos tokens; nenhum “KPI” / percentil / posição estimada
- [ ] Alvos ≥44×44 (`ca-alvo`); `prefers-reduced-motion` respeitado
- [ ] On-blur nos campos de data do Conferir; sticky “Salvar alterações”
- [ ] Undo toast ao deixar de acompanhar concurso (PCI)
- [ ] Falha parcial de importação: banner no bloco + ≤1 toast consolidado
- [ ] Dirty nav: “Continuar editando” ao descartar com alterações
- [ ] Breadcrumb + ← Voltar em Conferir
- [ ] Nome de produto **Gabarito Vivo** na janela, Sobre e rodapé do relatório
- [ ] CLI `gabarito-vivo`; alias `concurso-analise` com aviso de deprecation
- [ ] Pacote Python `concursos` e pasta `.concurso/` inalterados

## §7 — Roteiro de QA manual (think-aloud)

Cinco tarefas; anotar tempo até primeira ação e cliques até o tópico fraco:

1. Abrir o app e achar o diagnóstico da última prova (&lt;5 s até a primeira ação útil).
2. A partir do relatório, escolher o que estudar na semana (≤2 cliques até um tópico fraco).
3. Conferir uma lacuna do edital e salvar.
4. Explicar a tendência da nota (frase leiga, sem jargão de z-score na dobra).
5. Montar ou abrir um treino a partir do relatório (simulado / prática / TEC).

Métricas-alvo: SEDQ ≥ 6. Sem telemetria.

## Dívidas mínimas aceitas nesta leva

- Cancel cooperativo no pipeline (matar etapas) — não bloqueia aceite.
- Área de foco modelada — fora até `modelo.md` + migração.
- Busca full-text global — chips de filtro bastam.
- Tipografia display / motion fino / visual-regression NiceGUI — fora.

## Asserts automatizados

Rodar: `uv run pytest tests/test_produto_gabarito_vivo.py tests/test_tema_contraste.py tests/test_relatorio_painel.py -q`
