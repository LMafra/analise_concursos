# Spec: Análise Evolutiva entre Concursos (Fase 2)

Status: `ready-for-agent`

## Problem Statement

O pipeline da fase 1 já corrige cada concurso e mostra onde perco pontos. Ele não responde, porém, à pergunta que mais importa para o meu planejamento de estudos: **estou melhorando ao longo do tempo?** Hoje há três obstáculos.

1. **As notas não são comparáveis entre bancas.**
   - A Cebraspe desconta um ponto por erro em itens Certo/Errado. A FGV não desconta nada em questões de cinco alternativas. Alguns editais ainda dão peso diferente por módulo ou por eixo temático.
   - Comparar o percentual bruto mistura essas regras. Aplicar só a regra do edital também não resolve: um chute puro vale 0% esperado na Cebraspe e 20% na FGV. Nos meus dados, ordenar os concursos pela nota do edital leva as três provas FGV do fim para o topo do ranking por um efeito puramente mecânico.
2. **Não há eixo temporal nem metadados.** As saídas por concurso não têm a data da prova, a ordem cronológica, a escolaridade do cargo nem o modelo de correção do edital.
3. **A amostra é pequena e os nomes não casam.**
   - A mediana é de duas questões por tópico em cada prova. Só 49 de 423 combinações de concurso e tópico têm cinco questões ou mais, e só três tópicos aparecem em três ou mais concursos.
   - As disciplinas têm 53 nomes diferentes em 9 concursos, porque cada edital usa a sua nomenclatura.
   - Banca e tempo se confundem: as provas FGV caíram todas entre outubro e novembro de 2025.

Também quero que a análise seja reproduzível e auditável. Cada número precisa ser rastreável até o trecho do edital que define a regra, e a exploração deve ficar em notebooks que só orquestram código testado.

## Solution

Uma camada de análise cruzada sobre as saídas já existentes, com quatro partes:

1. **Resolução do modelo de correção de cada concurso.**
   - A regra é extraída do texto do edital: penalidade por erro, pesos por faixa de itens, nota máxima, nota de corte e data da prova.
   - Cada resultado guarda o trecho citado, a página e uma confiança.
   - A configuração do concurso pode complementar ou corrigir a extração. Sem nenhuma das duas, vale um default explícito, que gera aviso sempre que o edital parecer mencionar penalidade.
   - Quando um mesmo concurso vale para vários cargos com pesos diferentes (CPNU), cada cargo vira uma variante de correção.
2. **Um consolidado único, com uma linha por questão de todos os concursos.** Ele traz o eixo temporal, os metadados, a disciplina canônica (de uma taxonomia revisável) e o bloco geral ou específico. Fica em cache e é reconstruído automaticamente quando alguma análise muda.
3. **Métricas de evolução em três versões.**
   - **Bruta**, para auditoria.
   - **Corrigida**, pela regra do edital, para nota de corte e meta.
   - **Ajustada ao acaso**, a métrica padrão para comparar concursos entre si.
   - A leitura principal da evolução é o **z-score** de cada disciplina dentro da sua prova, que já leva o n em conta. Toda métrica vem com n, e nenhuma tendência é inferida com menos de três pontos.
4. **Cinco notebooks reproduzíveis**, versionados como scripts. Cada um responde a uma pergunta declarada no topo e fecha com uma conclusão em prosa. Os gráficos são interativos para exploração e estáticos para o relatório.

## User Stories

