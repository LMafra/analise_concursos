# 13: Troca de gabarito preliminar para definitivo

**What to build:** o usuário analisa com o gabarito preliminar (o relatório mostra o selo "Gabarito preliminar (provisório)"). Depois, coloca o definitivo na pasta, ou sobrescreve o arquivo com o mesmo nome, e roda `analisar`. Antes de processar, a análise varre a pasta em busca de arquivos não cadastrados.

Se encontrar um gabarito definitivo que casa com a seção configurada (mesma banca, cargo/tipo e faixa de itens), ela:
- atualiza o `concurso.yaml`;
- move o preliminar para `ignorar`;
- registra o evento em `historico`;
- copia as saídas atuais para o histórico da análise;
- gera `diff_gabarito.csv` (questões alteradas e anuladas, resposta do candidato, acerto antes e depois);
- reprocessa o concurso;
- adiciona ao relatório a seção "Preliminar → Definitivo", com o impacto em acertos e nota líquida.

Em qualquer outro caso (não casa, dois candidatos, arquivo desconhecido), o concurso fica desatualizado, com instrução para rodar `adicionar`.

**Blocked by:** 06, 07

**Status:** ready-for-agent

- [ ] Teste ponta a ponta: um concurso sintético com preliminar recebe o definitivo, e o teste verifica YAML, snapshot, diff, reprocessamento e seção do relatório.
- [ ] Teste: sobrescrever com o mesmo nome e status novo dispara o mesmo fluxo.
- [ ] Teste: gabarito definitivo de outro cargo deixa o concurso desatualizado, sem troca.
- [ ] Teste: dois definitivos candidatos deixam o concurso desatualizado.
