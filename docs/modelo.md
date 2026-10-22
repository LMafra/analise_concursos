# Modelo de domínio

Este documento descreve as entidades do domínio, o schema do `concurso.yaml`, o formato do edital manual e os contratos dos arquivos de saída.

## Entidades

**Concurso.** É uma pasta em `provas/<concurso>/` com um `concurso.yaml`. Tem:
- nome;
- banca: `cebraspe`, `fgv`, `selecon` ou `quadrix`;
- formato: `multipla_escolha` (A–E) ou `certo_errado` (C/E);
- regra de pontuação;
- cargo e tipo do caderno;
- edital;
- uma ou mais provas;
- a fonte das respostas;
- o resultado oficial (opcional);
- o histórico de eventos.

A situação é derivada: `completo`, `incompleto` (falta um arquivo, com o caminho) ou `desatualizado` (arquivo novo não cadastrado ou configuração inválida).

**Prova.** É uma parte do concurso com gabarito próprio. Exemplos: `cg` e `ce` na Cebraspe; `unica` nas demais bancas. Tem:
- chave;
- caderno de questões (opcional);
- gabarito;
- faixa de itens `[inicio, fim]`, com numeração global no concurso e faixas disjuntas entre as provas;
- faixas de disciplina (opcionais).

**Questão.** Um item numerado de uma prova. Tem:
- gabarito;
- se foi anulada;
- a resposta marcada;
- o resultado;
- disciplina;
- tópico sugerido (com score) e tópico final (revisado ou não).

**Disciplina e Tópico.** Vêm do edital estruturado, na hierarquia conhecimento (ex.: "Conhecimentos Gerais") → disciplina → tópicos. A disciplina e o tópico podem ter peso.

A disciplina de uma questão vem, em ordem de prioridade:
1. das faixas manuais do `concurso.yaml`;
2. dos cabeçalhos do caderno (FGV e SELECON);
3. do tópico sugerido (Cebraspe).

O tópico vem da sugestão por similaridade ou da revisão manual. Sem classificação, o valor é `nao_mapeado`.

**Gabarito.** É o arquivo de uma prova, com status `preliminar` ou `definitivo`. Cada item tem questão, resposta e se foi anulado (`X` ou `*`). Um PDF pode ter várias seções (cargo e tipo); a seção é escolhida pelo `cargo`/`tipo` do concurso.

**RespostaMarcada.** É a leitura de uma questão. Tem:
- alternativa (ou vazio);
- estado: `marcada`, `branco` ou `multipla`;
- confiança (0–1; 1 no `respostas.txt`);
- origem: `folha` ou `manual`;
- arquivo e página.

Uma leitura abaixo de `limiar_confianca` fica com `revisar = True`.

**Resultado.** É o desfecho de uma questão: `acerto`, `erro` ou `branco`. Anulada conta como acerto, mas fica fora do percentual de mérito. Regras de pontuação:
- `simples`: nota líquida = acertos;
- `cebraspe`: nota líquida = acertos − erros.

**Modelo de correção.** É a regra de pontuação da prova objetiva definida no edital. Tem:
- modelo: `bruta` (acerto vale 1, sem desconto), `liquida` (cada erro anula `fator_penalidade` acertos, com ou sem pesos) ou `ponderada` (sem desconto, com pesos que variam entre faixas de itens);
- fator de penalidade (1,0 na Cebraspe; 0 nas FGV analisadas; 0,25 em "a cada 4 erradas, anula-se uma certa");
- pesos por faixa de itens (itens fora das faixas valem 1);
- nota máxima e nota de corte do conjunto das provas objetivas;
- fonte: `edital`, `config` ou `default`;
- confiança da extração (0–1) e o trecho, o documento e a página de onde a regra foi lida;
- variante: o código do cargo, quando o concurso tem várias opções com pesos diferentes (CPNU).

A regra é extraída por regex do texto dos documentos do edital (anexos primeiro, sem OCR). Os padrões reconhecidos são:
- penalidade explícita ("1,00 ponto negativo … discordância") e fracionária ("a cada N erradas, anula-se uma certa", fator 1/N);
- pontos diferentes por prova ou módulo (creci: "1,00 ponto … conhecimentos básicos; 2,00 pontos … específicos"; dataprev: "valerá 1 ponto no Módulo de Conhecimentos Gerais, e 2,5 pontos no Módulo de Conhecimentos Específicos"). Os gerais vêm antes dos específicos, e quantos itens tem cada parte sai do número de itens do concurso e da nota máxima do edital; sem solução inteira, o padrão é ignorado;
- nota igual ao total de acertos, "valendo 1 ponto cada questão" ou "cada acerto valerá 1 ponto", sem menção a desconto (`bruta`);
- o quadro de pesos por eixo temático e cargo (CPNU), descrito abaixo em variantes.

A precedência é edital, depois `concurso.yaml`, depois default (`bruta`, fator 0). Pesos, nota máxima e nota de corte seguem a mesma ordem, campo a campo. Sem nota máxima em nenhuma fonte, ela é a soma dos pesos dos itens (o número de itens quando não há pesos).

**Variantes.** O bloco `correcao.variantes` do `concurso.yaml` lista as opções de cargo (no CPNU, os códigos dos cargos em que houve inscrição), e o `correcao.json` ganha uma configuração por variante. O fator e a nota de corte são os do concurso. A nota máxima é a soma dos pesos da variante, salvo se declarada no `concurso.yaml`. Os pesos de cada variante vêm:
1. dos `pesos` declarados na variante, que aqui prevalecem sobre o edital (fonte `config`);
2. do quadro de pesos do edital (fonte `edital`): a linha do cargo traz um peso de 1 a 5 por eixo ("B3-08-A 1 1 2 4 2"), e as faixas saem do texto do edital (no CPNU, itens 1–30 de conhecimentos gerais com peso 1 e cinco eixos de 12 itens: 31–42, 43–54, 55–66, 67–78 e 79–90). O trecho de origem é a linha do quadro, com o documento e a página;
3. sem nenhum dos dois, dos pesos do concurso, com aviso. O quadro também é ignorado, com aviso, quando os itens gerais e os eixos não somam o número de itens do concurso.

