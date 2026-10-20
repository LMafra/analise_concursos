# 15: README, assistente bash e documento do modelo

**What to build:** um usuário novo segue o README e adiciona um concurso do zero. O assistente bash interativo cria a pasta, orienta a cópia dos arquivos (incluindo o formato do `respostas.txt` e a troca de gabarito) e chama `adicionar` e depois `analisar`. O documento do modelo descreve as entidades do domínio: Concurso, Prova, Questão, Disciplina/Tópico, Gabarito com status, RespostaMarcada, Resultado e EventoHistórico.

**Blocked by:** 07, 14

**Status:** done

- [x] O README cobre instalação (uv, Tesseract opcional), o fluxo coletar, cadastrar e analisar, o formato do `respostas.txt`, a revisão de tópicos, a troca de gabarito e o comando `status`.
- [x] O assistente bash executa o fluxo completo num concurso sintético (verificação manual registrada).
- [x] O documento do modelo está alinhado com o schema do `concurso.yaml` e com os contratos de saída.

## Verificação manual do assistente

`scripts/novo_concurso.sh` (biblioteca do template da skill wizard + 7 etapas) executado num concurso sintético FGV (gabarito.txt definitivo + respostas.txt), com `PROVAS_DIR`/`ANALISES_DIR` em /tmp e respostas digitadas com pausas:

1. pré-requisitos (uv encontrado, Tesseract opcional, `uv sync` recusado);
2. pasta `sintetico_wizard`;
3. cópia dos arquivos (listagem confere);
4. respostas.txt (instruções de formato);
5. `adicionar` detectou gabarito (fgv, definitivo) e respostas e gravou o concurso.yaml;
6. `analisar --concurso` gerou as saídas e o consolidado, e o `status` mostrou "completo";
7. próximos passos.

Observação: com toda a entrada num pipe de uma vez, o `input()` do Python consome as respostas seguintes; num terminal isso não ocorre.
