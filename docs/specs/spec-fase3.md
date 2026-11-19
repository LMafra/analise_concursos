# Spec: Edital como Fonte de Verdade e Descoberta Dirigida (Fase 3)

Status: `ready-for-agent`

## Problem Statement

As fases 1 e 2 leem o edital só em parte: o conteúdo programático, a regra de correção, a data da prova e uma nota de corte única do conjunto das objetivas. O resto do que o edital declara, e que decide se eu passo, fica de fora. Hoje há quatro lacunas.

1. **A régua de aprovação está incompleta e às vezes errada.**
   - Os editais têm vários cortes cumulativos. O CD 25 exige 18 pontos em conhecimentos gerais, 27 em específicos e 54 no conjunto; o TCU 25, 20, 30 e 60. O projeto guarda só o último.
   - Na FGV, o corte é em acertos e por bloco. A AgSUS pede 20 acertos em gerais e 15 em específicos, sem zerar nenhuma disciplina; o CPRM, 15 no módulo I, ao menos 1 em cada disciplina desse módulo e 20 no módulo II. O projeto não guarda nenhum desses.
   - No CPNU, o corte é de 36 acertos crus, enquanto a nota é ponderada. O arquivo de correção está com corte vazio, porque o extrator procura "nota inferior a N pontos".
   - Resultado: o "quanto falta para passar" que eu vejo pode dizer que atingi o corte quando reprovaria por um mínimo de bloco ou de disciplina.
2. **O edital não é usado para conferir a prova.** Ninguém compara o que o edital promete (número de itens por prova, itens por disciplina na FGV, 5 alternativas, pesos que somam 10 no CPNU) com o que o gabarito e as questões entregaram. Uma divergência passaria em silêncio.
3. **A análise não sabe a que concurso e cargo se refere.**
   - O nome é o slug da pasta. O TCU nem tem cargo declarado.
   - No edital da PF, os cortes de delegado, perito e escrivão estão lado a lado. Sem o cargo, qualquer extração pode pegar o número errado.
4. **O que mais o edital oferece nunca foi inventariado.** Exemplos:
   - estrutura de fases e peso de cada uma na nota final;
   - critérios de desempate, que no Cebraspe separam nota líquida e número de acertos;
   - teto de classificados (os 80 primeiros no TCU);
   - validade (6 meses na PF, 2 anos nos demais);
   - regra de anulação;
   - legislação-base.

   Cada candidato a nova extração tem de vir com um uso declarado, para não virar ruído.

Também quero rastreabilidade: todo valor tirado do edital precisa trazer o trecho, o documento e a página, para eu conferir contra o PDF em menos de 2 minutos.

## Solution

Uma extensão da extração do edital, da validação e da aplicação, em quatro partes:

1. **Regras do edital, por concurso e por cargo.** Cada concurso analisado ganha, no mesmo arquivo de edital estruturado:
   - a identificação: nome oficial, cargo, especialidade e vagas;
   - pesos, distribuição de questões, cortes (cada um com a sua unidade, pontos ou acertos), cronograma e metadados descobertos.

   A extração respeita o bloco do edital que é do cargo. Cada valor traz a fonte, o trecho de origem e a confiança. As retificações sobrescrevem o edital.
2. **Validação edital × prova × gabarito.** Um CSV de discrepâncias por concurso, com severidade `info`, `warn` ou `error` e uma ação sugerida.
3. **Catálogo de descobertas.** Um markdown por concurso, gerado a partir de um registro versionado de candidatos. Cada candidato tem uso no projeto, impacto e status (aplicado, proposto ou descartado). O catálogo tem uma seção de propostas de evolução e outra de descartados com o motivo.
4. **Aplicação.** Funções de análise novas calculam:
   - a nota ponderada por disciplina;
   - o gap contra cada corte aplicável, em que só é "atingido" quem satisfaz todos;
   - quanto o ranking dos meus concursos muda entre bruto, corrigido e ponderado;
   - uma simulação, rotulada como estimativa, de quanto a nota e o gap mudam se eu subir numa disciplina.

   Um notebook novo mostra tudo isso, com um painel das peculiaridades do edital.

