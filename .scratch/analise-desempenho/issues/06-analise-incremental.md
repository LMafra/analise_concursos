# 06: Análise incremental

**What to build:** rodar `concursos analisar` de novo só reprocessa os concursos cujos arquivos de entrada, `concurso.yaml` ou revisão manual mudaram, com base num manifesto de hashes por concurso. `--forcar` reprocessa tudo e `--concurso X` processa só um. O consolidado é sempre refeito.

**Blocked by:** 01

**Status:** done

- [x] A segunda execução sem mudanças não reprocessa nenhum concurso, e o log informa isso.
- [x] Alterar um arquivo, o YAML ou a revisão reprocessa só o concurso afetado.
- [x] `--forcar` e `--concurso` funcionam (testes ponta a ponta).
- [x] Falha no meio do processamento não deixa o manifesto marcando o concurso como atualizado.