### Modelo de correção do edital
1. Como candidato, quero que o modelo de correção de cada concurso (bruta, líquida ou ponderada) seja extraído automaticamente do edital, para não transcrever regras de pontuação.
2. Como candidato, quero que o fator de penalidade (quantos acertos cada erro anula) seja lido do edital, para que a nota corrigida reflita a regra real da banca.
3. Como candidato, quero que fatores fracionários (por exemplo, um acerto anulado a cada quatro erros, fator 0,25) sejam suportados, para cobrir editais além dos que já fiz.
4. Como candidato, quero que pesos por módulo, prova ou eixo temático sejam lidos do edital e associados a faixas de itens, para calcular a nota ponderada corretamente.
5. Como candidato, quero que a nota máxima e a nota de corte do conjunto das provas objetivas sejam extraídas quando o edital as definir, para comparar minha nota com a régua oficial.
6. Como candidato, quero que cada regra extraída traga o trecho citado do edital e a página, para auditar a extração contra o PDF.
7. Como candidato, quero que cada extração traga uma confiança entre 0 e 1, para saber quais regras conferir à mão.
8. Como candidato, quero declarar o modelo de correção, o fator, os pesos, a nota máxima e a nota de corte na configuração do concurso, para cobrir editais ilegíveis ou com regra ambígua.
9. Como candidato, quero que a precedência seja edital, depois configuração, depois default (bruta com fator zero), para que a fonte mais confiável prevaleça.
10. Como candidato, quero que toda regra resolvida registre a sua fonte (edital, configuração ou default), para rastrear de onde veio cada número.
11. Como candidato, quero um aviso visível quando a regra cair no default e o texto do edital mencionar penalidade ("ponto negativo", "desconto", "anula acerto"), para que nada seja silenciado.
12. Como candidato, quero um aviso quando a pontuação declarada no concurso contradisser o edital, para corrigir cadastros errados.
13. Como candidato, quero que concursos com várias opções de cargo e pesos diferentes (CPNU) tenham uma variante de correção por cargo em que me inscrevi, para ver minha nota em cada vaga.
14. Como candidato, quero que as notas das variantes do CPNU (95, 95 e 87) batam com o resultado oficial, para confiar na extração dos pesos.
15. Como candidato, quero uma nota normalizada de 0 a 100 por concurso e variante, truncada em zero, para comparar com a meta e com a nota de corte numa escala comum.
16. Como candidato, quero que a nota normalizada siga o edital também nas anuladas (ponto para todos), para que ela possa ser conferida contra o resultado oficial.
17. Como candidato, quero que nenhum CSV existente ganhe ou perca colunas com esta fase, para que relatórios, scripts e testes atuais continuem funcionando.
18. Como candidato, quero que a próxima análise gere o arquivo de correção em todos os concursos já analisados, sem que eu precise forçar o reprocessamento à mão.

### Eixo temporal e metadados
19. Como candidato, quero que a data da prova seja extraída do cronograma do edital, para montar o eixo temporal sem digitar datas.
20. Como candidato, quero declarar a data da prova na configuração do concurso, com prioridade sobre o edital, porque no edital ela é sempre uma "data provável" sujeita a retificação.
21. Como candidato, quero que a ordem cronológica dos concursos seja calculada a partir das datas, para usá-la como eixo X.
22. Como candidato, quero que concursos sem data continuem no consolidado, fora das análises de tendência e com aviso, para nunca ter uma data inventada.
23. Como candidato, quero que banca, cargo, nível (federal, estadual ou municipal) e escolaridade (superior ou médio) estejam no consolidado, para estratificar e filtrar as análises.
24. Como candidato, quero que o concurso de nível médio (`cd_25`) entre marcado e que os achados principais sejam recalculados sem ele, para saber se ele distorce as conclusões.

### Consolidado
25. Como candidato, quero um dataframe único com uma linha por questão de todos os concursos analisados, para derivar qualquer métrica por agregação.
26. Como candidato, quero que o consolidado seja cacheado em parquet e reconstruído quando alguma análise, arquivo de correção ou taxonomia for mais recente que o cache, para não esperar à toa nem ler dados velhos.
27. Como candidato, quero que o consolidado seja validado (colunas, tipos, domínios e número de linhas igual à soma das tabelas de questões), para confiar na base de todas as análises.
28. Como candidato, quero uma taxonomia manual e revisável que mapeie cada nome de disciplina para uma disciplina canônica, para comparar a mesma matéria entre editais com nomes diferentes.
29. Como candidato, quero que a taxonomia indique o bloco (geral ou específico) de cada disciplina canônica, para separar as análises quando a prova é única.
30. Como candidato, quero que, nas provas divididas (conhecimentos gerais ou básicos e específicos), o bloco venha da própria prova, para não depender da taxonomia quando a banca já separa.
31. Como candidato, quero que a quantidade de questões de cada tópico naquela prova esteja disponível, para sempre ponderar percentuais pelo n.