## User Stories

### Identificação e escopo por cargo
1. Como candidato, quero que cada análise mostre o nome oficial do concurso como está na capa do edital, para reconhecer o concurso sem decorar o slug da pasta.
2. Como candidato, quero que o cargo e a especialidade venham do edital, para ter certeza de qual vaga está sendo analisada.
3. Como candidato, quero que, num edital de um só cargo, o cargo seja lido do edital mesmo que a configuração não o declare, para cobrir casos como o TCU.
4. Como candidato, quero que, num edital de vários cargos, o cargo da configuração seja casado com a lista do edital, para que a extração use o bloco certo.
5. Como candidato, quero um aviso em discrepâncias quando o cargo declarado não casar com nenhum cargo do edital, para corrigir o cadastro antes de confiar nos números.
6. Como candidato, quero que cortes, distribuição, pesos, duração e vagas sejam lidos só do trecho do meu cargo, para não usar o corte de delegado numa prova de perito.
7. Como candidato, quero ver o número de vagas do meu cargo (ampla concorrência e reservas), o cadastro de reserva e o teto de classificados, para entender o contexto da concorrência.
8. Como candidato, quero que as vagas sejam só contexto e não entrem em cálculo, para não confundir minha nota com uma previsão de aprovação.
9. Como candidato, quero que os CSVs e o consolidado continuem usando o slug da pasta como chave do concurso, para que nada que já existe quebre.

### Pesos
10. Como candidato, quero que o tipo de peso do edital seja registrado (uniforme, por disciplina, por tipo de questão, por bloco, por faixa de itens ou fórmula), para saber como a nota é composta.
11. Como candidato, quero que o quadro de eixos do CPNU seja representado como peso por faixa de itens, por variante, para manter o modelo já validado contra o resultado oficial.
12. Como candidato, quero que o peso lido do edital seja tratado como expectativa e o peso já resolvido na correção como o realizado, para que a nota não mude por uma releitura do edital.
13. Como candidato, quero um aviso quando o peso do edital divergir do realizado, para investigar a divergência.
14. Como candidato, quero que a soma dos pesos dos eixos do CPNU seja conferida contra os 10 que o edital declara, para pegar erro de leitura do quadro.

### Distribuição
15. Como candidato, quero o número de questões gerais e específicas declarado no edital, para comparar com a prova aplicada.
16. Como candidato, quero o número de questões por disciplina quando o edital o declara (FGV), para comparar com as questões da minha prova.
17. Como candidato, quero o número de questões por tipo (certo/errado, múltipla escolha, discursiva), para saber o formato esperado.
18. Como candidato, quero que, quando o edital não declara a distribuição por disciplina (Cebraspe), o campo fique vazio com fonte default e sem aviso, para não gerar alarme falso.

### Notas de corte
19. Como candidato, quero que cada corte tenha uma unidade, pontos ou acertos, para que 36 acertos do CPNU e 54 pontos líquidos do CD não sejam tratados como o mesmo número.
20. Como candidato, quero o corte do conjunto das objetivas, os cortes por bloco (gerais e específicos), o corte em acertos e o mínimo de acertos por disciplina, para ter a régua inteira do edital.
21. Como candidato, quero que o corte da discursiva seja registrado e exibido, mas fique fora do "atingido", porque o projeto não tem a minha nota discursiva.
22. Como candidato, quero que nenhum corte seja colapsado num número único, para não perder um mínimo eliminatório.
23. Como candidato, quero que a anulada conte como acerto também nos cortes em acertos, como diz o edital ("pontuação atribuída a todos"), para que o gap bata com o resultado oficial.

### Cronograma
24. Como candidato, quero as datas da objetiva, da discursiva, do resultado preliminar, do resultado final e do recurso, quando o edital as traz, para ter o cronograma do concurso.
25. Como candidato, quero que a data da prova do consolidado continue sendo a da objetiva, para que as análises da fase 2 não mudem.
26. Como candidato, quero que data ausente fique vazia com aviso e nunca seja imputada, para que nenhuma data inventada entre na tendência.
27. Como candidato, quero que a discursiva em outro dia (CPNU, 7/12/2025) e no mesmo dia em outro turno (Cebraspe) sejam distinguidas, para ler o cronograma corretamente.

