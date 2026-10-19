# 07: Comando adicionar (detecção e assistente)

**What to build:** o usuário copia arquivos com nomes livres para uma pasta nova e roda `concursos adicionar <pasta>`. O assistente:
- classifica cada arquivo pelo conteúdo (edital, prova, gabarito, folha, respostas, resultado oficial);
- detecta a banca, o formato, a pontuação, as faixas de itens e o status do gabarito;
- oferece as seções de cargo/tipo do gabarito para escolha;
- aponta duplicados (por hash), preliminar e definitivo juntos (prefere o definitivo) e arquivos não reconhecidos, perguntando em vez de decidir;
- ignora automaticamente metadados do Windows e arquivos compactados;
- mostra um resumo, pede confirmação e grava o `concurso.yaml`.

Rodar de novo mostra o diff e pede confirmação. O modo `--aceitar-sugestoes` roda sem perguntas e falha se algo for ambíguo.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] A detecção de papel, banca e status é testada com cabeçalhos reais anonimizados de cada tipo de arquivo.
- [ ] O assistente é testado com entrada e saída simuladas: caminho feliz, duplicado, dois gabaritos, arquivo desconhecido e recadastro com diff.
- [ ] O YAML gerado passa na validação do ticket 05 e é aceito pelo `analisar`.
- [ ] O modo não interativo falha com mensagem clara diante de ambiguidade.