### Métricas de desempenho
32. Como candidato, quero cada métrica em três versões (bruta, corrigida e ajustada ao acaso), para auditar o efeito de cada regra.
33. Como candidato, quero que a versão ajustada ao acaso seja o padrão nas comparações entre concursos, para que provas Certo/Errado e de múltipla escolha fiquem na mesma escala.
34. Como candidato, quero que as anuladas fiquem fora do numerador e do denominador das métricas de desempenho, porque não medem conhecimento.
35. Como candidato, quero que percentuais negativos em disciplinas e tópicos sejam mantidos sem truncar, para que médias e z-scores não fiquem enviesados para cima.
36. Como candidato, quero que todo percentual venha acompanhado do n, para nunca ler 100% de uma questão como domínio do assunto.
37. Como candidato, quero que tópicos com menos de cinco questões sejam marcados como amostra insuficiente, para não tirar conclusões deles.
38. Como candidato, quero o z-score de cada disciplina dentro do seu concurso, calculado sobre a pontuação de cada item e escalado pelo n da disciplina, para ver quanto estou acima ou abaixo da minha média naquela prova, mesmo quando a prova tem poucas disciplinas.
39. Como candidato, quero a evolução de cada disciplina ao longo da ordem cronológica, em percentual ajustado e em z-score, para ver se estou melhorando em cada matéria.
40. Como candidato, quero ver a evolução em uma série única (com a banca como cor) e estratificada por banca, para separar a tendência real do efeito de mudar de banca.
41. Como candidato, quero que tendências só sejam calculadas com três pontos ou mais, com slope, p-value e n, para não ler ruído como evolução.
42. Como candidato, quero conhecimentos gerais e específicos analisados separadamente, porque a distribuição de questões e a dificuldade são muito diferentes.
43. Como candidato, quero saber quantos tópicos do edital foram efetivamente cobrados em cada prova, e que tópicos nunca cobrados fiquem fora da análise de evolução, para não confundir ausência de questões com desempenho.
44. Como candidato, quero a lista de tópicos fracos persistentes, com acertos e erros somados entre concursos (n agregado mínimo de 5, abaixo do limiar em pelo menos dois concursos), para saber o que estudar mesmo com pouca amostra por prova.
45. Como candidato, quero comparar minha nota normalizada com uma meta configurável em cada concurso e variante, para saber a distância até a aprovação.
46. Como candidato, quero a correlação de Spearman entre a ordem cronológica e o z-score médio, com p-value, para ter uma medida única de tendência.
47. Como candidato, quero o ranking dos concursos pelas versões bruta, corrigida e ajustada, lado a lado, com o deslocamento de posições, para expor quando a comparação bruta mente.
48. Como candidato, quero saber se os concursos comparados têm modelos de correção distintos, para ser avisado antes de ler qualquer gráfico de evolução.

### Notebooks e visualizações
49. Como candidato, quero um notebook de carregamento que valide o consolidado e liste os avisos de data e de correção, para começar sabendo se a base está íntegra.
50. Como candidato, quero um notebook de visão geral com o perfil de n por concurso, prova e tópico, e um painel de correção, para entender a base antes das conclusões.
51. Como candidato, quero no painel de correção uma tabela e barras agrupadas de bruto, corrigido e ajustado por concurso, com o modelo e o fator no hover, para ver o efeito de cada regra.
52. Como candidato, quero um aviso visual ("modelos de correção distintos") no topo do notebook de evolução por disciplina quando houver mais de um modelo, para não esquecer o confundidor.
53. Como candidato, quero um gráfico de linha por disciplina com percentual ajustado e z-score ao longo da ordem, com marcas indicando o n, em que pontos com n < 5 aparecem soltos e transparentes, sem linha contínua, para ver tendências sem superestimar amostras pequenas.
54. Como candidato, quero um heatmap de tópicos por concursos, anotado só onde n ≥ 5 e cinza com "n<5" no resto, para ver lacunas e padrões de uma vez.
55. Como candidato, quero um box plot com os pontos sobrepostos da distribuição por disciplina entre concursos, para ver consistência e não só a média.
56. Como candidato, quero barras empilhadas de acertos e erros dos tópicos fracos persistentes, com n anotado, para priorizar a revisão.
57. Como candidato, quero gráficos interativos com hover mostrando n e um filtro por disciplina, para explorar sem escrever código.
58. Como candidato, quero que a linha de evolução, o heatmap e o painel de correção sejam exportados como imagens estáticas para um relatório de evolução em markdown, para ler as conclusões fora do Jupyter.
59. Como candidato, quero um notebook de insights que responda em markdown: em quais disciplinas melhorei de forma significativa (p < 0,05), quais tópicos continuam fracos, qual a correlação entre ordem e z-score médio, e se e em quantas posições o ranking muda entre bruto, corrigido e ajustado, para ter conclusões acionáveis.
60. Como candidato, quero que cada notebook abra com a pergunta que responde e feche com uma conclusão em prosa, para ler só o essencial.
61. Como candidato, quero que tabelas longas apareçam resumidas nas células, para que os notebooks fiquem legíveis.
62. Como desenvolvedor, quero que os notebooks não contenham parsing, OCR, regra de negócio nem cálculo de correção, só chamadas ao pacote e plots, para que toda lógica seja testada e reaproveitável.
63. Como desenvolvedor, quero os notebooks versionados como scripts no formato percent, com diffs legíveis, e os arquivos de notebook gerados fora do versionamento, para revisar mudanças como código.
64. Como desenvolvedor, quero um script que converta e execute todos os notebooks do zero, em ordem, falhando se algum quebrar, para garantir reprodutibilidade e preparar a execução em CI.