### Retificações e rastreabilidade
28. Como candidato, quero declarar PDFs de retificação no concurso, lidos depois do edital e dos anexos, para que o valor retificado vença.
29. Como candidato, quero que, quando uma retificação define um campo, a fonte seja "retificacao" e o trecho venha da retificação, para auditar a mudança.
30. Como candidato, quero que as notas "(Retificado por meio do Edital nº N)" no texto do edital também marquem a fonte como retificação, para saber quando um trecho já é retificado.
31. Como candidato, quero que todo valor de fonte edital, retificação ou descoberta tenha trecho, documento e página, para conferir em menos de 2 minutos.
32. Como candidato, quero uma confiança de 0 a 1 em cada extração, para priorizar o que conferir à mão.
33. Como candidato, quero a precedência retificação, edital, configuração e default, com aviso no default, para que a fonte mais confiável vença.
34. Como candidato, quero um aviso quando um campo cair no default e o texto do edital mencionar "peso", "nota mínima", "corte", "desempate" ou "distribuição", para que nada seja silenciado.

### Metadados e descoberta dirigida
35. Como candidato, quero que cada candidato conhecido seja marcado como encontrado, não encontrado ou ambíguo em cada concurso, com trecho, para saber o que o edital declara e o que não declara. Os candidatos conhecidos são: número de alternativas, tipo de questão, formato de marcação, tempo de prova, consulta, fases e caráter, peso das fases e fórmula da nota final, critérios de aprovação, desempate, legislação-base, bibliografia, vagas e cadastro de reserva, validade, locais, anulação, critérios da discursiva, formato e prazo de recurso.
36. Como candidato, quero que nenhum candidato vire invisível quando não for encontrado, para distinguir "o edital não declara" de "o extrator não achou".
37. Como candidato, quero que todo metadado tenha um uso no projeto declarado e uma severidade se estiver ausente, para que a extração não vire ruído.
38. Como candidato, quero as descobertas que mudam o cálculo, para que o gap e a simulação sigam a regra real:
    - corte em acertos ao lado de nota ponderada (CPNU);
    - desempate que separa nota líquida e acertos (Cebraspe);
    - teto de classificados, que não é nota mínima (TCU, CPNU).
39. Como candidato, quero que a legislação-base registre o marco do edital de que lei posterior à publicação não é cobrada (AgSUS), para priorizar o estudo.
40. Como candidato, quero um catálogo de descobertas por concurso, com informação, valor, trecho de origem, uso no projeto, impacto e status, para ver de uma vez o que o edital oferece.
41. Como candidato, quero uma seção de propostas de evolução no catálogo para as descobertas de alto impacto que não cabem nesta fase, para decidir o que fazer depois.
42. Como candidato, quero uma seção de descartados com o motivo, para não reavaliar a mesma informação no futuro.
43. Como candidato, quero que uma descoberta que afete uma fase anterior (por exemplo, número de alternativas no OCR da folha) vire só proposta, com diff estimado, para que nenhum código já validado mude sem a minha confirmação.

### Validação edital × prova × gabarito
44. Como candidato, quero um CSV de discrepâncias por concurso com item, esperado no edital, observado na prova, diferença, severidade e ação sugerida, para agir sobre cada divergência.
45. Como candidato, quero `error` quando o total de itens ou o total de um bloco ou prova divergir do edital, para pegar faixa de itens ou gabarito errados.
46. Como candidato, quero `warn` quando a contagem por disciplina divergir do edital (só onde ele declara), casando pela disciplina canônica, para revisar a classificação.
47. Como candidato, quero `error` quando o edital disser 5 alternativas e o gabarito só usar letras até D, para pegar um template de folha ou gabarito errado.
48. Como candidato, quero `info` quando a data usada vier da configuração e diferir da data provável do edital, porque a retificação pode ter mudado a data.
49. Como candidato, quero `warn` quando o peso realizado divergir do peso do edital, para seguir a regra 7 sem trocar a nota.
50. Como candidato, quero `error` quando os pesos dos eixos do CPNU não somarem 10, para pegar leitura errada do quadro.