Os pesos afetam só a nota do concurso, a nota normalizada e o ranking. O percentual por disciplina ou eixo não muda, porque cada eixo tem um peso só.

A análise emite aviso quando:
- a regra cai no default (o aviso é mais forte se o edital mencionar penalidade: "ponto negativo", "desconto de", "descontado", "anula um acerto");
- o fator ou os pesos do bloco `correcao` diferem do edital (vale o edital);
- uma variante não tem pesos no quadro do edital nem no `concurso.yaml`;
- a `pontuacao` declarada contradiz a regra vinda do edital ou do bloco `correcao` (`cebraspe` com fator diferente de 1, ou `simples` com fator diferente de 0). No default, vale só o aviso de default.

A `pontuacao` continua alimentando a `nota_liquida` dos CSVs; o modelo de correção alimenta a análise evolutiva e a nota final dos relatórios.

**Pontuação por item.** Cada questão não anulada recebe três pontuações:

| versão | acerto | erro | branco |
|---|---|---|---|
| bruta | 1 | 0 | 0 |
| corrigida (regra do edital) | 1 | \(-f\) | 0 |
| ajustada ao acaso | 1 | \(-1/(k-1)\) | 0 |

\(f\) é o fator de penalidade, e \(k\) é o número de alternativas: 2 em `certo_errado` (erro vale −1) e 5 em `multipla_escolha` (erro vale −0,25). A versão ajustada é a métrica padrão para comparar concursos, porque um chute puro vale 0 nos dois formatos.

As anuladas ficam fora das três versões (não medem conhecimento) e os percentuais podem ser negativos. O peso do item não entra nessas pontuações. A exceção é a nota do concurso, que segue o edital: soma das pontuações corrigidas multiplicadas pelo peso de cada item, com cada anulada valendo o seu peso. A nota normalizada é \(\max(0, \text{nota}/\text{nota máxima} \times 100)\), truncada em 0 só ela. Na Cebraspe, a nota corrigida é igual à soma da `nota_liquida` legada.

**Nota final** (`notas_finais`). É a nota do concurso pela regra do edital, uma por variante, com a nota máxima e a nota de corte ("atinge o corte" quando nota ≥ corte). Só existe nos modelos `liquida` e `ponderada`, em que ela difere da contagem de acertos; no `bruta`, a nota final é o próprio número de acertos. Aparece no `relatorio.md`, no `comparativo_concursos.md` e no `relatorio_evolucao.md`.

**Ranking entre concursos** (`comparar_bruto_vs_corrigido`). Uma linha por concurso e variante, sem as anuladas, com o percentual nas três versões:

- bruto e ajustado: média simples das pontuações dos itens;
- corrigido: média das pontuações corrigidas ponderada pelo peso da variante, que é a regra do edital.

A posição 1 é o maior percentual, e empates dividem a posição. As posições contam concursos, não linhas: cada variante é posicionada contra os outros concursos, e um concurso com variantes entra no ranking dos outros pela sua melhor variante. O deslocamento é a posição no bruto menos a posição na versão, ou seja, quantas posições a linha sobe.

**Evolução por disciplina** (`concursos.analytics.evolucao`). Todas as métricas são por concurso, bloco e disciplina canônica e vêm com o n. Só a nota normalizada conta as anuladas, como ponto, seguindo o edital; as demais as excluem. Disciplina com n < 5 é marcada como amostra insuficiente.

- **z-score:** \(z_d = (\bar s_d - \bar s_g)/(\sigma_g/\sqrt{n_d})\). Aqui \(s\) é a pontuação de cada item na versão escolhida (padrão: ajustada), \(g\) são os itens não anulados do concurso, e \(\sigma_g\) é o desvio populacional deles. Numa prova sem brancos, o z não muda entre versões que diferem por transformação afim; é o caso de bruta e ajustada na FGV.
- **Tendência:** slope do z pela ordem (regressão linear), com p-value. Só contam concursos com data e pontos com n ≥ 5, e a série precisa de 3 ordens distintas ou mais; senão, fica como amostra insuficiente. Toda série com algum concurso datado tem linha: `pontos` e `n` contam só os pontos com n ≥ 5, e `n_total` soma todos.
- **Correlação:** Spearman entre a ordem e o z, com os mesmos concursos da tendência; concursos na mesma ordem viram um ponto só, pela média dos z. É calculada por disciplina, porque a média dos z de um concurso fica perto de 0 por construção. Com até 9 pontos, o p-value é exato, por permutação de todas as ordenações.
- **Estrato:** a tendência e a correlação aceitam uma série única ou uma série por banca.

**Evolução e fraquezas por tópico** (`concursos.analytics.evolucao`). O tópico é a `chave_topico`: disciplina canônica mais as palavras-chave do nome. O bloco não separa tópicos, ao contrário das disciplinas, então o mesmo tópico nas provas geral e específica de um concurso é uma linha só. Tópicos não mapeados e anuladas ficam fora, e os percentuais não são truncados.