### Documentação
65. Como desenvolvedor, quero o modelo de domínio estendido com os campos novos, o arquivo de correção, o schema do consolidado e as fórmulas das métricas, para entender o que cada coluna significa.
66. Como candidato, quero uma seção "Análise evolutiva" no README explicando o que cada notebook responde e como rodar, para usar a análise sem ler código.
67. Como desenvolvedor, quero um documento de convenções para agentes (notebooks, métrica padrão, sempre mostrar n, onde mora cada lógica), para que sessões futuras sigam as mesmas regras.

## Implementation Decisions

### Decisões de análise (fechadas no grilling)
- **Métrica de nível entre concursos:** é o ajuste ao acaso, em que cada item vale +1 no acerto, \(-1/(k-1)\) no erro e 0 em branco, com k = 2 em Certo/Errado e k = 5 em múltipla escolha A–E.
  - Em Certo/Errado, coincide exatamente com a regra Cebraspe.
  - A métrica "corrigida" (regra do edital) é usada para nota de corte, meta e auditoria. A "bruta" (só acertos) é legado e auditoria.
  - A leitura principal da evolução é o z-score.
- **z-score:** \(z_d = (\bar s_d - \bar s_g)/(\sigma_g/\sqrt{n_d})\), onde \(s\) é a pontuação de cada item na versão escolhida, \(g\) é o conjunto de itens não anulados do concurso e \(d\) os itens da disciplina. Essa forma leva o n em conta e é estável com poucas disciplinas por prova. Dentro de uma prova sem brancos, ela não muda com transformações afins da pontuação, então bruta e ajustada dão o mesmo z na FGV.
- **Anuladas:** saem do numerador e do denominador de todas as métricas de desempenho. A única exceção é a nota normalizada, que segue o edital (ponto para todos).
- **Truncamento:** só a nota normalizada é truncada em 0. Percentuais de disciplina e tópico podem ser negativos.
- **Evolução:** há duas leituras, uma série cronológica única (banca como cor) e uma série estratificada por banca. Tendência só com três pontos ou mais.
- **Escopo:** os 9 concursos analisados. O `cd_25` entra com escolaridade "médio", e o notebook de insights mostra a sensibilidade sem ele.
- **Identidade de disciplina:** vem da taxonomia manual. A identidade de tópico é a disciplina canônica mais as palavras-chave normalizadas do nome do tópico, reaproveitando a normalização já usada no comparativo da fase 1.
- **Sem LLM:** a extração usa só regex. A precedência é edital, depois configuração, depois default.
- **Data da prova:** a precedência é configuração (data confirmada) e depois edital (data provável). Sem data, a ordem fica vazia e o concurso sai das tendências, sem imputação.