### Aplicação no desempenho
51. Como candidato, quero a nota ponderada por disciplina (acerto vale o peso do item, sem desconto), para separar o efeito do peso do efeito da penalidade.
52. Como candidato, quero, para cada corte aplicável, a nota atual, o corte, o gap absoluto na unidade do corte, o gap percentual sobre a nota máxima do escopo e se foi atingido, para saber quanto falta em cada régua.
53. Como candidato, quero que "atingido" só seja verdadeiro quando todos os cortes aplicáveis forem satisfeitos (bloco, conjunto, acertos e mínimo por disciplina), para não ter falsa sensação de aprovação.
54. Como candidato, quero saber em quantas posições o ranking dos meus concursos muda entre bruto, corrigido e ponderado, para entender quanto a regra mexe na comparação.
55. Como candidato, quero simular "se eu subir X pontos percentuais na disciplina Y", para ver como a nota e o gap mudariam. A simulação converte erros e brancos em acertos na proporção atual de cada um.
56. Como candidato, quero que a simulação seja rotulada como estimativa e nunca use linguagem de previsão ("vou passar", "serei aprovado"), para não confundir cenário com resultado.
57. Como candidato, quero que a simulação não estime minha colocação entre candidatos, porque o projeto não tem as notas dos outros.
58. Como candidato, quero que os critérios de desempate apareçam na ordem do edital, sem nenhum cálculo, para saber o que pesa num empate.
59. Como candidato, quero declarar um concurso-alvo na configuração global e, sem ele, ver todos os concursos, para focar no concurso que importa sem esconder os outros.

### Notebook e relatórios
60. Como candidato, quero uma tabela de quanto preciso melhorar em cada disciplina para atingir o corte do concurso-alvo (ou de todos), para planejar o estudo.
61. Como candidato, quero barras horizontais de gap percentual por disciplina, coloridas por atingido, para ver de relance onde estou abaixo.
62. Como candidato, quero a comparação lado a lado de percentual bruto, percentual ponderado e gap por concurso, para ver a régua inteira.
63. Como candidato, quero um destaque em markdown quando o ranking mudar entre as métricas, para não perder essa mudança.
64. Como candidato, quero um painel de peculiaridades do edital com as descobertas de alto impacto, para não ser surpreendido por uma regra. Exemplos: anuladas excluídas do mérito, corte em acertos, teto de classificados, cortes da discursiva.
65. Como candidato, quero que o cabeçalho do relatório por concurso mostre o nome oficial e o cargo, para identificar o relatório.
66. Como candidato, quero que o notebook novo e os existentes executem do zero sem erro, para confiar que tudo é reproduzível.

### Compatibilidade e operação
67. Como candidato, quero que nenhum CSV das fases 1 e 2 ganhe ou perca colunas, para que relatórios, scripts e testes continuem funcionando.
68. Como candidato, quero que regravar o conteúdo programático não apague as regras novas do edital estruturado, para que as duas partes convivam no mesmo arquivo.
69. Como candidato, quero que a próxima análise gere as saídas novas em todos os concursos já analisados, sem forçar o reprocessamento à mão.
70. Como candidato, quero que o README tenha uma seção sobre a fase 3 e que o AGENTS.md tenha as convenções de extração e de descoberta, para que outra pessoa ou agente siga as mesmas regras.

## Implementation Decisions

- **Módulos.**
  - Um módulo novo na camada de análise, `regras_edital`, extrai identificação, pesos, distribuição, cortes, cronograma e metadados. Ele também guarda o registro versionado de candidatos.
  - Um módulo novo, `validacao_edital`, compara edital, prova e gabarito e gera o DataFrame de discrepâncias.
  - O módulo de evolução ganha quatro funções e mantém as assinaturas que já existem.
  - O módulo de conteúdo programático da fase 1 continua dono dessa parte. Não vai existir um segundo módulo chamado "edital".
