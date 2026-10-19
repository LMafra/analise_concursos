# 02: Correção Certo/Errado no padrão Cebraspe, anuladas e brancos

**What to build:** concursos com formato Certo/Errado e pontuação Cebraspe passam a ser corrigidos com nota líquida (erro anula acerto, branco vale zero). Em qualquer formato, questões anuladas contam como acerto, ficam sinalizadas e saem do percentual de mérito. As saídas passam a incluir brancos, anuladas e nota líquida, e a verificação de fechamento dos totais passa a ser obrigatória.

**Blocked by:** 01

**Status:** done

- [x] Um concurso sintético C/E com `respostas.txt` produz a nota líquida correta.
- [x] As anuladas aparecem como acerto sinalizado e ficam fora do percentual de mérito.
- [x] As saídas de desempenho incluem `em_branco, anuladas, nota_liquida`.
- [x] Por prova, `acertos + erros + em_branco == total` e o total é igual ao tamanho da faixa. Se não fechar, a análise falha com mensagem clara.
- [x] Testes ponta a ponta cobrem as regras simples e Cebraspe.