### Configuração do concurso (extensão do schema)
- Campos opcionais novos: data da prova (ISO 8601), nível, escolaridade e um bloco de correção com:
  - modelo;
  - fator de penalidade;
  - nota máxima;
  - nota de corte;
  - pesos como lista de faixas de itens com peso, no mesmo formato já usado pelos pesos do resultado oficial;
  - variantes nomeadas (por exemplo, por código de cargo), cada uma com os seus pesos.
- Nenhum campo existente muda de significado. A pontuação já existente (simples ou Cebraspe) continua alimentando a nota líquida legada.

### Módulos
O código novo vive num subpacote de análise dentro do pacote existente, para não alterar o empacotamento e evitar confusão com o módulo de correção por questão da fase 1.

- **Correção (análise).** Tipo `ConfiguracaoCorrecao`, com:
  - modelo (`bruta | liquida | ponderada`; é `liquida` sempre que o fator for maior que zero, mesmo com pesos);
  - fator de penalidade;
  - pesos por faixa de itens;
  - nota máxima e nota de corte;
  - fonte (`edital | config | default`);
  - confiança, trecho de origem, documento de origem, página de origem, variante e data da prova.

  O documento de origem é necessário porque a regra pode estar num anexo (no CPNU, o quadro de pesos fica no anexo do bloco), e a página sozinha não identifica o PDF.

  Interfaces:
  - `extrair_fator_correcao(paginas) -> ConfiguracaoCorrecao`: localiza as seções de critérios de avaliação, prova objetiva, pontuação e correção, e aplica padrões por família de redação:
    - penalidade explícita ("X ponto negativo … discordância");
    - nota igual ao total de acertos, ou "valendo 1 ponto cada questão" sem menção a desconto;
    - pontos diferentes por prova ou módulo;
    - quadro de pesos por eixo e cargo;
    - penalidade fracionária ("a cada N erradas…").
  - `extrair_data_prova(paginas)`: cronograma com "Aplicação das provas objetivas … d/m/aaaa" e texto corrido com "dia dd de mês de aaaa".
  - `resolver_correcao(config, paginas) -> lista de ConfiguracaoCorrecao`: devolve uma configuração por variante, aplica a precedência e emite os avisos de default com menção a penalidade e de contradição com a pontuação declarada.
    - Recebe as páginas por documento, na mesma ordem já usada para o edital (anexos primeiro, depois o edital principal).
    - O aviso de menção a penalidade usa só expressões específicas: "ponto negativo", "desconto de", "descontado" e "anula um acerto" (e variações de número). Palavras soltas como "anulação", "anulada" ou "descontos" não contam, porque aparecem em todos os editais (anulação de questão, de inscrição ou de nomeação) e em trechos sobre salário ("descontos legais", no TCU).
    - Quando nem o edital nem a configuração definem a nota máxima, ela é a soma dos pesos dos itens do concurso, ou seja, o número de itens quando não há pesos. Nem todo edital declara a nota máxima: o agsus declara ("totalizará 70 pontos"), mas a regra da Cebraspe e a do cprm não.
  - `aplicar_correcao(questoes, cfg) -> NotaCorrigida`: pontuação de cada item nas três versões, a partir do formato da prova e do peso.
  - `nota_normalizada(nota, nota_maxima) -> float`: escala de 0 a 100, truncada em 0.
- **Pipeline (retrofit cirúrgico).**
  - Ao fim da análise de um concurso, o pipeline resolve a correção a partir do texto do edital e dos anexos, extraído sem OCR, e grava um arquivo de correção (JSON) na pasta de análise do concurso.
  - O texto de cada documento é lido uma única vez e serve tanto para estruturar o conteúdo programático quanto para resolver a correção. A extração do PDF é a etapa mais lenta da leitura do edital, e lê-lo de novo só para a correção dobraria esse tempo.
  - Com edital manual, a correção continua sendo extraída dos PDFs declarados, se houver. Sem nenhum PDF, ela sai da configuração ou do default.
  - A versão da análise no manifesto é incrementada para que todos os concursos regenerem esse arquivo na próxima execução.
  - Nenhum CSV muda.
- **Consolidado (análise).**
  - `construir_consolidado` junta as tabelas de questões de todos os concursos (acrescentando o nome do concurso), o arquivo de correção, os metadados da configuração e a taxonomia. Deriva o bloco e a ordem cronológica.
  - `carregar_consolidado` lê o cache em parquet ou o reconstrói quando alguma tabela de análise, arquivo de correção ou a taxonomia for mais novo que o cache (comparação por mtime).
  - `validar_schema` é escrito à mão, sem dependência nova.
  - A quantidade de questões do tópico é exposta como apelido do total já existente, e não como coluna duplicada.