- **Cobertura do edital:** por concurso, conta os tópicos distintos do `edital_estruturado.json`, quantos foram cobrados na prova (questão anulada também cobra) e quantos tópicos da prova não casam com o edital. O casamento é só pelas palavras-chave do nome do tópico, dentro do concurso, porque a disciplina da prova nem sempre repete a do edital; pelo mesmo motivo, um tópico repetido em duas disciplinas do edital conta uma vez.
- **Tendência por tópico:** slope do percentual (padrão: ajustado) pela ordem, com as mesmas regras da tendência por disciplina. O n mínimo por ponto é configurável (padrão 5). Tópico nunca cobrado não tem linha.
- **Fracos persistentes:** tópicos abaixo do limiar (padrão 60%; o notebook passa o `limiar_topico_baixo` do `config.yaml`, o mesmo do comparativo da fase 1) em pelo menos 2 concursos, com acertos, erros e brancos somados entre concursos e n agregado ≥ 5. O n de cada concurso não importa, porque só a soma dá amostra. O percentual agregado é a média dos itens de todos os concursos.

**Insights e relatório de evolução** (`concursos.analytics.insights`).

- **Meta** (`comparar_com_meta`, em `evolucao`): por concurso e variante, a nota pela regra do edital (peso da variante, anulada vale ponto), a nota de corte, a nota normalizada (0–100 da nota máxima, truncada em 0) e a distância até a meta (padrão 70%), em pontos percentuais.
- **Nota ponderada** (`nota_ponderada_por_disciplina`, em `evolucao`): por concurso, variante, bloco e disciplina canônica, `nota_ponderada = Σ peso × acerto`, sem desconto do erro e com a anulada contando como acerto; `nota_maxima = Σ peso` e `percentual_ponderado = 100 × nota_ponderada / nota_maxima`.
- **Gap para o corte** (`gap_para_corte`, em `evolucao`): recebe os cortes do edital estruturado (`cortes_por_concurso`, em `consolidado`) e devolve uma linha por corte aplicável de cada concurso e variante; no escopo `disciplina`, uma por disciplina (do `bloco` do corte, ou de todos). O corte da discursiva fica de fora.
  - Nota no escopo, na unidade do corte: em `pontos`, `Σ peso × pontos corrigidos`, com a anulada valendo 1; em `acertos`, a contagem de acertos mais as anuladas.
  - Nota máxima do escopo: `Σ peso` em pontos e o número de itens em acertos.
  - `gap = nota − corte` (positivo acima do corte), `gap_percentual = 100 × gap / nota máxima do escopo` (pontos percentuais) e `satisfeito = gap ≥ 0`.
  - `atingido` só é verdadeiro quando todos os cortes da variante são satisfeitos: passar no conjunto não basta se um bloco ou uma disciplina fica abaixo.
- **Concurso-alvo:** `concurso_alvo` no `config.yaml` (nome da pasta do concurso, opcional) restringe as duas funções acima, a simulação e o desempate a esse concurso. Sem ele, saem todos.
- **Ranking entre métricas** (`ranking_concursos_por_metrica`, em `evolucao`): por concurso e variante, com a anulada valendo acerto e ponto:
  - `percentual_bruto = 100 × acertos / n` (sem peso, sem desconto);
  - `percentual_corrigido = 100 × Σ peso × pontos corrigidos / Σ peso` (peso e desconto);
  - `percentual_ponderado = 100 × Σ peso × acerto / Σ peso` (peso, sem desconto).

  Posições e deslocamentos seguem o comparativo da fase 2: a posição 1 é o maior percentual, e o deslocamento é quantas posições a linha sobe em relação ao bruto.

  A fórmula do corrigido é a da fase 2, mas a anulada entra pela regra do edital, como no gap. O `comparar_bruto_vs_corrigido` (notebook 02) a exclui, então os percentuais bruto e corrigido dos dois rankings diferem quando o concurso tem anulada.
- **Simulação** (`simular_cenario`, em `evolucao`, e o texto em `insights.descrever_simulacao`): "se eu subir X p.p. na disciplina Y". Em cada concurso com Y:
  - `k = min(round(X/100 × n), erros + brancos)`, com n os itens de Y (anuladas incluídas) e o arredondamento meio para cima;
  - `k_erros = round(k × erros / (erros + brancos))` e `k_brancos = k − k_erros`, tomados na ordem das questões;
  - os itens convertidos viram acerto (1 ponto em todas as versões) e o gap de cada corte é recalculado com `gap_para_corte`.

  A saída tem `natureza = estimativa`, e o texto se apresenta como estimativa de cenário, sem linguagem de previsão e sem estimar colocação.
- **Desempate** (`insights.desempate_por_concurso`): os critérios do metadado `desempate`, na ordem das alíneas do edital, sem cálculo.
- **Gap por disciplina** (`gap_por_disciplina`, em `evolucao`): cada disciplina comparada com o corte que mais a aperta.
  - Um corte de escopo exige `exigido = 100 × corte / nota máxima do escopo`; no mínimo por disciplina, o escopo é a própria disciplina.
  - `percentual` é o da disciplina na unidade do corte, `gap_percentual = percentual − exigido`, e fica o corte de menor gap.
  - `falta = max(0, −gap_percentual / 100 × nota máxima da disciplina)`, na unidade do corte; `no_ritmo = gap_percentual ≥ 0` (a disciplina acompanha o corte, o que não é o "atingido" do gap); `amostra_suficiente = n ≥ N_MINIMO_TOPICO`.
  - Em cada concurso, a disciplina mais longe vem primeiro.
