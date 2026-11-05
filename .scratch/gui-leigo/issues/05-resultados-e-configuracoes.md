# 05: Resultados e configurações

**What to build:** relatório em `iframe` (arquivos estáticos de `analises/<candidato>/`) e "Abrir no navegador"; abas de recomendações, prática no TEC e exportação; configurações com os dois limiares, o concurso-alvo, a troca de pasta e a IA opcional.

**Blocked by:** 03

**Status:** done

- [x] Sem relatório, a tela explica como gerar; com relatório, o `iframe` aponta para o `index.html`.
- [x] Recomendações e prática mostram o markdown quando existe e um estado vazio explicado quando não.
- [x] Mudar um limiar grava `[analise]` e vale na análise seguinte.
- [x] A IA começa desmarcada; a chave vai para `llm.guardar_chave`, nunca para TOML.

Notas:

- No modo navegador, a GUI abre a página pelo `abrir_no_navegador` da CLI (`show=False` no `ui.run`), porque o `webbrowser` do NiceGUI não acha o navegador do Windows no WSL. Os componentes do Quasar ficam em português (`language='pt-BR'`).
- "Projeto" saiu do menu: a troca de pasta está em Concursos e em Configurações.