- **Evolução (análise, funções puras).** Todas recebem o consolidado. As que comparam níveis aceitam `usar` (`bruta | corrigida | ajustada`, padrão `ajustada`). As temporais aceitam `estrato` (nenhum ou `banca`).
  - `percentual_por_disciplina_ao_longo_do_tempo`: concurso, ordem, disciplina, bloco, as três versões do percentual, nota normalizada, n, modelo de correção e fator.
  - `zscore_por_disciplina`
  - `evolucao_por_topico(min_n=5)`: slope via `scipy.stats.linregress`, com p-value e n, só com três pontos ou mais.
  - `topicos_fracos_persistentes(limiar=0.6, min_concursos=2)`: contagens somadas entre concursos.
  - `comparar_com_meta(meta=0.7)`: compara a meta com a nota normalizada, por concurso e variante.
  - `correlacao_tempo_zscore`: Spearman com p-value.
  - `comparar_bruto_vs_corrigido`: rankings pelas três versões e o deslocamento de posições.
  - `cobertura_edital`: tópicos do edital estruturado efetivamente cobrados.
  - `modelos_distintos`: alimenta o aviso do notebook de evolução.
- **Visualização (análise).** Uma função por gráfico, cada uma recebendo um DataFrame já calculado:
  - linha de evolução;
  - heatmap tópico por concurso;
  - box com os pontos sobrepostos;
  - barras empilhadas de tópicos fracos;
  - painel de correção.

  Plotly cuida da interatividade. Matplotlib exporta só a linha, o heatmap e o painel para o relatório de evolução, na pasta do consolidado. Há também um helper de resumo de tabelas (os N primeiros e as contagens) para as células.
- **Notebooks.**
  - Os cinco são: carregamento e validação, visão geral com o painel de correção, evolução por disciplina, evolução por tópico e insights.
  - Ficam versionados como scripts jupytext (formato percent), e os arquivos de notebook gerados não são versionados.
  - O script de execução converte e executa em ordem (nbconvert ou papermill).
  - As dependências de análise (pyarrow, scipy, plotly, jupyter, jupytext, papermill, nbconvert, ipykernel) ficam num grupo opcional do projeto.

### Contratos de saída
- **Arquivo de correção por concurso:** lista de configurações (uma por variante) com todos os campos de `ConfiguracaoCorrecao`.
- **Consolidado em parquet**, com uma linha por questão. Colunas:
  - concurso, prova, questão, disciplina bruta e canônica, bloco, tópico, gabarito, anulada, resposta e resultado;
  - formato, banca, cargo, nível, escolaridade, data da prova e ordem;
  - modelo de correção, fator de penalidade, nota máxima, nota de corte, fonte da correção, confiança da extração e peso de cada variante;
  - a pontuação de cada item nas três versões.
- **Relatório de evolução em markdown** com as três imagens estáticas, na pasta do consolidado.

### Pesos do CPNU (dados do anexo do Bloco 3, quadro de pesos)
- A ordem dos pesos é eixo 1, 2, 3, 4 e 5:
  - B3-08-A (Analista do Seguro Social, TI): 1, 1, 2, 4, 2;
  - B3-10-A (Analista I, TI): 1, 2, 3, 3, 1;
  - B3-07-C (Tecnologista): 1, 2, 1, 4, 2.
- Conhecimentos gerais têm peso 1 (itens 1–30). Cada eixo tem 12 itens consecutivos (31–42, 43–54, 55–66, 67–78, 79–90), o que deve ser confirmado contra as faixas de eixo do caderno.
- Com 16 acertos nos gerais e 8, 3, 11, 9 e 5 nos eixos, as notas oficiais são 95, 95 e 87.

## Testing Decisions