- **Lado a lado** (`comparar_percentual_e_gap`, em `evolucao`): percentual bruto e ponderado do ranking e, de `gap_para_corte`, o menor gap percentual, o corte mais distante e o "atingido".
- **Destaque do ranking** (`insights.destaque_do_ranking`): em markdown, quem sobe e quem cai no corrigido e no ponderado, ou a frase de que o ranking é o mesmo.
- **Peculiaridades** (`insights.peculiaridades_do_edital`): os metadados de impacto alto encontrados, menos `aprovacao` (a régua já são os cortes), mais os cortes em acertos e da discursiva, com o trecho.
- **Carregamento:** `regras_por_concurso` e `cortes_por_concurso` (em `consolidado`) leem o edital estruturado de cada concurso analisado que já tem as regras.
- **Correlação geral** (`correlacao_tempo_percentual`, em `evolucao`): Spearman entre a ordem e o percentual ajustado de cada concurso. É a medida única de tendência geral; a média dos z-scores de um concurso não serve, porque fica perto de 0 por construção.
- **Achados:** melhoras e pioras são as tendências por disciplina com p < 0,05; os fracos usam o limiar do `config.yaml`; o ranking muda quando alguma linha tem deslocamento no corrigido ou no ajustado.
- **Sensibilidade:** os achados são recalculados sem os concursos de nível médio (`escolaridade: medio`), e as diferenças são declaradas.
- **Relatório:** `relatorio_evolucao.md`, na pasta do consolidado, traz as quatro respostas, a sensibilidade, a nota final dos concursos com desconto por erro ou pesos e três PNGs gravados com matplotlib: `evolucao_zscore.png` (só disciplinas com 3 concursos ou mais de n ≥ 5), `heatmap_topicos.png` (tópicos em 2 concursos ou mais) e `painel_correcao.png`.

**Data da prova e metadados.** Cada concurso tem:
- data da prova: a do `concurso.yaml` (`data_prova`) ou, sem ela, a extraída do edital. A configuração vem antes porque no edital a data é sempre "provável" e pode ser retificada. O edital é lido em dois formatos:
  - cronograma: "Aplicação das provas objetivas e discursiva 22/2/2026" (Cebraspe, CPNU);
  - texto corrido: "a Prova Objetiva … será realizada … no dia 12 de outubro de 2025" (FGV).

  Sem data em nenhuma fonte, a análise avisa e o concurso fica sem data, fora das análises de tendência. Nada é imputado (nem data de arquivo, nem data de publicação do edital);
- nível: `federal`, `estadual` ou `municipal`;
- escolaridade: `superior` ou `medio`.

Nível e escolaridade são opcionais e ficam `nao_informado` quando ausentes.

**EventoHistórico.** Registra mudanças no concurso. Hoje só existe a troca do gabarito preliminar pelo definitivo, com data, tipo (`gabarito_definitivo`), prova, arquivo anterior e arquivo novo.

**Validação oficial.** Compara o desempenho calculado com o resultado oficial da banca. A medida é acertos ou pontos, com pesos opcionais por faixa de itens. Uma divergência vira alerta. Se o resultado inclui outras fases, a comparação é só informativa.

## Regras do edital (fase 3)

O módulo `concursos.analytics.regras_edital` lê do texto do edital e dos anexos (sem OCR e sem LLM) o que vai além do conteúdo programático e da regra de correção. O resultado é gravado no `edital_estruturado.json`. Cada valor é um **campo** com:

- `valor`;
- `fonte`: `retificacao`, `edital`, `config`, `default` ou `descoberta`;
- `trecho_origem`, `documento_origem` e `pagina_origem`, sempre preenchidos quando a fonte é `retificacao`, `edital` ou `descoberta`;
- `confianca_extracao`, de 0 a 1.

A precedência é retificação, depois edital, depois configuração, depois default. Um campo que cai no default fica com `valor` nulo, e o motivo vai para `avisos` (lista de textos) e para o log. O `correcao.json` continua sendo a fonte da regra de correção aplicada; as regras do edital são a expectativa.

**Retificações.** Há duas formas de um valor sair com fonte `retificacao`:

- **PDF de retificação:** o arquivo é declarado em `edital.retificacoes` e lido só pelas regras do edital (o conteúdo programático e a correção não o veem). A busca percorre as retificações da mais recente para a mais antiga, e só depois o edital e os anexos. O valor encontrado numa retificação vence o do edital, campo a campo, com o trecho e o documento da retificação. A ordem dos cortes continua a do edital.
- **Nota inline no edital consolidado:** a frase do trecho é seguida da nota "(Retificado por meio do Edital nº …)", antes do próximo subitem e com no máximo um fim de frase entre as duas. O documento de origem continua sendo o edital.

**Identificação** (`identificacao`). Tem os campos `nome_oficial` (o órgão na capa), `edital` (a linha "EDITAL Nº …" da capa), `cargo`, `especialidade`, `vagas`, `cadastro_reserva` e `teto_classificados`, mais `cargo_casado` (lógico) e `cargos_do_edital` (lista). O cargo vem do edital:

- **Lista de cargos:** as linhas "CARGO N: …" ou "EMPREGO N: …" (Cebraspe), os blocos temáticos (CPNU), o cargo da capa ("PARA O CARGO DE …", edital de um cargo só) ou os cargos citados no preâmbulo ("vagas para o cargo de Analista de Gestão", FGV).
- **Casamento:**
  - Num edital de um só cargo, o cargo é o do edital, mesmo sem cargo no `concurso.yaml`.
  - Num edital de vários cargos, o `cargo` do `concurso.yaml` casa pelo número ("CARGO 4: …") ou, sem número, pelo nome: todas as palavras do cargo do edital (sem acento, caixa e palavras vazias) têm de estar no cargo declarado. No empate, vence o nome mais longo.
  - Sem casamento, `cargo_casado` é falso, o CSV de discrepâncias recebe um `warn`, e as extrações usam o concurso inteiro.
- **Especialidade:** é o que vem depois de "– ESPECIALIDADE:", "– ÁREA N:" ou "– ATRIBUIÇÃO:" na linha do cargo, ou depois do primeiro travessão. Na FGV, vem da linha "… – Área: …" do edital ou, sem ela, do resto do cargo declarado (fonte `config`).

As vagas, o cadastro de reserva e o teto de classificados são só contexto e não entram em cálculo. A coluna `concurso` dos CSVs e do parquet continua sendo o nome da pasta.

**Escopo por cargo.** Num edital de vários cargos, um trecho vale para o cargo quando a última menção a cargos antes dele (ou dentro dele) cita o cargo. Exemplo: "o candidato ao cargo de Perito Criminal Federal que…".

