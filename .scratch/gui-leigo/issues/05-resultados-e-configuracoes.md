# 05: Resultados e configurações

**What to build:** relatório em `iframe` (arquivos estáticos de `analises/<candidato>/`) e "Abrir no navegador"; abas de recomendações, prática no TEC e exportação; configurações com os dois limiares, o concurso-alvo, a troca de pasta e a IA opcional.

**Blocked by:** 03

**Status:** todo

- [ ] Sem relatório, a tela explica como gerar; com relatório, o `iframe` aponta para o `index.html`.
- [ ] Recomendações e prática mostram o markdown quando existe e um estado vazio explicado quando não.
- [ ] Mudar um limiar grava `[analise]` e vale na análise seguinte.
- [ ] A IA começa desmarcada; a chave vai para `llm.guardar_chave`, nunca para TOML.