- **Sem sobreposição com a correção.** A regra de correção da fase 2 não importa nada do módulo novo. O arquivo de correção mantém o schema e os valores; ele é a fonte do peso realizado.
- **Interfaces de extração.** Cada extrator recebe as páginas dos documentos do edital (anexos e retificações incluídos), o cargo e a lista de candidatos, conforme o caso. Ele devolve uma configuração em que cada valor tem fonte, trecho, documento, página e confiança. Fontes possíveis: retificação, edital, configuração, default ou descoberta.
  - Extratores: identificação, pesos, distribuição, cortes, cronograma e metadados.
  - Um candidato não encontrado sai com status "não encontrado". Ele não some da saída.
- **Estratégia em camadas.**
  1. Regex sobre as seções típicas: quadro de provas, critérios de avaliação, nota final, desempate, cronograma e anexos.
  2. A configuração do concurso.
  3. Default com aviso.

  As retificações declaradas são lidas por último, e a mais recente vence campo a campo. Não há fallback por LLM.
- **Escopo por cargo.**
  - Edital com um só cargo: o cargo vem do edital.
  - Edital com vários cargos: o cargo da configuração é casado com a lista do edital por texto normalizado. No CPNU, valem os códigos das variantes.
  - Sem casamento: aviso em discrepâncias e extração no escopo do concurso inteiro, com confiança reduzida.
- **Schema dos cortes.** Cada corte tem valor, unidade (pontos ou acertos), escopo, fonte, trecho e confiança. Os campos são:
  - corte do conjunto das objetivas;
  - cortes por bloco (geral e específica);
  - corte em acertos;
  - mínimo de acertos por disciplina;
  - corte da discursiva, que é só informativo.

  Isto substitui os campos "geral, por prova, por disciplina e de classificação" da proposta original. O teto de classificados vai para os metadados, porque não é nota.
- **Schema dos pesos.** O tipo pode ser uniforme, por disciplina, por tipo de questão, por bloco, por faixa de itens ou fórmula. "Por faixa de itens" é o quadro de eixos por variante, no mesmo formato de faixas do arquivo de correção.
- **Cronograma.** Tem objetiva, discursiva, resultado preliminar, resultado final e recurso. A data da prova do consolidado continua sendo a da objetiva, resolvida como na fase 2.
- **Persistência.** Tudo fica no arquivo de edital estruturado já existente, em blocos novos ao lado do conteúdo programático. A gravação do conteúdo programático passa a preservar as chaves que não são dela.
  - Dois arquivos novos por concurso: o CSV de discrepâncias e o markdown do catálogo.
  - Os CSVs das fases 1 e 2 e o parquet não mudam de schema.
- **Execução.** A extração, a validação e o catálogo rodam dentro do comando de análise, reaproveitando as páginas que ele já lê. As saídas novas entram no manifesto, e a versão da análise sobe para que os nove concursos sejam regenerados.
- **Configuração.**
  - O edital do concurso aceita uma lista de retificações.
  - A configuração global aceita um concurso-alvo opcional, que começa vazio.
  - Os dois são validados como os campos atuais e documentados no modelo de domínio.
- **Severidades da validação.**
  - `error`: total ou bloco divergente, alternativas incompatíveis com o gabarito, soma dos pesos do CPNU diferente de 10.
  - `warn`: contagem por disciplina divergente onde o edital declara, peso realizado diferente do edital, cargo sem casamento.
  - `info`: data da configuração diferente da data do edital.
  - A cor da caneta contra lápis na folha não é validada: a folha digitalizada não traz esse sinal.
- **Fórmulas.**
  - Nota ponderada: acerto vale o peso do item, sem desconto por erro.
  - Corrigido: peso e desconto, como na fase 2.
  - Gap absoluto: na unidade do corte.
  - Gap percentual: gap dividido pela nota máxima do escopo, em pontos percentuais.
  - A anulada vale ponto ou acerto, como diz o edital.
  - A simulação converte round(X% × n) itens que não são acerto em acerto, na proporção atual de erros e brancos da disciplina.