- **Onde a menção é procurada:** desde o início do subitem de dois níveis que contém o trecho. Para a alínea c) do 8.11.5, a busca começa no 8.11. Sem numeração por perto, ela cobre os 600 caracteres anteriores.
- **Quando a menção cita o cargo:** quando todas as palavras de um dos nomes citados estão no cargo.
- **Menções genéricas:** "todos os cargos" e "demais cargos" valem para todos.
- **Nível:** "cargos de Nível Superior" e "cargos de Nível Intermediário" casam com a `escolaridade`. Sem escolaridade declarada, vale o nível superior.

**Cortes** (`cortes`). É uma lista com todos os mínimos eliminatórios do cargo, na ordem do edital; nenhum é colapsado num número único. Cada corte é um campo com mais três chaves:

- `escopo`: `conjunto` (todas as objetivas), `geral`, `especifico`, `disciplina` (mínimo em cada disciplina) ou `discursiva`;
- `unidade`: `pontos` (nota líquida, Cebraspe) ou `acertos` (FGV e CPNU);
- `bloco`: no escopo `disciplina`, o bloco das disciplinas. Fica vazio quando vale para todas.

| Padrão no edital | Corte |
|---|---|
| "nota inferior a 18,00 pontos na prova objetiva de conhecimentos gerais P1" | `geral`, 18 pontos |
| "… de conhecimentos específicos P2", "… nos itens de conhecimentos específicos" | `especifico` |
| "… no conjunto das provas objetivas", "… na prova objetiva P1" (prova única) | `conjunto` |
| "acertar, no mínimo, em Conhecimentos Gerais, 20 questões" (AgSUS) | `geral`, 20 acertos |
| "Acertar 15 (quinze) questões do Módulo I" (CPRM; módulo II é `especifico`) | `geral`, 15 acertos |
| "não zerar nenhuma das disciplinas" | `disciplina`, 1 acerto, todas |
| "ao menos 1 (uma) questão em cada disciplina que compõe o Módulo I" | `disciplina`, 1 acerto, `geral` |
| "inferior a 36 (trinta e seis) acertos nas provas objetivas … para os cargos de Nível Superior" | `conjunto`, 36 acertos |
| "aprovado na prova discursiva … NFPD ≥ 30,00 pontos", "reprovado … NPD < 15,00 pontos" | `discursiva` |

Cortes "no bloco I" (escrivão da PF) não são lidos. Para cada escopo e bloco, vale o primeiro na ordem de busca, então a retificação vence o edital. O corte da discursiva é só informativo: o projeto não tem a nota discursiva, e ele fica fora do "atingido".

A precedência é edital, depois `correcao.nota_corte` do `concurso.yaml` (corte do conjunto em pontos, fonte `config`), depois default (lista vazia). Há aviso quando:

- a nota de corte do `concurso.yaml` difere da do edital (vale o edital);
- não há corte em nenhuma fonte. Se o edital menciona "peso", "nota mínima", "corte", "desempate" ou "distribuição", o aviso cita essas palavras.

O `correcao.json` mantém o seu `nota_corte`, que continua alimentando a nota final dos relatórios.

**Cronograma** (`cronograma`). Datas da prova objetiva e do que vem em torno dela, cada uma num campo (`AAAA-MM-DD`): `objetiva`, `discursiva`, `resultado_preliminar` e `resultado_final` (da objetiva), e `recurso` (prazo contra o gabarito, `{inicio, fim}`). O lógico `discursiva_no_mesmo_dia` distingue a discursiva no mesmo dia, em outro turno (Cebraspe, CPRM), da discursiva em outro dia (CPNU, 07/12/2025); fica vazio sem data da discursiva.

- **Onde as datas são lidas:** no cronograma anexo ("Aplicação das provas objetivas e discursiva 8/3/2026", Anexo I do Cebraspe e Anexo X do CPNU) ou no texto ("serão realizadas no dia 30 de novembro de 2025", FGV). Numa célula quebrada do anexo, a data pode vir no meio da atividade ("resultado final nas provas 5/8/2026 objetivas").
- **Data ausente:** fica vazia, nunca é imputada, e um aviso lista as que faltam.
- **Data da prova do consolidado:** continua sendo a do `correcao.json`, resolvida como na fase 2. Quando o `concurso.yaml` declara `data_prova` diferente da objetiva do edital, o CSV de discrepâncias ganha um `info` (`data da prova objetiva`, com a diferença em dias).

**Pesos** (`pesos`). São a expectativa do edital; o peso realizado, que entra na nota, continua sendo o do `correcao.json`. Têm três chaves:

- `tipo`: `uniforme`, `por_disciplina`, `por_tipo_de_questao`, `por_bloco`, `por_faixa_de_itens` ou `formula`;
- `faixas`: variante (vazia quando vale para o concurso todo) → campo com as faixas `{inicio, fim, peso}`, no formato do `correcao.json`. Itens fora das faixas valem 1;
- `soma_dos_eixos`: o total que o edital promete aos pesos dos eixos ("totalizando, em conjunto, o valor de 10", CPNU 8.9.2).

O quadro de eixos do CPNU dá `por_faixa_de_itens`, uma entrada por variante do `correcao.variantes`, com a faixa dos conhecimentos gerais primeiro. Sem quadro, vale a regra de pontuação que a correção também lê: pontos iguais em todos os itens são `uniforme` (Cebraspe, AgSUS, CPRM), e pontos diferentes por parte são `por_bloco`. Sem nenhum dos dois, há aviso. O CSV de discrepâncias ganha duas regras:

| Item | Comparação | Severidade |
|---|---|---|
| `soma dos pesos dos eixos: <variante>` | soma dos pesos dos eixos da variante no edital contra `soma_dos_eixos` | `error` |
| `pesos dos itens[: <variante>]` | peso de cada item no edital contra o do `correcao.json` (um `concurso.yaml` com pesos próprios na variante, por exemplo). Variante fora do quadro de eixos não é comparada | `warn` |