- **O que é um bom teste:** valida comportamento observável (arquivos gerados, valores de métricas, avisos emitidos e mensagens) e nunca detalhes internos. Fixtures pequenas e determinísticas. Dados reais só como trechos curtos de texto dos editais.
- **Seam 1, a CLI de análise ponta a ponta (existente).** Os testes rodam a análise sobre pastas temporárias com concursos sintéticos, usando os helpers já existentes para criar concursos, analisar e ler CSVs. Verificam:
  - o arquivo de correção é gravado com a fonte certa (edital, configuração ou default);
  - os CSVs existentes mantêm exatamente as mesmas colunas;
  - a mudança de versão no manifesto provoca a regeneração;
  - os campos novos opcionais da configuração são aceitos e validados.
- **Seam 2, do texto do edital à configuração de correção (novo, puro).** Usa trechos reais curtos (Cebraspe, FGV agsus e cprm, quadro do CPNU, pesos por prova do creci e do dataprev) e textos sintéticos. Casos obrigatórios:
  - edital sem menção, que dá default com aviso;
  - default com o texto mencionando penalidade, que dá aviso;
  - fator 1,0;
  - fator fracionário 0,25;
  - pesos por faixa de itens;
  - variantes por cargo;
  - precedência edital, configuração, default;
  - contradição com a pontuação declarada;
  - data da prova nos dois formatos e com precedência da configuração.

  Sempre que a fonte for o edital, o trecho de origem deve vir preenchido.
- **Seam 3, a API de análise sobre um DataFrame por questão (novo, puro).** Uma factory de teste monta consolidados mínimos. Casos:
  - teste paramétrico: com penalidade, corrigido difere do bruto em pelo menos uma questão com erro; sem penalidade, os dois coincidem;
  - nota negativa truncada só na nota normalizada;
  - anuladas fora das métricas;
  - aceitação do CPNU: 95, 95 e 87;
  - todas as funções de evolução com n < 5, com um único concurso, com tópico sem gabarito, com correção líquida comparada à bruta, com geral e específico separados e com estratificação por banca;
  - tendência ausente com menos de três pontos;
  - reconstrução do cache por mtime;
  - validação de schema e contagem de linhas.
- **Notebooks:** só teste de fumaça, com o script que executa todos do zero sem erro. Isso faz parte da verificação final, não da suíte unitária.
- **Verificação com dados reais (manual, ao final):**
  - todos os concursos analisados têm modelo e fonte de correção resolvidos;
  - o parquet tem tantas linhas quanto a soma das tabelas de questões;
  - as datas extraídas batem com a tabela das Further Notes;
  - o ranking por ajuste ao acaso reproduz os valores aproximados abaixo.
- **Prior art:** os testes da fase 1 de CLI ponta a ponta (fixtures em pasta temporária e helper de análise), de parsers sobre trechos de texto (edital, gabarito, resultado oficial) e de validação contra o resultado oficial.
- **Desenvolvimento:** TDD para o módulo de correção e o módulo de evolução. O critério de pronto é a suíte verde, o ruff limpo e todos os notebooks executando do zero.

## Out of Scope

- Cadastrar `creci`, `dataprev_2024` e `senappen`, que ainda não têm respostas, e, no caso dos dois últimos, nem configuração.
- Corrigir a banca do `creci`: está como Quadrix, mas o edital é do Instituto IBEST.
- Fallback por LLM na extração do modelo de correção.
- Workflow de CI. Só o script de execução dos notebooks é entregue.
- Gráfico radar, violin, linha de evolução por tópico, bandas de confiança e projeções.
- Normalização por desempenho de outros candidatos (média ou desvio da banca). A nota é sempre a minha, pela regra do edital ou pelo ajuste ao acaso.
- Provas discursivas, redação e títulos.
- Alterações nos relatórios por concurso e no comparativo consolidado da fase 1.

## Further Notes