- **Catálogo.** É gerado a partir do registro de candidatos e da extração do concurso. Tem três partes: a tabela obrigatória, as propostas de evolução e os descartados com o motivo. O template fica no modelo de domínio, e o AGENTS.md aponta para ele.
- **Rótulos.** Catálogo, discrepâncias, notebook novo e cabeçalho do relatório por concurso mostram nome oficial e cargo. A coluna de concurso continua sendo o slug.

## Testing Decisions

- **O que é um bom teste:** valida comportamento observável (arquivos gerados, valores, avisos e mensagens), nunca detalhes internos. As fixtures são pequenas e determinísticas. Dados reais só entram como trechos curtos de texto dos editais. O valor esperado sai de um exemplo calculado à mão ou do edital, nunca recalculado do mesmo jeito que o código.
- **Ponto de teste 1, a análise ponta a ponta (existente).** Concursos sintéticos em pasta temporária, com o edital em texto e páginas separadas por form feed, usando os helpers atuais de criar, analisar e ler CSV. Casos:
  - o edital estruturado tem identificação, as quatro configurações e os metadados, e mantém o conteúdo programático depois de regravado;
  - o CSV de discrepâncias tem um `error` quando o edital diz 5 alternativas e o gabarito só usa letras até D;
  - o catálogo tem a tabela, as propostas e os descartados;
  - uma retificação declarada sobrescreve o corte e marca a fonte como retificação;
  - cargo sem casamento gera aviso;
  - os CSVs existentes mantêm exatamente as mesmas colunas;
  - a mudança de versão regenera as saídas;
  - os campos novos de configuração são validados.
- **Ponto de teste 2, do texto do edital às regras (novo, puro).** Trechos reais curtos: quadro 7.1 e item 8.11 do Cebraspe, AgSUS 9.5 e 9.14, CPRM 12.13, CPNU 8.9 e 8.15, Anexo I de cronograma. Também textos sintéticos. Casos obrigatórios:
  - cortes em pontos por bloco e no conjunto;
  - corte em acertos;
  - mínimo por disciplina;
  - escopo por cargo, com dois cargos e cortes diferentes;
  - cronograma com a discursiva no mesmo dia e em outro dia;
  - distribuição FGV por disciplina;
  - candidato não encontrado com status explícito;
  - default com palavra-gatilho emitindo aviso;
  - trecho, documento e página preenchidos sempre que a fonte for edital, retificação ou descoberta.
- **Ponto de teste 3, as funções de análise sobre o consolidado (existente).** A factory de consolidados sintéticos mais uma configuração de cortes. Casos:
  - nota ponderada bate com o cálculo manual numa fixture com pesos 1, 2 e 0,5 misturados;
  - "atingido" falso quando o conjunto passa mas uma disciplina zera ou um bloco fica abaixo;
  - "atingido" verdadeiro só com todos os cortes satisfeitos;
  - corte em acertos com anulada contando;
  - deslocamento do ranking entre as três métricas;
  - a simulação muda nota e gap, é rotulada como estimativa e não contém linguagem de previsão;
  - concurso-alvo ausente devolve todos.
- **Notebooks:** teste de fumaça com o script que executa o notebook novo e os existentes do zero.
- **Verificação com dados reais (manual, ao final):**
  - os nove concursos têm edital estruturado, discrepâncias e catálogo;
  - os cortes extraídos batem com a tabela das Further Notes;
  - pelo menos três descobertas além da lista conhecida aparecem com trecho e uso;
  - o arquivo de correção não muda.
- **Prior art:** os testes da fase 2 da correção do edital pela análise ponta a ponta; os testes puros de extração da correção a partir de trechos; os testes de evolução sobre a factory de consolidado sintético.
- **Desenvolvimento:** TDD em fatias verticais, uma por vez, nos três pontos de teste. O critério de pronto é a suíte verde, o ruff limpo e todos os notebooks executando do zero.

## Out of Scope