**Distribuição de questões** (`distribuicao`). Tem cinco campos: `total`, `geral` e `especifico` (inteiros), `por_disciplina` (nome da disciplina no edital → número de itens, só as gerais) e `por_tipo` (`certo_errado` ou `multipla_escolha` → total, e `discursiva` → número de questões).

- **Por bloco:** a frase "N questões de Conhecimentos Gerais e M de Conhecimentos Específicos" (FGV, CPNU) ou "Módulo I … N questões" (CPRM). Sem ela, o quadro de provas do Cebraspe ("NÚMERO DE ITENS"): soma das linhas de cada bloco, ou as duas provas objetivas pela posição.
- **Por disciplina:** o quadro de disciplinas da FGV. Num edital com vários quadros, vale aquele cujo título tem mais palavras em comum com o cargo; no empate, o de "demais" especialidades; sem vencedor único, nenhum. As disciplinas específicas do quadro somam no bloco específico.
- **Total:** "total de N questões/itens"; sem ele, a soma dos dois blocos. Sem total, há aviso.

O CSV de discrepâncias compara a distribuição com as questões corrigidas (`questoes.csv`):

| Item | Observado | Severidade |
|---|---|---|
| `total de itens` | número de questões do concurso | `error` |
| `itens de conhecimentos gerais` / `… específicos` | questões por bloco: pela prova (P1/P2) ou, na prova única, pelo bloco da disciplina na taxonomia. Fica de fora se alguma questão não tem bloco conhecido | `error` |
| `disciplina: <nome>` | questões da disciplina, casada pela disciplina canônica da taxonomia (ou pelo nome, se a taxonomia não a conhece) | `warn` |

**Metadados e descoberta dirigida** (`metadados`, `versao_candidatos`). O registro versionado de candidatos (`concursos.analytics.candidatos_edital`, `VERSAO_CANDIDATOS`) declara, para cada candidato, a informação, os padrões de busca, o uso no projeto, o impacto (`alto`, `medio`, `baixo`), o status (`aplicado`, `proposto` ou `descartado`) e a severidade quando ausente. Mudar um candidato sobe a versão. Cada concurso tem um metadado por candidato, na ordem do registro, e nenhum some da saída. O metadado é um campo com mais duas chaves:

- `chave`: a do candidato (`alternativas`, `desempate`, `validade`…);
- `status`: `encontrado`, `nao_encontrado` ou `ambiguo`. Ambíguo é o candidato de valor único (alternativas, tipo de questão, validade) com valores diferentes no edital; o `valor` vira a lista deles.

Encontrado, o metadado tem fonte `descoberta` (ou `retificacao`), trecho, documento e página; a busca respeita o escopo do cargo, e uma retificação que o traz vence o edital. Os candidatos sem padrão são derivados das regras já extraídas: corte em acertos ao lado de nota ponderada (CPNU 8.15), teto de classificados (TCU 8.11.5) e soma dos pesos dos eixos (CPNU 8.9.2). O `desempate` tem extração própria: o `valor` é a lista de critérios na ordem das alíneas ("terá preferência o candidato que, na seguinte ordem: a) …"), da lista do cargo, com o "(P ); 2" do PDF lido como "(P2)". Quando o edital traz o número de alternativas e o gabarito usa outra última letra (por exemplo, 5 alternativas e gabarito só até D), o CSV de discrepâncias ganha um `error` (`alternativas`, `A a E` contra `A a D`).

**Catálogo de descobertas** (`catalogo_edital.md`). Gerado do registro e dos metadados, um por concurso, com este template:

```markdown
# Catálogo do edital: <nome oficial>, <cargo> – <especialidade>

Concurso `<slug>`; registro de candidatos na versão <n>. "(descoberta)" marca o que veio além da lista inicial de candidatos.

## Descobertas

| Informação | Valor | Trecho de origem | Uso no projeto | Impacto | Status | No edital |
|---|---|---|---|---|---|---|
| Número de alternativas | 5 | «… contendo 5 (cinco) alternativas cada …» (p. 29, edital.pdf) | Confere o gabarito … | alto | aplicado | encontrado |
| Bibliografia | – | – | Fontes de estudo indicadas | baixo | proposto | não encontrado (info) |

## Propostas de evolução

- **<informação>** (<status>): <proposta, com o diff estimado>

## Descartados

- **<informação>**: <motivo>
```

- **Propostas de evolução:** os candidatos de impacto alto com proposta. A que muda código de uma fase anterior (o número de alternativas no OCR da folha) fica só como proposta, com o diff estimado, e só é aplicada com confirmação.
- **Descartados:** os candidatos descartados e as informações que nem viraram candidato (taxa, remuneração, jornada, lotação, cotas, isenção, atendimento especial, nome social, amamentação, heteroidentificação, perícia médica), cada um com o motivo.

## `concurso.yaml`

O arquivo é gerado por `concursos adicionar` e pode ser editado à mão. Os caminhos são relativos à pasta do concurso.

