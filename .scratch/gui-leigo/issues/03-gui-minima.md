# 03: GUI mínima que analisa

**What to build:** extra `[gui]`, `concurso-analise gui` e `concurso-analise-gui`, `gui/app.py` (só `127.0.0.1`, janela nativa fora do Linux), escolha do projeto com `chdir` e `[gui] ultimo_projeto`, tela de concursos (status), Analisar com barra e log, tela Sobre.

**Blocked by:** 01

**Status:** done

- [x] `executar` sempre passa `host='127.0.0.1'` e `reload=False`.
- [x] Sem o extra, `concurso-analise gui` sai com código 1 e a dica de instalação.
- [x] Analisar pela GUI chama `aplicacao.analise.analisar`; a barra avança a cada `ao_progresso`; o painel recebe o log.
- [x] Sobre mostra a versão e o caminho do log.
- [x] Testes com a fixture `user`, com a camada de aplicação falsa.