- Fallback por LLM na extração.
- Imputar a data da prova a partir do resultado preliminar.
- Estimar colocação entre candidatos ou cruzar o número de vagas com o resultado oficial.
- Retrofitar o OCR da folha ou os templates com o número de alternativas e o formato de marcação. Isso fica como proposta no catálogo.
- Reclassificar tópicos por legislação-base ou por sub-itens do conteúdo programático.
- Gráficos de vagas, cotas, discursiva ou títulos, e qualquer nota discursiva no gap.
- Cadastrar `creci`, `dataprev_2024` e `senappen`.
- Mudar o schema ou os valores do arquivo de correção, dos CSVs e do parquet.

## Further Notes

- **Retificações hoje:**
  - Nenhum concurso tem PDF de retificação separado. O mecanismo é testado com fixture.
  - Os PDFs do CPNU (8ª retificação, 21/11/2025) e do CPRM ("retificado em 24/11/2025") já são o texto retificado.
  - Notas inline aparecem no TCU (Editais 4 e 5), no Funpresp (2 a 4), na Infra (2 a 4), na PF (2 e 9) e na Telebras (2 e 3). Elas mudam requisitos, conteúdo, títulos e datas, mas não peso nem corte da objetiva.
- **Cortes esperados** (Cebraspe em pontos líquidos; FGV em acertos):
  - CD 25: 18 em P1, 27 em P2 e 54 no conjunto.
  - TCU 25: 20, 30 e 60; discursiva ≥ 30; os 80 primeiros por lista seguem.
  - PF Perito: 10, 21 e 48; o quadro e os cortes de delegado e escrivão são outros.
  - Telebras: 10, 21 e 36.
  - Funpresp-Jud: 10, 21 e 36.
  - Infra SA: 8, 18 e 30.
  - AgSUS: 20 acertos em gerais, 15 em específicos, não zerar disciplina.
  - CPRM: 15 no módulo I, ao menos 1 por disciplina do módulo I, 20 no módulo II; discursiva ≥ 12.
  - CPNU: 36 acertos nas objetivas; a nota mínima necessária e o teto de 9× as vagas saem depois.
- **Distribuição declarada:**
  - Cebraspe só por prova:
    - CD: 90 + 90;
    - TCU: 100 + 100;
    - PF Perito: 50 + 70;
    - Telebras: 50 + 70.

    No Funpresp e na Infra, o par vem do quadro do item 7 e será confirmado na extração.
  - AgSUS TI (quadro de demais especialidades): Português 15, Raciocínio 5, Legislação 10, Informática 10, específicos 30.
  - CPRM ADS: Português 10, Raciocínio 10, Atualidades 10, específicos 40.
  - CPNU: 30 gerais e 5 eixos de 12, com pesos de 1 a 5 que somam 10.
- **Cronograma:**
  - As datas da objetiva são as da fase 2.
  - A discursiva é no mesmo dia em todos os Cebraspe e no CPRM. No CPNU, é em 07/12/2025.
  - A AgSUS (TI) não tem discursiva. A nota final dela é só a objetiva, e a experiência profissional conta só em Saúde Pública.
- **Descobertas além da lista conhecida:**
  - corte em acertos crus ao lado de nota ponderada (CPNU 8.15);
  - desempate separando nota líquida e acertos na mesma prova (CD 12.1 e TCU 11.1);
  - teto de classificados, que não é nota mínima (TCU 8.11.5 e CPNU item 11);
  - soma dos pesos dos eixos igual a 10 (CPNU 8.9.2);
  - lei posterior ao edital não cobrada (AgSUS 16.11.1).
- **Descartados:**
  - Motivo: não mudam nota, gap nem ranking. Itens: taxa, remuneração, jornada, lotação, percentuais de cota, isenção, atendimento especial, nome social, amamentação, heteroidentificação e perícia médica.
  - Caneta contra lápis: sem sinal na folha digitalizada.
- Não há issue tracker configurado, então esta spec fica no repositório, como as das fases 1 e 2. A ordem de execução é:
  1. modelo de domínio;
  2. extração;
  3. persistência no edital estruturado;
  4. validação;
  5. aplicação;
  6. saídas reais;
  7. notebook;
  8. documentação.