```yaml
nome: tcu_25
banca: cebraspe                # cebraspe | fgv | selecon | quadrix
formato: certo_errado          # multipla_escolha | certo_errado
pontuacao: cebraspe            # simples | cebraspe (padrão: simples)
cargo: 'CARGO 2: AUDITOR ...'  # obrigatório quando o gabarito tem várias seções
tipo: '1'                      # tipo/versão do caderno, quando houver
edital: edital.pdf             # ou a forma completa:
# edital:
#   arquivo: edital.pdf        # opcional se houver manual
#   anexos: [anexo_ii.pdf]     # lidos antes do edital principal
#   manual: edital_manual.yaml # tem prioridade sobre os PDFs
#   retificacoes: [ret_2.pdf, ret_3.pdf]  # na ordem de publicação; só para as regras do edital
provas:
  cb:
    caderno: prova_cb.pdf      # opcional; usado para disciplinas e tópicos
    gabarito:                  # ou só o nome do arquivo (status definitivo)
      arquivo: gabarito_cb.pdf
      status: preliminar       # preliminar | definitivo
    itens: [1, 100]
    disciplinas:               # opcional; sobrepõe os cabeçalhos do caderno
      - {inicio: 1, fim: 20, disciplina: Língua Portuguesa}
  ce:
    gabarito: {arquivo: gabarito_ce.pdf, status: definitivo}
    itens: [101, 200]
respostas:                     # use 'arquivo' OU 'folha'
  folha: folha_resposta.pdf
  template: cebraspe_ce        # cebraspe_ce | fgv_mod70ae | fgv_cpnu_90
  total_itens: 200
  itens_por_coluna: 20         # opcional; detectado pela grade
# respostas:
#   arquivo: respostas.txt
data_prova: 2026-02-22         # opcional; ISO 8601, prevalece sobre a data provável do edital
nivel: federal                 # opcional; federal | estadual | municipal (padrão: nao_informado)
escolaridade: superior         # opcional; superior | medio (padrão: nao_informado)
resultado_oficial:             # opcional
  arquivo: resultado.pdf
  identificador: '12345678'    # inscrição do candidato
  pesos:                       # opcional; peso por faixa de itens
    - {itens: [101, 200], peso: 2}
correcao:                      # opcional; complementa ou substitui a regra extraída do edital
  modelo: liquida              # bruta | liquida | ponderada (liquida exige fator > 0; as outras, fator 0)
  fator_penalidade: 1          # acertos anulados por erro
  nota_maxima: 200             # padrão: soma dos pesos dos itens
  nota_corte: 60               # nota mínima no conjunto das provas objetivas
  pesos:                       # opcional; mesmo formato dos pesos do resultado oficial
    - {itens: [101, 200], peso: 2}
  variantes:                   # opcional; uma configuração de correção por opção de cargo
    - B3-08-A                  # pesos lidos do quadro de pesos do edital
    - nome: B3-10-A
      pesos:                   # sobrescrevem o quadro do edital
        - {itens: [31, 42], peso: 1}
ignorar: [gabarito_prel.pdf]   # arquivos da pasta que não são usados
historico:
  - {data: '2026-10-19', tipo: gabarito_definitivo, prova: cb, anterior: gabarito_prel.pdf, novo: gabarito_cb.pdf}
```

Todo arquivo da pasta precisa aparecer no `concurso.yaml` (num campo ou em `ignorar`). Caso contrário, o concurso fica `desatualizado`. Ficam de fora dessa regra:
- a pasta `revisao/`;
- arquivos `.yaml`;
- compactados;
- arquivos `:Zone.Identifier`.

## Taxonomia de disciplinas

A `taxonomia.yaml`, na raiz do projeto, é escrita e revisada à mão. Ela mapeia cada nome de disciplina, como aparece nos `questoes.csv`, para uma **disciplina canônica**. Assim, a mesma matéria é comparada entre editais que usam nomes diferentes:

```yaml
Raciocínio Lógico:
  bloco: geral                 # geral | especifico
  nomes:                       # o próprio nome canônico já está incluído
    - Raciocínio Lógico Matemático
    - Raciocínio Análitico
```

- **Nomes:** um nome só pode aparecer em uma disciplina canônica. A taxonomia não tem fallback: um nome ausente reprova a validação do consolidado, com a lista dos nomes que faltam. A disciplina `nao_mapeado`, das questões que o pipeline não classificou, passa direto, sem entrada na taxonomia.
- **Bloco:**
  - Nas provas divididas, o bloco vem da própria prova: `cg` e `cb` são `geral`, e `ce` é `especifico`.
  - Na prova única, vem do bloco da disciplina canônica. Uma questão `nao_mapeado` em prova única fica com bloco `nao_informado`.
- **Identidade de tópico** (`chave_topico`): a disciplina canônica mais as palavras-chave do nome do tópico, sem acento, caixa ou palavras vazias, em ordem alfabética. É a mesma normalização do comparativo entre concursos. Por exemplo, "Emprego do sinal indicativo de crase" e "EMPREGO DO SINAL INDICATIVO DA CRASE", ambos em Língua Portuguesa, têm a mesma chave.

Editar a taxonomia reconstrói o consolidado na próxima carga.

## Edital manual

Use quando o conteúdo programático não puder ser extraído do PDF, ou para corrigir a estrutura extraída. O caminho vai em `edital.manual`.

```yaml
cargo: Analista de TI          # opcional
conhecimentos:
  - nome: Conhecimentos Gerais
    disciplinas:
      - nome: Língua Portuguesa
        peso: 1                # opcional
        topicos:
          - Compreensão e interpretação de textos
          - nome: Domínio da ortografia
            descricao: Domínio da ortografia oficial. Emprego da crase.  # usada na similaridade
            peso: 2            # opcional
```

## Revisão de tópicos

O arquivo `provas/<concurso>/revisao/questoes_revisado.csv` é criado na primeira análise com edital e nunca é sobrescrito. Colunas:

- `questao`, `prova`;
- `disciplina_sugerida`, `topico_sugerido`, `score`;
- `enunciado` (trecho);
- `disciplina`, `topico` (para o usuário preencher).

Células não vazias em `disciplina` e `topico` têm prioridade sobre a sugestão. Editar o arquivo dispara o reprocessamento.

## Contratos de saída

Por concurso, em `analises/<concurso>/`:

- **`respostas_extraidas.csv`:** uma linha por questão, sem exceção. Colunas:
  - `concurso`, `prova`, `questao`;
  - `alternativa_marcada`, `estado`;
  - `confianca_ocr`, `revisar`;
  - `origem`, `arquivo`, `pagina`.
