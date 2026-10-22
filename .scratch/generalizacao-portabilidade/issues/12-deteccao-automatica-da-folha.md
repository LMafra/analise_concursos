# 12: Detecção automática da folha

**What to build:** uma folha fora dos perfis de OCR é lida por detecção automática da grade: contornos, retificação e agrupamento em linhas e colunas.

A confiança de cada questão é a diferença entre os dois maiores preenchimentos. Abaixo do limiar, a questão fica com `revisar=true` no CSV.

**Blocked by:** 07

**Status:** done

- [x] Uma folha sintética sem perfil, com rotação leve, é lida corretamente.
- [x] Uma questão com duas bolhas de preenchimento parecido sai com confiança baixa e `revisar=true`.
- [x] Uma grade que não for detectada gera mensagem com `dica:` que aponta o CSV manual. A análise dos outros concursos não é interrompida.
- [x] A imagem de depuração continua sendo gravada.
