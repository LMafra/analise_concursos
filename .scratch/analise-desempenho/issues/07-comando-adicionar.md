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

**Status:** done

- [x] A detecção de papel, banca e status é testada com cabeçalhos reais anonimizados de cada tipo de arquivo.
- [x] O assistente é testado com entrada e saída simuladas: caminho feliz, duplicado, dois gabaritos, arquivo desconhecido e recadastro com diff.
- [x] O YAML gerado passa na validação do ticket 05 e é aceito pelo `analisar`.
- [x] O modo não interativo falha com mensagem clara diante de ambiguidade.

## Verificação manual (cópia de `provas/` em /tmp)

| Concurso | `--aceitar-sugestoes` | Observação |
|---|---|---|
| cd_25, funpresp_jud, infrasa, pf_perito, tcu_25, telebras | ok | provas cg/cb + ce, cadernos pareados, folha `cebraspe_ce` |
| agsus | ok | seção e caderno tipo 1 sugeridos pelo caderno |
| cpnu | ok | Bloco 3 tipo 2, caderno b3302, anexo do edital, template `fgv_cpnu_90` |
| creci | pergunta a banca | interativo: quadrix, definitivo sugerido, caderno 101 pelo cargo |
| cprm, dataprev_2024, senappen | pergunta cargo/tipo | pasta tem cadernos de vários tipos |