- **`desempenho_por_disciplina.csv` e `desempenho_por_topico.csv`:** colunas `concurso, prova, disciplina, topico, total, acertos, erros, percentual, em_branco, anuladas, nota_liquida`. No arquivo por disciplina, `topico = todos`. Sempre vale `acertos + erros + em_branco = total`.
- **`questoes.csv`:** colunas:
  - `questao`, `prova`, `disciplina`;
  - `topico_sugerido`, `score`, `topico`, `revisado`;
  - `gabarito`, `anulada`, `resposta`, `resultado`.
- **`diff_gabarito.csv`** (após a troca de gabarito): colunas:
  - `prova`, `questao`;
  - `gabarito_preliminar`, `gabarito_definitivo`;
  - `mudanca` (`alterada | anulada`);
  - `resposta`, `acerto_antes`, `acerto_depois`.
- **`edital_estruturado.json`:** `fonte`, `cargo` e `conhecimentos[].disciplinas[].topicos[]`. Cada tópico tem `numero`, `nome`, `descricao` e `peso`. Quando há PDF do edital, o arquivo ganha as [regras do edital](#regras-do-edital-fase-3) (`identificacao`, `avisos` e os blocos descritos lá). Cada parte grava só as próprias chaves e preserva as outras.
- **`discrepancias_edital.csv`:** uma linha por divergência entre o edital e a prova, com as colunas `item, esperado_edital, observado_prova, diferenca, severidade, acao_sugerida`. A `severidade` é `info`, `warn` ou `error`; a `diferenca` fica vazia quando não é numérica. Só existe quando há PDF do edital, e fica só com o cabeçalho quando tudo confere.
- **`catalogo_edital.md`:** o catálogo de descobertas do edital (template em "Regras do edital"). Só existe quando há PDF do edital.
- **`correcao.json`:** lista de configurações de correção (uma por variante; uma só quando o concurso não tem variantes). Campos:
  - `modelo`, `fator_penalidade`, `nota_maxima`, `nota_corte`;
  - `pesos`: lista de `{inicio, fim, peso}` (vazia quando todos os itens valem 1);
  - `fonte` (`edital | config | default`), `confianca`;
  - `trecho_origem`, `documento_origem`, `pagina_origem` (preenchidos quando a fonte é o edital);
  - `variante` (`null` quando o concurso não tem variantes);
  - `data_prova` (ISO 8601 ou `null`) e `fonte_data` (`edital | config`, `null` sem data), iguais em todas as variantes.
- **`validacao_oficial.json`:** `arquivo`, `descricao` e `alerta`. Só existe quando há resultado oficial.
- **`relatorio.md` e `graficos/*.png`:** o relatório, com a nota final abaixo do resumo por prova quando o modelo é `liquida` ou `ponderada`; os gráficos ficam na pasta indicada.
- **`historico/<data>_gabarito_preliminar/`:** cópia das saídas anteriores à troca de gabarito.

No consolidado, em `analises/consolidado/`:

- **`desempenho_geral.csv`:** junção dos `desempenho_por_topico.csv` de todos os concursos analisados, com as mesmas colunas.
- **`comparativo_concursos.md`:** reúne:
  - desempenho e status do gabarito por concurso, com a coluna `nota_final` (`-` no modelo `bruta`; com variantes, uma por variante);
  - tópicos e disciplinas abaixo de `limiar_topico_baixo` em pelo menos dois concursos (nomes comparados por palavras-chave);
  - concursos incompletos ou desatualizados, com o motivo;
  - validação com o resultado oficial.
- **`consolidado.parquet`:** cache da análise evolutiva (`concursos.analytics.consolidado`), com uma linha por questão de cada concurso que tem `questoes.csv`, `correcao.json` e `concurso.yaml`. É reconstruído quando um `questoes.csv`, `correcao.json`, `concurso.yaml` ou a `taxonomia.yaml` fica mais novo que ele, ou quando o conjunto de concursos analisados muda. Colunas:
  - de `questoes.csv`: `concurso` (nome da pasta), `prova`, `questao`, `disciplina` (nome bruto), `topico`, `gabarito`, `anulada`, `resposta`, `resultado` (`acerto | erro | branco`);
  - da [taxonomia](#taxonomia-de-disciplinas): `disciplina_canonica`, `bloco` (`geral | especifico | nao_informado`) e `chave_topico`;
  - do `concurso.yaml`: `formato`, `banca`, `cargo`, `nivel` (`federal | estadual | municipal | nao_informado`), `escolaridade` (`superior | medio | nao_informado`);
  - do `correcao.json` (a primeira configuração, quando há variantes): `data_prova` (data, vazia sem data), `modelo_correcao` (`bruta | liquida | ponderada`), `fator_penalidade`, `nota_maxima`, `nota_corte` (vazia sem corte), `fonte_correcao` (`edital | config | default`), `confianca_correcao`;
  - `pontos_bruta`, `pontos_corrigida` e `pontos_ajustada`: a pontuação por item da tabela acima, sem peso, vazia nas anuladas;
  - `peso__<variante>`: o peso do item em cada variante (`peso__padrao` quando o concurso não tem variantes), vazio nos concursos sem aquela variante;
  - `ordem`: posição cronológica do concurso pela data da prova, a partir de 1 (datas iguais empatam), vazia sem data;
  - `n_topico`: quantidade de questões do tópico naquela prova (o `total` de `desempenho_por_topico.csv`).

  `validar_schema` confere colunas, tipos, domínios, nomes de disciplina sem mapeamento na taxonomia, a existência de ao menos uma coluna `peso__` e o número de linhas igual à soma das linhas de todos os `questoes.csv` (um concurso analisado que ficou fora reprova a contagem).