- **Modelo de correção por edital** (páginas do PDF; "fonte" é a fonte esperada após a resolução):
  - **Cebraspe** (tcu_25, telebras, infrasa, cd_25, funpresp_jud, pf_perito): seção 8.11.2, "1,00 ponto, caso a resposta do candidato esteja em concordância com o gabarito oficial definitivo das provas; 1,00 ponto negativo, caso a resposta do candidato esteja em discordância com o gabarito oficial definitivo das provas; 0,00 ponto, caso não haja marcação ou haja marcação dupla (C e E)". Modelo líquido, fator 1,0, sem pesos (o TCU confirma no 8.11.6 que a nota final é a soma de P1 e P2). Páginas: tcu_25 p.29, telebras p.41, infrasa p.30, cd_25 p.28, funpresp_jud p.35 e pf_perito p.28–29.
  - **Notas de corte do conjunto (Cebraspe):** tcu_25 60, telebras 36, infrasa 30, cd_25 54, funpresp_jud 36 e pf_perito 48.
  - **agsus (FGV):** p.14, seção 9.5, "A Prova Objetiva totalizará 70 (setenta) pontos […] valendo 1 (um) ponto cada questão". Modelo bruto. O corte é por bloco (seção 9.14), e não há nota de corte do conjunto.
  - **cprm (FGV):** seção 12.15, "Nota da Prova Objetiva (NPO) igual ao total de acertos". Modelo bruto. O corte é por módulo (seção 12.13).
  - **cpnu (FGV):** p.29, seções 8.9.1 a 8.9.4, com eixos de peso 1 a 5 que variam por cargo e nota máxima de 150. O quadro de pesos está no anexo, p.91–92. Modelo ponderado, com três variantes.
  - **Fora do pipeline:** creci (IBEST) dá 1 ponto por item em P1 e 2 em P2, sem desconto, máximo 60. dataprev_2024 (FGV) dá 1 ponto nas gerais e 2,5 nas específicas, máximo 115, corte 57,5. senappen (Selecon) dá 1 ponto nas gerais e 2 nas específicas, máximo 100, e é para cargo de Direito.
- **Falsos positivos de palavras-chave (verificados no texto real):** "anulação"/"anulada" aparecem em todos os editais (seção de recursos, eliminação, nulidade da nomeação). "Descontos legais" aparece no edital do TCU, na seção do programa de formação. Nenhum dos dois indica penalidade por erro.
- **Leituras de "fator de correção" nesta base:**
  - Penalidade aparece só na Cebraspe.
  - Anulação aparece em todos os editais como "ponto atribuído a todos".
  - Nenhum edital normaliza a prova objetiva.
  - O fator é sempre o mesmo para gerais e específicas; o que muda entre elas é o peso.
- **Datas esperadas e ordem:**
  1. pf_perito, 27/07/2025
  2. cpnu, 05/10/2025
  3. agsus, 12/10/2025
  4. cprm, 30/11/2025
  5. telebras, 08/02/2026
  6. tcu_25, 22/02/2026
  7. cd_25, 08/03/2026
  8. infrasa, 15/03/2026
  9. funpresp_jud, 05/07/2026
- **Percentuais aproximados por concurso** (bruto / regra do edital / ajustado ao acaso; anuladas contadas como acerto):

  | concurso | bruto | regra do edital | ajustado ao acaso |
  |---|---|---|---|
  | agsus | 55,7 | 55,7 | 44,6 |
  | cpnu | 57,8 | depende da variante | 47,2 |
  | cprm | 41,4 | 41,4 | 26,8 |
  | tcu_25 | 72,5 | 45,0 | 45,0 |
  | telebras | 70,0 | 40,0 | 40,0 |
  | infrasa | 70,0 | 40,0 | 40,0 |
  | pf_perito | 66,7 | 33,3 | 33,3 |
  | cd_25 | 61,1 | 22,2 | 22,2 |
  | funpresp_jud | 57,5 | 15,0 | 15,0 |

  Pela regra do edital, as provas FGV sobem do fim para o topo. Pelo ajuste ao acaso, as escalas se aproximam.
- **Esparsidade:** a mediana é de 2 questões por tópico e prova. Só 49 de 423 linhas de tópico têm n ≥ 5. Há 53 nomes de disciplina, dos quais só 5 aparecem em três ou mais concursos sem taxonomia. Nenhuma prova real tem itens em branco.
- **Resumo de tabelas:** a skill `caveman-compress`, citada no pedido original, comprime arquivos de memória e não se aplica a saídas de células. Por isso o resumo de tabelas é feito por um helper do pacote.
- Não há issue tracker configurado, então esta spec fica no repositório, como a da fase 1. O plano de execução complementa esta spec. A ordem é: modelo de domínio, retrofit, correção, consolidado, evolução, visualização, notebooks, verificação e documentação.
