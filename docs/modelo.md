# Modelo de domínio

Este documento descreve as entidades do domínio, o schema do `concurso.yaml`, o formato do edital manual e os contratos dos arquivos de saída.

## Entidades

**Concurso.** É uma pasta em `provas/<concurso>/` com um `concurso.yaml`. Tem:
- nome;
- banca: `cebraspe`, `fgv`, `selecon` ou `quadrix`;
- formato: `multipla_escolha` (A–E) ou `certo_errado` (C/E);
- regra de pontuação;
- cargo e tipo do caderno;
- edital (obrigatório: o PDF ou o `edital.manual`);
- uma ou mais provas;
- a fonte das respostas;
- o resultado oficial (opcional);
- o histórico de eventos.

A situação é derivada: `completo`, `incompleto` (falta o edital, as respostas ou um arquivo obrigatório, com o caminho) ou `desatualizado` (arquivo novo não cadastrado ou configuração inválida). Caderno ou resultado oficial ausente só gera aviso: o concurso continua completo, e a análise segue sem o texto das questões ou sem a conferência da nota.

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

**Gabarito.** É o arquivo de uma prova, com status `preliminar` ou `definitivo` (`StatusGabarito` em `modelo.py`; o yaml grava o texto). Cada item tem questão, resposta e se foi anulado (`X` ou `*`). Um PDF pode ter várias seções (cargo e tipo); a seção é escolhida pelo `cargo`/`tipo` do concurso.

**RespostaMarcada.** É a leitura de uma questão. Tem:
- alternativa (ou vazio);
- estado: `marcada`, `branco` ou `multipla`;
- confiança (0–1; 1 no `respostas.txt` e nos CSVs de respostas);
- origem: `folha`, `manual` (`respostas.txt` ou CSV manual) ou `revisada` (CSV de leitura corrigido e aplicado com `--reuse-csv`);
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
- fonte: `edital`, `config`, `perfil` ou `default`;
- confiança da extração (0–1) e o trecho, o documento e a página de onde a regra foi lida;
- variante: o código do cargo, quando o concurso tem várias opções com pesos diferentes (CPNU).

A regra é extraída por regex do texto dos documentos do edital (anexos primeiro, sem OCR). Os padrões reconhecidos são:
- penalidade explícita ("1,00 ponto negativo … discordância"), erro que vale zero ("0,00 ponto, caso a resposta … em discordância", fator 0) e fracionária ("a cada N erradas, anula-se uma certa", fator 1/N);
- pontos diferentes por prova ou módulo (creci: "1,00 ponto … conhecimentos básicos; 2,00 pontos … específicos"; dataprev: "valerá 1 ponto no Módulo de Conhecimentos Gerais, e 2,5 pontos no Módulo de Conhecimentos Específicos"). Os gerais vêm antes dos específicos, e quantos itens tem cada parte sai do número de itens do concurso e da nota máxima do edital; sem solução inteira, o padrão é ignorado;
- nota igual ao total de acertos, "valendo 1 ponto cada questão" ou "cada acerto valerá 1 ponto", sem menção a desconto (`bruta`);
- o quadro de pesos por eixo temático e cargo (CPNU), descrito abaixo em variantes.

A precedência é edital, depois `concurso.yaml`, depois o [perfil da banca](#perfis-de-banca-fase-4), depois default (`bruta`, fator 0). O perfil só entra quando é de outra banca que não a `generic` e tem o mesmo `formato` do concurso; a regra sai com fonte `perfil`, confiança 0,5 e um aviso no log e no consolidado ("regra de correção do perfil da banca"). Pesos, nota máxima e nota de corte seguem a mesma ordem, campo a campo. Sem nota máxima em nenhuma fonte, ela é a soma dos pesos dos itens (o número de itens quando não há pesos).

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

\(f\) é o fator de penalidade, e \(k\) é o número de alternativas: 2 em `certo_errado` (erro vale −1) e, em `multipla_escolha`, o `alternativas` do `concurso.yaml`, o do perfil da banca ou 5 (erro vale −0,25; com 4 alternativas, −1/3). A versão ajustada é a métrica padrão para comparar concursos, porque um chute puro vale 0 nos dois formatos.

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
- **Fracos persistentes:** tópicos abaixo do limiar (padrão 60%; o notebook passa o `limiar_topico_baixo` do `config.toml`, o mesmo do comparativo da fase 1) em pelo menos 2 concursos, com acertos, erros e brancos somados entre concursos e n agregado ≥ 5. O n de cada concurso não importa, porque só a soma dá amostra. O percentual agregado é a média dos itens de todos os concursos.

**Insights e relatório de evolução** (`concursos.analytics.insights`).

- **Meta** (`comparar_com_meta`, em `evolucao`): por concurso e variante, a nota pela regra do edital (peso da variante, anulada vale ponto), a nota de corte, a nota normalizada (0–100 da nota máxima, truncada em 0) e a distância até a meta (padrão 70%), em pontos percentuais.
- **Nota ponderada** (`nota_ponderada_por_disciplina`, em `evolucao`): por concurso, variante, bloco e disciplina canônica, `nota_ponderada = Σ peso × acerto`, sem desconto do erro e com a anulada contando como acerto; `nota_maxima = Σ peso` e `percentual_ponderado = 100 × nota_ponderada / nota_maxima`.
- **Gap para o corte** (`gap_para_corte`, em `evolucao`): recebe os cortes do edital estruturado (`cortes_por_concurso`, em `consolidado`) e devolve uma linha por corte aplicável de cada concurso e variante; no escopo `disciplina`, uma por disciplina (do `bloco` do corte, ou de todos). O corte da discursiva fica de fora.
  - Nota no escopo, na unidade do corte: em `pontos`, `Σ peso × pontos corrigidos`, com a anulada valendo 1; em `acertos`, a contagem de acertos mais as anuladas.
  - Nota máxima do escopo: `Σ peso` em pontos e o número de itens em acertos.
  - `gap = nota − corte` (positivo acima do corte), `gap_percentual = 100 × gap / nota máxima do escopo` (pontos percentuais) e `satisfeito = gap ≥ 0`.
  - `atingido` só é verdadeiro quando todos os cortes da variante são satisfeitos: passar no conjunto não basta se um bloco ou uma disciplina fica abaixo.
- **Concurso-alvo:** `concurso_alvo` no `config.toml` (nome da pasta do concurso, opcional) restringe as duas funções acima, a simulação e o desempate a esse concurso. Sem ele, saem todos.
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
- **Carregamento:** `regras_por_concurso` (em `consolidado`) lê o edital estruturado de cada concurso analisado que já tem as regras, e `cortes_por_concurso` tira delas os cortes.
- **Correlação geral** (`correlacao_tempo_percentual`, em `evolucao`): Spearman entre a ordem e o percentual ajustado de cada concurso. É a medida única de tendência geral; a média dos z-scores de um concurso não serve, porque fica perto de 0 por construção.
- **Achados:** melhoras e pioras são as tendências por disciplina com p < 0,05; os fracos usam o limiar do `config.toml`; o ranking muda quando alguma linha tem deslocamento no corrigido ou no ajustado.
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
- `fonte`: `retificacao`, `edital`, `config`, `perfil`, `default`, `descoberta`, `llm` ou `pci` (só no nome do concurso, pelo título do PCI);
- `trecho_origem`, `documento_origem` e `pagina_origem`, sempre preenchidos quando a fonte é `retificacao`, `edital` ou `descoberta`;
- `confianca_extracao`, de 0 a 1;
- `camada`, só no JSON: `heuristica` (fontes `retificacao`, `edital` e `descoberta`), `llm`, `perfil`, `config` ou `nenhuma` (`default`).

A precedência é retificação, depois edital, depois configuração, depois perfil da banca (só nos campos que o perfil traz), depois default. Um campo que cai no default fica com `valor` nulo, e o motivo vai para `avisos` (lista de textos) e para o log. O `correcao.json` continua sendo a fonte da regra de correção aplicada; as regras do edital são a expectativa.

**Confiança do edital** (`confianca_edital`, `{valor, nivel}`). Agrega os campos essenciais: cargo, formato, penalidade, total da distribuição, data da objetiva, tipo de pesos, o melhor corte calculável fora da discursiva e, em múltipla escolha, as alternativas. O `valor` é a soma das confianças dos essenciais que vieram do texto (edital, retificação, descoberta ou LLM com citação) dividida pelo número de essenciais, com 2 casas. O `nivel` é `alta` a partir de 0,8, `media` a partir de 0,5, `baixa` abaixo disso e `minima` quando nenhum essencial veio do texto (`valor` 0).

**Modo mínimo e `edital_a_confirmar.yaml`.** Um edital sem conteúdo programático (texto sem a seção, ou PDF imagem sem o Tesseract) não aborta a análise: o log avisa com uma `dica:` (instalar o Tesseract com o idioma português, rodar `concurso-analise doctor` ou fornecer `edital.manual`), e as questões ficam com tópico `nao_mapeado`. Depois das regras, faltando algum destes campos, a análise grava `provas/<concurso>/edital_a_confirmar.yaml` e avisa no log:

- `data_prova`: a correção ficou sem data;
- `alternativas`: múltipla escolha com alternativas no default;
- `fator_penalidade`: regra de correção no default;
- `nota_corte`: nenhum corte calculável fora da discursiva.

O arquivo traz um cabeçalho, a lista do que foi extraído (ou "Nada foi extraído do edital") e, para cada campo, um comentário e a chave vazia. Já existindo, só ganha as chaves que faltam; o que o usuário escreveu fica. O usuário preenche os valores pela tela de conferência ("Conferir" no card do concurso, aba "Dados do edital"); ver [Conferência pela tela](#conferência-pela-tela). Na próxima análise, os valores preenchidos entram como se estivessem no `concurso.yaml` (fonte `config`; `fator_penalidade` e `nota_corte` dentro de `correcao`), e o `concurso.yaml` vence quando os dois trazem o campo. Chave desconhecida ou valor inválido param a análise com o nome do arquivo.

**Retificações.** Há duas formas de um valor sair com fonte `retificacao`:

- **PDF de retificação:** o arquivo é declarado em `edital.retificacoes` e lido só pelas regras do edital (o conteúdo programático e a correção não o veem). A busca percorre as retificações da mais recente para a mais antiga, e só depois o edital e os anexos. O valor encontrado numa retificação vence o do edital, campo a campo, com o trecho e o documento da retificação. A ordem dos cortes continua a do edital.
- **Nota inline no edital consolidado:** a frase do trecho é seguida da nota "(Retificado por meio do Edital nº …)", antes do próximo subitem e com no máximo um fim de frase entre as duas. O documento de origem continua sendo o edital.

**Identificação** (`identificacao`). Tem os campos `nome_oficial` (o órgão na capa), `edital` (a linha "EDITAL Nº …" da capa), `cargo`, `especialidade`, `vagas`, `cadastro_reserva` e `teto_classificados`, mais `cargo_casado` (lógico), `cargos_do_edital` (lista), `sigla` e `ano`. O cargo vem do edital:

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
- `unidade`: `pontos` (nota líquida, Cebraspe), `acertos` (FGV e CPNU), `percentual` (0 a 100 do máximo do escopo), `nota_0_10` (escala de 0 a 10), `escore_padronizado` ou `classificados`. As duas últimas dependem das notas dos outros candidatos: não são calculáveis localmente, ficam fora do gap e do "atingido", geram aviso e aparecem nas peculiaridades como "Corte não calculável". O `valor` do corte por classificados fica vazio;
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
| "ter acertado, no mínimo, 30 pontos na prova de Conhecimentos Específicos" (IBFC) | `especifico`, 30 pontos |
| "obtiver NP < 15,00 pontos", "NFPO < 40,00 pontos" (fórmula do TSE) | `geral` e `conjunto` |
| "não tenha obtido nota igual a 0,00 em qualquer uma das disciplinas" | `disciplina`, 1 acerto, todas |
| "nota mínima … igual ou superior a 5,00", com a "escala de 0 a 10" no edital (sem ela, `pontos`) | `conjunto`, `nota_0_10` |
| "no mínimo, 50% … em cada bloco", "mínimo, 60% … da prova objetiva" (FCC, Vunesp) | `percentual`, por bloco ou `conjunto` |
| "somatório das notas padronizadas … igual ou superior a N" (Vunesp) | `conjunto`, `escore_padronizado` |
| "considerados aprovados nas provas objetivas os candidatos … mais bem classificados" (Cebraspe) | `conjunto`, `classificados` |

Cortes "no bloco I" (escrivão da PF) não são lidos. Percentual e `nota_0_10` viram nota na escala do corte: escala × pontos ÷ máximo do escopo. Para cada escopo e bloco (e, nos não calculáveis, unidade), vale o primeiro na ordem de busca, então a retificação vence o edital. O corte da discursiva é só informativo: o projeto não tem a nota discursiva, e ele fica fora do "atingido".

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

O quadro de eixos do CPNU dá `por_faixa_de_itens`, uma entrada por variante do `correcao.variantes`, com a faixa dos conhecimentos gerais primeiro. Sem quadro, vale a regra de pontuação que a correção também lê: pontos diferentes por parte são `por_bloco`. Depois vêm os pesos por prova, `por_bloco` com confiança 0,8: pontos por item de cada prova (TSE), "questão de conhecimento comum … específico" (Fortaleza), "peso N à nota da prova de conhecimentos gerais; peso M …" (TRT-6), "questões, com pesos A e B" (EMPARN), "N questões de conhecimentos gerais, que valerão P pontos" (STN) e o quadro de pontos por prova do IBFC (TRF-5). As faixas saem quando as quantidades dos dois blocos somam o total de itens; pesos iguais nos dois não dão `por_bloco`. Por fim, pontos iguais em todos os itens são `uniforme` (Cebraspe, AgSUS, CPRM). Sem nada disso, há aviso. O CSV de discrepâncias ganha duas regras:

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

**Prova** (`prova`). Três campos sobre o formato da prova objetiva, com a mesma precedência dos outros (edital, configuração, perfil da banca, default):

- `formato`: `certo_errado` ou `multipla_escolha`, lido do edital ("julgamento de itens … CERTO ou ERRADO", "múltipla escolha"; com só o número de alternativas, múltipla escolha com confiança 0,7). Sem menção, o `formato` do `concurso.yaml` (fonte `config`);
- `alternativas`: "cinco alternativas", "5 (cinco) opções"; vazio em certo/errado. Sem a menção no edital, `alternativas` do `concurso.yaml`, depois o perfil e, por fim, 5 (fonte `default`);
- `penalidade`: o fator que a correção leria do edital; sem ele, o do `concurso.yaml`, depois o do perfil (mesmo formato), depois 0.

**Metadados e descoberta dirigida** (`metadados`, `versao_candidatos`). O registro versionado de pistas do edital (`concursos.analytics.pistas_edital`, `VERSAO_CANDIDATOS`) declara, para cada pista, a informação, os padrões de busca, o uso no projeto, o impacto (`alto`, `medio`, `baixo`), o status (`aplicado`, `proposto` ou `descartado`) e a severidade quando ausente. Mudar uma pista sobe a versão. O campo serializado `versao_candidatos` no JSON não muda de nome. Cada concurso tem um metadado por pista, na ordem do registro, e nenhum some da saída. O metadado é um campo com mais duas chaves:

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

## Pastas de uma execução (fase 4)

O resolvedor de contexto (`config/contexto.py`) decide todos os caminhos; nada mais procura o `pyproject.toml`.

| Pasta | Padrão | Sobreposta por |
|---|---|---|
| Global (preferências, logs, backups) | `~/.concurso/` | `CONCURSO_HOME` |
| Projeto (configuração e taxonomia) | `./.concurso/` | `--data-dir` |
| Provas | `./provas/` | `--provas` |
| Análises | `./analises/` | `--analises` |

O log técnico, com traceback, fica em `<global>/logs/concurso-analise.log` (rotativo, 3 cópias de 1 MB). Na tela, um erro sai em até duas linhas: `erro: <causa>` e `dica: <comando>`. Códigos de saída: 0 sucesso, 1 falha do usuário ou dos dados, 2 falha do ambiente ou uso inválido da CLI.

Pastas de provas e análises também podem vir da seção `[pastas]` do `config.toml` do projeto, sobrepostas por `CONCURSO_PROVAS`, `CONCURSO_ANALISES` e pelas flags `--provas` e `--analises`.

## `config.toml` do projeto

Fica em `./.concurso/config.toml` (ou em `--data-dir`). A taxonomia fica ao lado, em `./.concurso/taxonomia.yaml`.

```toml
[pastas]
provas = "provas"
analises = "analises"

[analise]
limiar_confianca = 0.75
limiar_topico_baixo = 0.6
concurso_alvo = "tcu_25"   # opcional; nome da pasta do concurso
incluir_simulados = false  # true: os simulados do PCI entram no consolidado e nas tendências
```

- **Validação:** os campos de `[analise]` são os mesmos do `config.yaml` antigo. Campo desconhecido ou valor fora de 0 a 1 (nos limiares) gera erro citando o campo e as opções.
- **Escrita pela GUI:** a tela de configurações grava `limiar_confianca`, `limiar_topico_baixo` e `concurso_alvo` por `aplicacao.preferencias.gravar_analise`, com a mesma validação; as outras chaves e seções ficam como estavam (os comentários do arquivo se perdem, como em toda gravação do `config.toml`).
- **Precedência:** flag, variável de ambiente, `config.toml`, padrão.
- **`[candidato] ultimo`:** o último candidato analisado; vale quando não há `--candidate` nem `CONCURSO_CANDIDATO`.
- **`[migracao]`:** o registro da migração das fases 1 a 3 (`versao = 4`, `candidato`, `backup`, `data`).
- **`[pratica]`:** a prática no TEC (opcional); veja "Prática no TEC (tec-erros)".
- **`[dicionario]`:** `usar` (booleano; sem a chave, o dicionário vale quando o arquivo existe) e o resumo do último teste de ganho, gravado pelo app: `antes` e `depois` (taxas de 0 a 1), `n`, `data` (ISO) e `alerta`; veja "Dicionário de temas".
- **`incluir_simulados`:** booleano; veja "PCI Concursos opcional".

## Onboarding (fase 4)

Roda no comando sem subcomando quando o projeto não tem `config.toml`, e sempre com `init`. As perguntas saem com `[n/total]` e o padrão entre colchetes; Enter aceita o padrão.

| Pergunta | Padrão | Flag | Variável |
|---|---|---|---|
| nome | o do candidato atual; sem ele, o único candidato das provas ou o login | `--candidate` | `CONCURSO_CANDIDATO` |
| pasta de provas | a resolvida pelo contexto | `--provas` | `CONCURSO_PROVAS` |
| pasta de análises | a resolvida pelo contexto | `--analises` | `CONCURSO_ANALISES` |
| folha para calibrar e as respostas das 5 primeiras questões | pular | `init --calibrate-sheet` e `--calibrate-answers` | `CONCURSO_CALIBRAR_FOLHA` e `CONCURSO_CALIBRAR_RESPOSTAS` |
| LLM para editais (`nenhum`, `openai`, `openrouter`, `gemini`, `ollama`, `anthropic`) | o atual ou `nenhum` | — | `CONCURSO_LLM` |
| rodar o `doctor` no fim | sim | `init --doctor/--no-doctor` | `CONCURSO_DOCTOR` |

- **Só o que falta:** o que veio por flag ou variável não é perguntado.
- **Sem perguntas:** sem TTY, com `CI` ou com `--yes`, ficam os padrões, listados no log. Sem a pasta de provas, para com a `dica:` de sempre.
- **Pasta de provas ausente:** o wizard oferece criá-la com um `LEIA-ME.txt` que explica o que pôr nela; criada vazia, a análise fica para a próxima execução.
- **Resumo:** antes de gravar, lista o que será gravado e pede confirmação; recusar sai com 1 sem gravar nada.
- **Ordem:** migração das fases 1 a 3 (com o candidato respondido), depois a gravação, o `doctor` e a análise (forçada quando houve calibração).
- **Calibração:** detecta a grade da folha de amostra sem perfil, deduz o número de alternativas do espaçamento entre as colunas de bolhas (maior entre itens do que dentro de um item) e mede a tinta das 5 primeiras questões da primeira coluna. As respostas digitadas (letra ou `-`, sem diferença de caixa) separam as bolhas em marcadas e vazias: `vazio` e `cheio` são as medianas de cada grupo, e `limiar_marcada` fica no meio entre a marcada mais fraca e a vazia mais forte, na escala de 0 a 1 entre `vazio` e `cheio` (limitado a 0,05 a 0,95). Reprova, sem gravar nada, quando uma letra digitada não existe na grade, quando uma bolha digitada tem menos tinta que uma não digitada, ou quando todas estão em branco; no wizard interativo, mostra o erro com a `dica:` e pergunta de novo; por flag ou variável, para com código 1.
- **Perfil calibrado:** `./.concurso/folha_calibrada.yaml` (`id: calibrado`, `alternativas`, `vazio`, `cheio`, `limiar_marcada`) e a imagem `./.concurso/calibracao.png`. Na leitura, os limiares dele substituem os padrão da detecção automática (sem `template` ou quando o perfil da folha falha); o perfil de OCR do `template` continua vindo antes.
- **LLM:** ao escolher um provedor pela primeira vez, o wizard diz o que vai para ele (só o texto do edital e dos anexos) e pede concordância; sem ela, fica `nenhum`. Sem a chave, diz qual variável definir; com a chave só na variável, oferece guardá-la no keyring.
- **O que grava:** no projeto, `[pastas]` (relativas à raiz quando dentro dela) e `[candidato] ultimo`; o perfil global `~/.concurso/candidatos/<slug>.toml` com o nome digitado; e, na configuração global `~/.concurso/config.toml`, `[candidatos] conhecidos` (lista de slugs) e `[llm]` (`provedor`, `url`, `modelo`, `variavel_chave`, `consentimento` e, na fase 7, `consentimento_livros`). A chave de API nunca vai para o TOML.

## LLM opcional (fase 4)

Desligado por padrão; nenhuma chamada de rede acontece sem `[llm]` com `consentimento = true` na configuração global. `--no-llm` e `--offline` (flags globais, antes do subcomando) o desligam numa execução.

- **Clientes** (`concursos.llm`): um compatível com OpenAI (`POST <url>/chat/completions`), que serve OpenAI, OpenRouter, Gemini e Ollama, e um adaptador Anthropic (`POST <url>/messages`). Timeout de 60 s, sem nova tentativa; uma falha vira aviso e a análise segue sem o LLM.
- **Chave:** a variável de `variavel_chave`, depois o keyring (serviço `concurso-analise`, extra `llm`), depois o `~/.concurso/.env` (`VARIAVEL=valor`). Guardar sem keyring grava o `.env` com permissão 600 e aviso de texto plano; ler um `.env` legível por outros também avisa. Sem chave, o aviso diz qual variável definir, e o `doctor` mostra `✗` com o `export`.
- **Camada** (`concursos.edital_llm`): depois das regras do texto, pede só os campos que caíram no perfil da banca ou no padrão, o que poupa a rede quando o edital foi lido: `alternativas` (múltipla escolha), `penalidade` e `data_prova` (a data da objetiva no cronograma). O que vem do texto do edital ou do `concurso.yaml` nunca é trocado. Vão só páginas do edital e dos anexos que tenham palavras dessas regras, com o documento e a página, até 40 mil caracteres.
- **Citação:** a resposta é um JSON com `{"valor", "trecho_origem"}` por campo. O trecho precisa existir numa página do texto enviado, comparando sem acento, sem caixa e com espaços normalizados; sem isso, ou com valor fora do esperado (alternativas de 2 a 10, penalidade de 0 a 1, data ISO), o valor é descartado e o campo fica como estava. Aceito, o campo sai com fonte e camada `llm`, confiança 0,6, trecho, documento e página.
- **Só regras do edital:** o valor do LLM é expectativa, como o resto do `edital_estruturado.json`; a correção segue com o `correcao.json`.

## open-notebook opcional

Desligado por padrão; nada sai da máquina sem `[open_notebook]` com `enabled = true` e `consentimento = true` na configuração global, gravados por `concurso-analise notebook enable` depois de mostrar o que vai. `--offline` e `--dry-run` desligam a sincronização numa execução. Comandos e decisões em `docs/spec-open-notebook.md`.

```toml
[open_notebook]
enabled = true
consentimento = true
url = "http://localhost:5055"
variavel_chave = "OPEN_NOTEBOOK_PASSWORD"  # o nome da variável; a senha nunca vai para o TOML
timeout = 120                              # segundos por pedido
incluir_nome = false                       # true: o slug do candidato no nome do notebook e o index.html no consolidado
embed = false                              # true: a instância gera embeddings com o provedor de IA dela
```

- **Campos:** desconhecidos ou de tipo errado levantam `ConfiguracaoInvalidaError`; o `doctor` mostra `✗` com a seção a corrigir e nunca consulta a instância.
- **Senha:** como a chave do LLM: variável, keyring, `~/.concurso/.env`. Vai como `Authorization: Bearer`.
- **Notebooks:** `<concurso> — <rótulo>` com as sources `concurso-analise: <concurso>/<arquivo>` (`relatorio.md`, `desempenho_por_disciplina.csv`, `desempenho_por_topico.csv`, `questoes.csv`, `edital_estruturado.json`, `catalogo_edital.md`) e `Consolidado — <rótulo>` com `concurso-analise: consolidado/<arquivo>` (`desempenho_geral.csv`, `comparativo_concursos.md`, `relatorio_evolucao.md`; `index.html` só com `incluir_nome`). Cada source é `type=text`, começa por `Arquivo: <nome>; concurso: <concurso>` e traz o conteúdo (JSON formatado, HTML sem tags).
- **Nota** `concurso-analise: resumo executivo` (tipo `human`, sem LLM): por concurso, acertos, nota líquida, disciplina mais fraca e mais forte e os tópicos abaixo de `limiar_topico_baixo` com n ≥ `N_MINIMO_TOPICO`; no consolidado, as respostas de `insights` e a nota final pela regra do edital, ou o motivo de faltarem.
- **Rótulo:** `candidato N`, na ordem da primeira sincronização com aquela `url`; com `incluir_nome`, o slug.
- **Estado** `.concurso/open_notebook.json`, gravado só quando muda:

```json
{
  "versao": 1,
  "instancias": {
    "<url>": {
      "pseudonimos": {"<slug>": "candidato 1"},
      "notebooks": {
        "<slug>/<concurso>": {
          "id": "notebook:...", "nome": "<concurso> — candidato 1",
          "sources": {"relatorio.md": {"id": "source:...", "sha256": "..."}},
          "notas": {"resumo": {"id": "note:...", "sha256": "..."}},
          "vinculos": {"source:...": true}
        }
      }
    }
  }
}
```

  O consolidado usa a chave `<slug>/_consolidado`; sem candidato (layout das fases 1 a 3), o slug fica vazio. `vinculos` guarda só as sources de outros notebooks que o app vinculou, e só essas ele desvincula.
- **Idempotência:** hash igual e id presente no remoto, pula; senão apaga (o id do estado e as sources do notebook com o mesmo título, se começar por `concurso-analise:`) e cria. Notebook pelo id do estado, depois pelo nome exato (o mais antigo), depois cria. Nota pelo id ou pelo título, com `PUT` se o hash mudou.
- **Saída:** `notebook sync` imprime o resumo e sai com 0, 1 (alguma falha parcial ou senha recusada) ou 2 (instância fora do ar). No fim da análise, uma falha vira aviso no log e não muda o código de saída.

## PCI Concursos opcional

Desligado por padrão; nada sai da máquina sem `[pci_mcp] enabled = true` na configuração global, gravado por `concurso-analise pci enable` depois de mostrar o que vai (só termos de busca: cargo, UF, cidade, região, termo de prova). Não há `consentimento`, porque nenhum dado do candidato vai. `--offline` fica só no cache e `--dry-run` não chama a rede nem grava. O SDK `mcp` vem no extra `pci`. Detalhes do servidor em `docs/pesquisa-pci-mcp.md`; comandos e decisões em `docs/spec-pci-mcp.md`.

```toml
# ~/.concurso/config.toml
[pci_mcp]
enabled = true
url = "https://mcp.pciconcursos.com.br/mcp"
timeout = 30              # segundos por consulta
ttl_horas = 24            # validade do cache
cargos = ["analista"]     # reserva dos cargos-alvo do candidato
uf = "mg"                 # sigla de 2 letras, ou vazio
cidade = ""               # nome oficial de um município da UF (lista do IBGE), ou vazio
regiao = ""               # norte | nordeste | centro-oeste | sudeste | sul, ou vazio
dias_alerta = 15          # o radar mostra o que fecha ou abre nesse prazo
pasta_downloads = ""      # vazio: ~/Downloads (no WSL, a Downloads do usuário do Windows)
timeout_download = 300    # segundos esperando os arquivos do --download
```

```toml
# ~/.concurso/candidatos/<slug>.toml
[pci]
cargos = ["auditor fiscal", "analista"]   # vencem os de [pci_mcp]
uf = "df"
```

- **Campos:** desconhecidos ou de tipo errado levantam `ConfiguracaoInvalidaError`; o `doctor` mostra `✗` com a seção a corrigir e nunca consulta o servidor.
- **Cache** `.concurso/cache/pci_mcp.json`: `{"<sha256>": {"ferramenta", "argumentos", "obtido_em", "data_atual", "resposta"}}`. A chave é o sha256 da ferramenta e dos argumentos normalizados (sem vazios, sem acento, minúsculas, chaves ordenadas). Respostas vazias entram; `isError` não. Gravado só quando muda.
- **Filtros lembrados:** "Lembrar estes filtros", na tela Encontrar, grava `cargos`, `uf`, `cidade` e `regiao` em `[pci_mcp]` por `gravar_filtros_pci`. A cidade exige a UF e tem de ser dela; ela é gravada com o nome oficial do IBGE. Numa busca sem filtro, a cidade lembrada só vale na UF dela.
- **Municípios** `src/concursos/dados/municipios_ibge.json`: `{"<UF>": [nomes em ordem alfabética]}`, a lista do IBGE embutida no pacote (5.571 nomes, 27 UFs). O app não a consulta pela rede; `scripts/atualizar_municipios.py` a regenera à mão antes de uma release.
- **Datas:** toda exibição ao usuário (GUI, `radar_editais.md`, `index.html`, tabela do `discover`) usa DD/MM/AAAA por `datas.data_br`. O cache, os interesses e o `radar_editais.json` continuam em ISO.
- **Interesses** `.concurso/interesses_pci.yaml`: `interesses: [{id, titulo, uf, inicio, fim, link, registrado_em, concurso?}]`, gravado por `discover --register ID` e limpo por `discover --forget ID`; `concurso` é a pasta vinculada por `add <pasta> --pci ID` ou por `adicionar_ao_projeto`.
- **Adicionar ao meu projeto** (`discover --add ID`, ou o botão do card na tela Encontrar): `adicionar_ao_projeto` acompanha o concurso e cria `provas/<sigla_ano>/` (o título do PCI antes do " - ", até 4 palavras, com `_2`, `_3`… se já existir) com um `concurso.yaml` só com `nome` e `pci`. A pasta fica INCOMPLETA ("falta o edital e os arquivos da prova") até o envio dos arquivos, que preserva o bloco `pci`. Até lá, o nome mostrado é o título do PCI, a confirmar (`nomes.nome_sem_cadastro`). Adicionar de novo devolve a mesma pasta.
- **Situação do cache:** a tela Encontrar mostra "Atualizado há N horas" pelo maior `obtido_em` do cache (`situacao_do_cache`); "Atualizar agora" refaz a busca com `refresh`.
- **Região no card:** `regiao_do_concurso` dá "Sudeste · MG" (a região do PCI ou a da UF) e, com UF `BR`, "Nacional — todas as regiões". O PCI não informa a cidade da prova.
- **`pci:` no `concurso.yaml`:** `{id, titulo, link}` do concurso PCI vinculado. `pci.termos_provas` (lista) substitui os termos automáticos de `pci provas`.
- **`simulado:` no `concurso.yaml`:** marca uma prova anterior do PCI como simulado. Campos: `fonte` (`pci` ou `manual`, padrão `manual`), `id_pci` (int), `ano_original` (int), `organizadora`, `orgao`, `descricao`, `link`, `concurso_alvo` (pasta do alvo) e `cargo_alvo` (o cargo usado para ler o edital emprestado). O `edital` aponta para o do alvo (`../<alvo>/<arquivo>`), só para os tópicos: a correção vem do `concurso.yaml` e do perfil da banca da prova, e as regras do edital do alvo não são extraídas. O manifesto inclui o hash do edital de fora da pasta. `data_prova` é o dia em que o candidato resolveu (o `add` das respostas grava hoje, quando falta).
- **Simulados e consolidado:** com `incluir_simulados = false` (padrão), ficam fora de `desempenho_geral.csv`, do comparativo, do parquet e de `contar_questoes(raiz_analises, raiz_provas)`. O schema do parquet não muda. No `index.html`, aparecem na seção "Simulados (provas anteriores do PCI)", fora da tabela de concursos.
- **`analises/<candidato>/<alvo>/provas_anteriores.md`:** a lista de `pci provas <alvo>` (id, ano, órgão, cargo, banca e página), gravada só quando muda.
- **Importação em lote** (`pci provas <alvo> --import-all`, ou "Importar selecionadas" e "Importar todas" na tela): `importar_simulados` importa uma prova por vez, com a mesma espera do `--download`. A falha de uma vira aviso e o lote segue; cancelar a espera encerra o lote, e as que faltavam ficam como não tentadas. Uma prova cuja pasta já tem `provas` no `concurso.yaml` não é aberta de novo. O código de saída é 1 se alguma falhou.
- **Revisão do simulado antes das respostas:** logo depois do cadastro, `pipeline.preparar_revisao` classifica as questões da prova importada pelo edital emprestado e grava só `revisao/questoes_revisado.csv` (a análise continua exigindo as respostas). Um simulado sem a revisão é classificado na próxima análise.
- **Simulado focado** `analises/<candidato>/consolidado/simulado_focado.md`: depois de cada análise, só se o projeto tem simulados. Na ordem dos tópicos fracos persistentes (`topicos_fracos`), até 5 questões por tópico e 30 no total, tiradas das revisões dos simulados (a correção manual vence a sugestão; as questões já acertadas pelo candidato ficam fora; `nao_mapeado` nunca entra). O tópico casa pelo texto normalizado e, quando a questão tem disciplina, também pela disciplina. Aparece no `index.html` e na tela Provas anteriores ("Ver"). Gravado só quando muda.
- **Termo previsto:** `termos_previstos(contexto, alvo)` devolve os `termos_automaticos` do alvo, e a tela os mostra no campo Termo antes da busca.
- **Radar** (depois de cada análise, com `enabled`): entram os concursos dos cargos-alvo abertos com `dias_ate_fim <= dias_alerta` e os que ainda não abriram com `dias_ate_inicio <= dias_alerta`, mais os interesses até o `fim`, juntados pelo `id` e ordenados pelo prazo. Os dias vêm do PCI, relativos ao `meta.data_atual`. Grava, só quando muda:
  - `analises/<candidato>/radar_editais.json`: `{data_referencia, dias_alerta, cargos, itens: [{id, titulo, uf, inicio, fim, situacao, dias_ate_fim, link, interesse, concurso}]}`, lido pelo `status` e pelo `doctor`, que não falam com o PCI;
  - `analises/<candidato>/radar_editais.md`: a seção "Editais que fecham em breve" do `index.html`.
- **Falhas:** num comando explícito, `PciMcpParametroError` vira `ErroDoUsuario` (1), e `PciMcpIndisponivelError` e `PciMcpFormatoError`, `ErroDoAmbiente` (2). Depois da análise, viram aviso no log e não mudam o código de saída.

## Fontes de estudo: biblioteca e legislação

Opcionais e independentes; sem livros na biblioteca do app, sem `.concurso/biblioteca.yaml` e sem `[legislacao]`, nenhuma saída muda. São sugestões: não trocam o tópico nem a disciplina de nenhuma questão.

**Livros do app (fase 7).** Com algum livro lido (`lido`, `enviando` ou `pronto`) na biblioteca do app, a própria disciplina de cada livro também é categoria (`MapaBiblioteca.por_disciplina`), mesmo sem `biblioteca.yaml`, e a busca de recomendações usa o índice local dos livros (`BuscaLocal`, sem abrir o open-notebook). Sem livros do app, a busca no open-notebook externo segue como antes.

**`biblioteca.yaml` (legado, opcional).** `.concurso/biblioteca.yaml` (projeto, fora do git), disciplina canônica → categorias `<main> › <sub>` da estante do projeto `books`. Uma migração única (`migracao.migrar_biblioteca_yaml`, chamada antes da análise) passa os livros do app cuja disciplina é uma categoria do arquivo para a disciplina mapeada, com backup verificado em `~/.concurso/backup-biblioteca-<data>/` (o `biblioteca.yaml`, o `biblioteca.sqlite` e o `hashes.json`), e registra `[migracao_biblioteca] feita` e `livros` no `config.toml` do projeto. O arquivo fica onde está:

```yaml
catalogo: ../books/Bookshelf/README.md   # relativo à raiz do projeto; opcional
disciplinas:
  Banco de Dados: ["TI - Banco de Dados › SQL e Teoria", "TI - Banco de Dados › MongoDB"]
```

- **Validação:** disciplina fora de `.concurso/taxonomia.yaml` (quando ela existe) é `ConfiguracaoInvalidaError` com as opções, e a análise sai com código 1; categoria sem seção no catálogo nem notebook `Biblioteca — <categoria>` é só aviso.
- **Catálogo:** as seções `## <main> › <sub>` do `Bookshelf/README.md` com a tabela `Título | Autor | Arquivo`; seção sem ` › ` (exceto `Índice`) vira aviso.

`[legislacao]` na configuração global (um caminho desta máquina), apontando para um clone parcial do `ctresb/leis`. O app só lê arquivos; não chama `git` nem a rede:

```toml
[legislacao]
repositorio = "~/projects/leis"
```

- **Citações:** `legislacao.extrair_citacoes` acha, nos tópicos do `edital_estruturado.json`, Lei, Lei Complementar, Decreto (não Decreto-Lei nem Decreto Legislativo), Emenda Constitucional, Súmula Vinculante, Súmula do TCU e Constituição, com o trecho original.
- **Resolução:** `federal/<pasta>/<ano>/*-<numero>-<ano>-*.md`, `jurisprudencia/stf/sumulas-vinculantes/sumula-vinculante-<N>.md`, `jurisprudencia/outros-tribunais/tcu/sumula-<N>.md` e `constituicao.md`. Norma sem arquivo vira aviso com a dica de `git pull`. Avisos da norma: `versao_texto` não compilada, arquivo menor que `TAMANHO_MINIMO_NORMA` (8 KB, exceto súmulas) e revogada.
- **Chave da norma:** o `urn` do cabeçalho YAML ou, sem ele, o caminho relativo no clone.

`analises/<candidato>/consolidado/recomendacoes_estudo.md`, gravado com `gravar_se_mudou` no fim da análise e mostrado no `index.html` (seção "Recomendações de estudo"): para cada tópico de `insights.calcular_achados(...).fracos`, disciplina, tópico, n, percentual ajustado, os concursos abaixo do limiar e as linhas `- [<fonte>] <título> (<origem>). <detalhe>`, na ordem das camadas (`FonteRecomendacao`):

| Fonte | Camada | Detalhe |
|---|---|---|
| `legislacao` | normas citadas no próprio tópico, do clone | trecho citado, `fonte` oficial, arquivo e avisos da norma |
| `livros` | o índice local dos livros do app da disciplina, por trechos do tópico; até `LIVROS_POR_TOPICO` (3), origem `Meus livros` | a página do melhor trecho (`p. N`) |
| `open_notebook` | `POST /api/search` `type=text` nos notebooks `Biblioteca — <categoria>` mapeados, por trechos do tópico; até `LIVROS_POR_TOPICO` (3) | relevância (a busca não devolve trecho) |
| `catalogo` | sem rede, com erro ou sem resultado: os livros das categorias mapeadas, primeiro os que dividem palavras com o tópico | — |

A busca só roda com o open-notebook ligado, com consentimento e sem `--offline`; a falha vira aviso e o catálogo assume. Tópico sem nada sai como "Sem livro na estante nem norma citada", e a seção "Disciplinas sem livros mapeados" lista as disciplinas fracas fora do mapa.

No open-notebook (`notebook sync` e a sincronização automática):
- **Livros:** as sources dos notebooks de biblioteca das disciplinas presentes no `questoes.csv` do concurso são vinculadas ao notebook dele; tirar uma disciplina do mapa (ou o arquivo) desfaz só os vínculos que o app criou.
- **Legislação:** um notebook `Legislação`, compartilhado entre candidatos (chave `_legislacao` no estado), com uma source por chave de norma (título `<titulo> — <ementa curta>`, os avisos no topo do conteúdo), vinculada a cada concurso que a cita.
- **Nota:** o consolidado recebe `concurso-analise: recomendações de estudo` com o conteúdo do `recomendacoes_estudo.md`.
- Se a leitura da biblioteca ou o envio das normas falha, os vínculos daquela execução ficam como estão, para a lista incompleta não desvincular nada.
- **Normas da prática:** com `[pratica]`, `extrair_citacoes` roda também sobre o enunciado e o comentário dos erros do TEC; as normas do clone citadas ali entram na seção "Normas citadas nos seus erros do TEC", das mais citadas para as menos (`citada em N erros`, arquivo e avisos).

## Prática no TEC (tec-erros)

Opcional; sem `[pratica]` no `config.toml` do projeto, nenhuma saída muda. A captura mora em `tec-erros/`, neste repositório (extensão do Chrome, userscript para o Firefox do Android e `caderno.html`); as fixtures do contrato ficam em `tests/contrato_tec/` e passam pelo `node --test` e pelo `pytest`. O `tec-erros/docs/contrato.md` define o arquivo `tec-erros-<aparelho>-<data>.json` (`app = "tec-erros"`, `v = 1`, `erros`, `cads`). O app só lê arquivos; não acessa o TEC nem a rede.

```toml
[pratica]
entrada_tec = "tec"     # pasta das exportações, relativa à raiz do projeto
candidato = "ana"       # opcional; de quem é a prática (obrigatório com --all-candidates)
open_notebook = false   # true: o caderno de erros vai ao open-notebook (enunciado e comentário do professor)
```

- **Comando:** `concurso-analise pratica import [arquivo]` valida o arquivo (`app` e `v`; campo desconhecido é aviso), copia para `entrada_tec` e roda a análise; sem arquivo, só analisa. A análise padrão lê a pasta sempre que a seção existe. `--dry-run` não copia nem grava.
- **Mesclagem** (`pratica_tec`, as mesmas regras de `core/nucleo.js`): por `id` ou pela impressão digital `fp` (enunciado sem acento, minúsculo, espaços simples, 300 caracteres); `ds` é a união dos eventos (data e hora locais) e `v = len(ds)`, ou 1 sem evento; um registro de histórico (`OrigemErroTec.HISTORICO`) nunca soma ao tempo real; campo vazio é preenchido, `com` fica com o texto mais longo, `d` é a menor data; sem mudança, o registro (e o `t`) fica como estava. Cadernos: vence o de maior `res` e, no empate, o de maior `t`. Arquivo inválido é aviso e os outros seguem.
- **`caderno-estado.json`** (exportado pelo `caderno.html`, na mesma pasta): `removidos` saem das tabelas; `aliases`, `materias` e `cadernos` são sugestões que o app aproveita.
- **Disciplina:** a matéria do TEC casa com um nome da `.concurso/taxonomia.yaml` (sem diferença de acento, caixa e palavras vazias) ou com `materias` das escolhas; sem casamento, a disciplina fica vazia e o aviso pede para acrescentá-la em `nomes:`.
- **Tópico:** o assunto do TEC vira um tópico do `edital_estruturado.json` do `concurso_alvo`. Nome igual ao do tópico casa sozinho; senão, a sugestão vem do `caderno-estado.json` ou de `topicos.sugerir_topicos`. Com terminal, a pergunta sai uma vez por assunto (sugestão, tópicos da disciplina, "não pertence a nenhum tópico", "decidir depois"); sem terminal, o assunto vai para `pratica/revisao_aliases.csv` (`assunto`, `disciplina`, `sugestao`, `score`, `topico`), e a coluna `topico` preenchida (ou `nenhum`) entra nas escolhas na próxima execução. A escolha vale para todos os erros daquele assunto, inclusive os já importados. Sem `concurso_alvo`, os tópicos ficam `nao_mapeado`, com aviso.
- **Caderno:** `ModoCaderno.TUDO` (padrão, base zero) ou `DAQUI` (a base é o total da primeira importação); a pergunta sai uma vez por caderno com terminal, e o modo do `caderno-estado.json` vence a pergunta. O desempenho é o total atual menos a base.
- **Escolhas** `.concurso/pratica_tec.yaml` (fora do git), gravado só quando muda:

```yaml
aliases: {"Simples Nacional": "Simples Nacional: regime único", "Assunto alheio": null}
materias: {"Direito Tributário": "Legislação Tributária"}
cadernos: {"c87654321": {"modo": "daqui", "base": {"res": 2, "ac": 0, "er": 2}}}
```

Saídas em `analises/<candidato>/pratica/`, com `gravar_se_mudou`; o parquet, o `correcao.json` e os CSVs das fases 1 a 3 não mudam:

| Arquivo | Colunas |
|---|---|
| `erros_tec.csv` | `id`, `v`, `primeira_data`, `ultima_data`, `origem`, `materia_tec`, `disciplina`, `assunto`, `topico` (`nao_mapeado` pendente, `fora_do_edital` para `null`), `banca`, `orgao`, `ano`, `caderno`; do mais repetido para o menos |
| `cadernos_tec.csv` | `id`, `caderno`, `materia_tec`, `disciplina`, `modo`, `total`, `resolvidas`, `acertos`, `erros` (já descontada a base), `percentual`, `amostra_insuficiente` (n < `N_MINIMO_TOPICO`) |
| `desempenho_pratica_por_disciplina.csv` | `disciplina`, `n`, `acertos`, `erros`, `percentual`, `amostra_insuficiente`, `cadernos`, `erros_registrados`, `repetidos` (v ≥ 2) |
| `resumo_pratica.md` | a seção "Prática no TEC" do `index.html` |

- **Seção "Prática no TEC":** a prioridade de revisão (tópico fraco de `calcular_achados(...).fracos` com erro repetido no TEC no mesmo tópico, comparando por `chave_de_palavras`, com o percentual ajustado e o n da prova), os até `MAXIMO_REPETIDOS` (20) erros repetidos, os cadernos e o desempenho por disciplina; n < `N_MINIMO_TOPICO` sai como "amostra insuficiente (n = …)".
- **open-notebook:** só com `[pratica] open_notebook = true` e a sincronização ligada, o notebook `Caderno de erros — <rótulo>` (chave `<slug>/_caderno_de_erros`) recebe uma source por disciplina, `concurso-analise: caderno de erros/<disciplina>`, com assunto, banca, enunciado, alternativas, a resposta marcada, o gabarito e o comentário do professor. Esse conteúdo é do TEC: se a instância usa um provedor de IA na nuvem, o chat dela o envia para lá.
- **Dono:** a prática é de `[pratica] candidato` ou, sem ele, do candidato da execução; com `--all-candidates` e sem `candidato`, fica de fora, com aviso.

## Candidatos (fase 4)

Um concurso pode ter vários candidatos. Cada um tem uma subpasta com as respostas e o perfil:

```
provas/<concurso>/candidatos/<slug>/candidato.yaml
provas/<concurso>/candidatos/<slug>/respostas.txt   # ou respostas.csv, folha.pdf/png/jpg
provas/<concurso>/candidatos/<slug>/respostas_revisadas.csv   # com --reuse-csv; vence a folha
provas/<concurso>/candidatos/<slug>/respostas_revisadas.json  # hash da folha lida na revisão
analises/<slug>/<concurso>/                         # saída do candidato
analises/comparativo_candidatos.md                  # com --all-candidates
analises/<slug>/index.html                          # relatório HTML do candidato
analises/<slug>/export/consolidado.<csv|parquet|md> # com `export`
~/.concurso/candidatos/<slug>.toml                  # perfil global: nome e slug
```

```yaml
nome: Alice Souza
respostas:
  arquivo: respostas.txt     # ou folha: folha.pdf
resultado_oficial:           # opcional; nunca herdado do concurso.yaml
  identificador: '12345678'
```

- **Slug:** o nome sem acento, em minúsculas, com `_` no lugar do que não for letra ou dígito (`Carol Souza` vira `carol_souza`).
- **Herança:** gabarito, edital, template da folha, `total_itens` e `itens_por_coluna` vêm do `concurso.yaml`. O identificador do resultado oficial vem só do perfil do candidato.
- **Perfil ausente:** uma subpasta sem `candidato.yaml` tem o perfil inferido (`respostas.txt`, `respostas.csv`, o único `.txt`, o único `.csv` ou a única folha), gravado com aviso.
- **CSV manual:** quem não tem folha informa as respostas num CSV com as colunas `questao,alternativa` (`respostas.arquivo` ou inferido). Separador `,` ou `;`, UTF-8 (com ou sem BOM) ou cp1252, como o Excel grava; os nomes das colunas ignoram acento e caixa. Alternativa vazia ou `-` é branco, e questão omitida também. Questão fora das faixas, repetida ou com letra inválida é erro, com o arquivo e a linha.
- **Revisão da leitura (`analyze <concurso> --reuse-csv`):** o candidato corrige a coluna `alternativa_marcada` do `analises/<slug>/<concurso>/respostas_extraidas.csv` no Excel ou no LibreOffice. O comando valida o CSV com as regras do CSV manual e o copia para `respostas_revisadas.csv` na subpasta do candidato, com o hash da folha em `respostas_revisadas.json`. A partir daí ele vence a folha e o `respostas.arquivo`, e entra no manifesto como qualquer arquivo do candidato. Uma linha sem alternativa e com `estado = multipla` continua múltipla. Se o hash da folha mudar depois, a análise avisa ("revisão antiga") e continua usando a revisão; para ler a folha nova, apague o `respostas_revisadas.csv`. Sem o CSV de leitura, sem concurso ou sem candidato, o comando para com uma `dica:`.
- **Escolha:** `--candidate`, `CONCURSO_CANDIDATO` ou `[candidato] ultimo` do `config.toml`, gravado a cada análise que não seja `--dry-run` nem `--all-candidates`. Com vários candidatos e nenhum escolhido, a CLI pede `--candidate` ou `--all-candidates`.
- **Manifesto por par:** o hash de entrada de um par (candidato, concurso) cobre os arquivos comuns e só a subpasta do candidato. Mudar as respostas de um reprocessa só ele; mudar o gabarito reprocessa todos.
- **Layout legado:** só o comando obsoleto `concursos analisar` ainda lê as respostas do `concurso.yaml` e grava em `analises/<concurso>/`; o `concurso-analise` migra antes de analisar.

## Perfis de banca (fase 4)

O que muda de uma banca para outra fica num perfil, não em ramos do código. Os embutidos são YAML em `src/concursos/perfis/bancas/`; outro pacote acrescenta (ou substitui, pelo mesmo `id`) um perfil no entry point `concurso.banca`, que devolve um `PerfilBanca`, um dict ou o caminho de um YAML.

```yaml
id: cebraspe                 # valor de `banca` no concurso.yaml
nome: Cebraspe
ordem: 10                    # ordem de detecção; o primeiro com marca no texto vence (padrão 100)
marcas: [CEBRASPE]           # procuradas como palavra inteira no texto normalizado (sem acento, maiúsculo)
formato: certo_errado        # ou multipla_escolha (padrão)
alternativas: null           # opcional
penalidade: 1.0              # fator de penalidade por erro no formato padrão
leitor_gabarito: cebraspe    # gabarito PDF que já traz os itens
leitor_secoes: null          # gabarito PDF com uma seção por cargo e tipo (fgv, lista)
leitor_cargo: cebraspe       # cargo no cabeçalho do gabarito
segmentacao: itens           # questoes (padrão) ou itens (comando do bloco antes do item)
disciplinas_pelo_caderno: false  # faixas de disciplina pelos títulos do caderno
chaves_prova:                # chave da prova pela marca no cabeçalho do gabarito
  - [CONHECIMENTOS BASICOS, cb]
chave_padrao: ce             # sem marca (padrão: unica)
marca_caderno_padrao: CONHECIMENTOS ESPECIFICOS  # separa o caderno da prova padrão
templates_folha:             # template da folha pelo total de itens; '*' vale para qualquer total
  '*': cebraspe_ce
```

- **Leitores:** um nome embutido (`cebraspe`, `fgv`, `lista`) ou `modulo:funcao` de outro pacote, com a assinatura do embutido.
- **Validação:** campo desconhecido, `formato` ou `segmentacao` fora das opções, ou `id` e `marcas` ausentes geram erro citando o campo. `marcas: []` é válido: o perfil nunca é detectado.
- **Embutidos:** `cebraspe` (certo/errado, fator 1), `fgv`, `fcc`, `vunesp` (múltipla escolha, 5 alternativas, fator 0), `ibfc` e `idecan` (múltipla escolha, fator 0, alternativas variam por edital) e `generic`. Os cortes típicos de cada banca ficam nos comentários do YAML, como referência: quem decide o corte é o edital.
- **`generic`:** sem marcas, nunca detectado; é o template de banca nova e vale quando o concurso não declara banca. Ele não preenche regra (não há fonte `perfil` vinda dele): sem a regra no edital nem na configuração, cai no default.
- **Regra que o perfil preenche:** penalidade (na correção e no bloco `prova`) e alternativas, quando nem o edital nem o `concurso.yaml` as trazem e o perfil é do mesmo formato do concurso.
- **Penalidade na agregação:** a nota líquida usa o fator da `pontuacao` do concurso (`cebraspe` = 1, `simples` = 0), nunca o nome da banca.

## Perfis de OCR da folha (fase 4)

A grade da folha de respostas e os limiares de leitura ficam num perfil de OCR, escolhido pelo `template` do `concurso.yaml` (ou pelo `templates_folha` da banca). Os embutidos são YAML em `src/concursos/perfis/folhas/` (`cebraspe_ce`, `fgv_mod70ae`, `fgv_cpnu_90`, `grade_abcd`); outro pacote acrescenta um no entry point `concurso.ocr`, que devolve um `PerfilOcr`, um dict ou o caminho de um YAML.

```yaml
id: grade_abcd               # valor de `template` em respostas
alternativas: ABCD           # letras das bolhas, da esquerda para a direita (CE no certo/errado)
itens_por_coluna: null       # opcional; sem ele vale o do concurso.yaml
vazio: 0.2                   # preenchimento de uma bolha vazia
cheio: 0.9                   # preenchimento de uma bolha marcada
limiar_marcada: 0.5          # acima disto, a bolha conta como marcada
largura: 2480                # largura, em pixels, para a qual a página é normalizada
```

Um `template` sem perfil gera erro com a lista dos perfis disponíveis.

**Detecção automática.** Sem `template` (no `concurso.yaml`, no perfil do candidato e na banca), ou quando o perfil não lê a folha, a leitura detecta a grade sozinha: círculos pelos contornos, ângulo de até 5° corrigido, bolhas agrupadas em linhas e colunas, com as letras do concurso (`CE` ou as `alternativas` do formato) e os limiares padrão. Quando o perfil falha, o log avisa antes de tentar. A imagem de depuração é a mesma. Se nem a detecção acha a grade, o erro lista o que cada tentativa encontrou e traz uma `dica:` para digitar as respostas num `respostas.csv`; os outros concursos seguem.

**Confiança da leitura.** Numa bolha marcada, a diferença entre as notas dos dois maiores preenchimentos; em branco, 1 menos a maior nota; em múltipla, a segunda maior nota.

## Migração das fases 1 a 3

Toda análise do `concurso-analise` (menos o `--dry-run`, que só lista as operações) começa migrando o que estiver no formato antigo. O candidato é o escolhido (`--candidate`, `CONCURSO_CANDIDATO`, `[candidato] ultimo`), o da migração anterior ou o login do sistema.

| Formato antigo | Vira |
|---|---|
| `analises/<x>/` com saídas (`correcao.json`, `.manifesto.json`, `relatorio.md`, `comparativo_concursos.md` ou `desempenho_geral.csv`) | `analises/<candidato>/<x>/`, movida sem reprocessar |
| `respostas` e `resultado_oficial.identificador` num `concurso.yaml` sem `candidatos/` | `candidatos/<candidato>/candidato.yaml`, com a folha ou o texto no lugar (`../../<arquivo>`) |
| `config.yaml` da raiz | seção `[analise]` do `config.toml` (o que já estava no `config.toml` vence) |
| `taxonomia.yaml` da raiz | `.concurso/taxonomia.yaml`; se as duas existem, a migração para e pede para juntá-las |

- **Backup:** antes de qualquer mudança, tudo o que será alterado ou movido é copiado para `<global>/backup-<AAAAMMDD-HHMMSS>/` (`raiz/`, `projeto/`, `provas/`, `analises/`), com `hashes.json`. Uma cópia que não confere com o original aborta a migração sem alterar nada.
- **Destino ocupado:** se `analises/<candidato>/<x>/` já existe, a migração para antes de mexer em qualquer arquivo.
- **Manifestos:** o de cada saída que estava em dia é regravado para o par (candidato, concurso), para a próxima análise não reprocessar.
- **Uma vez só:** sem nada no formato antigo, nada acontece. Uma pasta antiga que apareça depois do registro é migrada na hora, com aviso.

## `concurso.yaml`

O arquivo é gerado por `concursos adicionar` e pode ser editado à mão. Os caminhos são relativos à pasta do concurso.

```yaml
nome: tcu_25
titulo: TCU 2025 — AUFC        # opcional: o nome corrigido pelo usuário ("Corrigir nome"); vence o do edital
banca: cebraspe                # cebraspe | fgv | selecon | quadrix
formato: certo_errado          # multipla_escolha | certo_errado
pontuacao: cebraspe            # simples | cebraspe (padrão: simples)
alternativas: 4                # só em multipla_escolha, de 2 a 10 (padrão: o do perfil da banca ou 5)
cargo: 'CARGO 2: AUDITOR ...'  # obrigatório quando o gabarito tem várias seções
tipo: '1'                      # tipo/versão do caderno, quando houver
edital: edital.pdf             # obrigatório; sem ele, o concurso fica incompleto. Ou a forma completa:
# edital:
#   arquivo: edital.pdf        # opcional se houver manual
#   anexos: [anexo_ii.pdf]     # lidos antes do edital principal
#   manual: edital_manual.yaml # tem prioridade sobre os PDFs
#   retificacoes: [ret_2.pdf, ret_3.pdf]  # na ordem de publicação; só para as regras do edital
provas:
  cb:
    caderno: prova_cb.pdf      # opcional; usado para disciplinas e tópicos (ausente, só avisa)
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
  template: cebraspe_ce        # opcional; perfil de OCR: cebraspe_ce | fgv_mod70ae | fgv_cpnu_90 | grade_abcd (sem ele, detecção automática)
  total_itens: 200
  itens_por_coluna: 20         # opcional; detectado pela grade
# respostas:
#   arquivo: respostas.txt     # ou respostas.csv (colunas questao,alternativa)
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
pci: {id: 296237, titulo: '...', link: 'https://...'}  # opcional; vínculo com o PCI (add --pci)
# simulado: {fonte: pci, id_pci: 20549582, ano_original: 2014, organizadora: ESAF, concurso_alvo: tcu_25, ...}
```

Todo arquivo da pasta precisa aparecer no `concurso.yaml` (num campo ou em `ignorar`). Caso contrário, o concurso fica `desatualizado`. Ficam de fora dessa regra:
- a pasta `revisao/`;
- arquivos `.yaml`;
- compactados;
- arquivos `:Zone.Identifier`.

## Taxonomia de disciplinas

A taxonomia fica em `./.concurso/taxonomia.yaml`. É gravada pela tela Configurações > "Disciplinas e temas" (ver [Conferência pela tela](#conferência-pela-tela)), e editá-la à mão continua valendo. Ela mapeia cada nome de disciplina, como aparece nos `questoes.csv`, para uma **disciplina canônica**. Assim, a mesma matéria é comparada entre editais que usam nomes diferentes:

```yaml
Raciocínio Lógico:
  bloco: geral                 # geral | especifico
  nomes:                       # o próprio nome canônico já está incluído
    - Raciocínio Lógico Matemático
    - Raciocínio Análitico
```

- **Nomes:** um nome só pode aparecer em uma disciplina canônica. Sem o arquivo de taxonomia, cada disciplina bruta vira canônica de si mesma. Um nome ausente do mapa também vira canônico de si mesmo, com bloco `nao_informado` na prova única (nas provas divididas, o bloco vem da chave da prova), e o consolidado registra aviso com a lista de nomes. A disciplina `nao_mapeado`, das questões que o pipeline não classificou, passa direto, sem entrada na taxonomia.
- **Bloco:**
  - Nas provas divididas, o bloco vem da própria prova: `cg` e `cb` são `geral`, e `ce` é `especifico`.
  - Na prova única, vem do bloco da disciplina canônica. Uma questão `nao_mapeado` em prova única fica com bloco `nao_informado`.
- **Identidade de tópico** (`chave_topico`): a disciplina canônica mais as palavras-chave do nome do tópico, sem acento, caixa ou palavras vazias, em ordem alfabética. É a mesma normalização do comparativo entre concursos. Por exemplo, "Emprego do sinal indicativo de crase" e "EMPREGO DO SINAL INDICATIVO DA CRASE", ambos em Língua Portuguesa, têm a mesma chave.

Editar a taxonomia reconstrói o consolidado na próxima carga.

## Edital manual

Use quando o conteúdo programático não puder ser extraído do PDF (sem ele, a análise segue com os tópicos `nao_mapeado`), ou para corrigir a estrutura extraída. O caminho vai em `edital.manual`. Sem o PDF do edital, o manual mínimo (`conhecimentos: []`) cumpre a obrigatoriedade do edital, mas não traz regra nem tópico.

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

O arquivo `provas/<concurso>/revisao/questoes_revisado.csv` é criado na primeira análise e nunca é sobrescrito. Sem tópicos no edital (modo mínimo ou manual sem conhecimentos), a disciplina sugerida vem das faixas do `concurso.yaml` (ou `nao_mapeado`) e o tópico sugerido é `nao_mapeado`. Colunas:

- `questao`, `prova`;
- `disciplina_sugerida`, `topico_sugerido`, `score`;
- `enunciado` (trecho);
- `disciplina`, `topico` (para o usuário preencher).

Células não vazias em `disciplina` e `topico` têm prioridade sobre a sugestão. Editar o arquivo dispara o reprocessamento. A tela de conferência grava as duas colunas das questões escolhidas (`topicos.gravar_revisao_editada`), sem mexer nas outras linhas nem nas colunas; "Nenhum" grava `topico = nao_mapeado`.

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
  - `gabarito`, `anulada`, `resposta`, `resultado`;
  - só com o [dicionário de temas](#dicionário-de-temas) ligado, no fim: `score_tfidf`, `topico_tfidf` (a sugestão sem o dicionário) e `score_expandido` (igual a `score`). O parquet não muda.
- **`diff_gabarito.csv`** (após a troca de gabarito): colunas:
  - `prova`, `questao`;
  - `gabarito_preliminar`, `gabarito_definitivo`;
  - `mudanca` (`alterada | anulada`);
  - `resposta`, `acerto_antes`, `acerto_depois`.
- **`edital_estruturado.json`:** `fonte`, `cargo` e `conhecimentos[].disciplinas[].topicos[]`. Cada tópico tem `numero`, `nome`, `descricao` e `peso`. Quando há PDF do edital, o arquivo ganha as [regras do edital](#regras-do-edital-fase-3) (`identificacao`, `avisos` e os blocos descritos lá). Cada parte grava só as próprias chaves e preserva as outras.
- **`discrepancias_edital.csv`:** uma linha por divergência entre o edital e a prova, com as colunas `item, esperado_edital, observado_prova, diferenca, severidade, acao_sugerida, nome_oficial, cargo`. `nome_oficial` e `cargo` (com a especialidade depois de " – ", quando houver) vêm da identificação do edital e se repetem em toda linha. A `severidade` é `info`, `warn` ou `error`; a `diferenca` fica vazia quando não é numérica. Só existe quando há PDF do edital, e fica só com o cabeçalho quando tudo confere.
- **`catalogo_edital.md`:** o catálogo de descobertas do edital (template em "Regras do edital"). Só existe quando há PDF do edital.
- **`correcao.json`:** lista de configurações de correção (uma por variante; uma só quando o concurso não tem variantes). Campos:
  - `modelo`, `fator_penalidade`, `nota_maxima`, `nota_corte`;
  - `pesos`: lista de `{inicio, fim, peso}` (vazia quando todos os itens valem 1);
  - `fonte` (`edital | config | perfil | default`), `confianca`;
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
  - do `correcao.json` (a primeira configuração, quando há variantes): `data_prova` (data, vazia sem data), `modelo_correcao` (`bruta | liquida | ponderada`), `fator_penalidade`, `nota_maxima`, `nota_corte` (vazia sem corte), `fonte_correcao` (`edital | config | perfil | default`), `confianca_correcao`;
  - `pontos_bruta`, `pontos_corrigida` e `pontos_ajustada`: a pontuação por item da tabela acima, sem peso, vazia nas anuladas;
  - `peso__<variante>`: o peso do item em cada variante (`peso__padrao` quando o concurso não tem variantes), vazio nos concursos sem aquela variante;
  - `ordem`: posição cronológica do concurso pela data da prova, a partir de 1 (datas iguais empatam), vazia sem data;
  - `n_topico`: quantidade de questões do tópico naquela prova (o `total` de `desempenho_por_topico.csv`).

  `validar_schema` confere colunas, tipos, domínios, nomes de disciplina sem mapeamento na taxonomia, a existência de ao menos uma coluna `peso__` e o número de linhas igual à soma das linhas de todos os `questoes.csv` (um concurso analisado que ficou fora reprova a contagem).
- **`relatorio_evolucao.md` e as figuras (`evolucao_zscore.png`, `heatmap_topicos.png`, `painel_correcao.png`):** gravados pelo notebook 04 e pelo relatório HTML, quando o consolidado tem `MINIMO_CONCURSOS` (2) concursos ou mais. Sem tópico em concursos suficientes, o heatmap sai vazio, com o aviso na figura.

No relatório HTML do candidato, em `analises/<slug>/` (`concursos.relatorio_html`):

- **`<concurso>/relatorio.html`:** o `relatorio.md` em HTML, com as imagens relativas de `graficos/` e um link de volta ao índice.
- **`index.html`:**
  - tabela de concursos: link para o `relatorio.html`, data da prova, acertos de total, percentual pela regra (a nota de `notas_pela_regra`, com o desconto por erro e os pesos do `correcao.json` e a anulada valendo ponto, sobre a soma dos pesos: no Cebraspe, 35 certos e 15 errados em 50 itens dão 40%; uma linha por variante, inclusive na bruta; sem `concurso.yaml` em `provas/`, o percentual de mérito do `desempenho_por_disciplina.csv`), o selo da confiança do edital (`edital: alta`, `média`, `baixa` ou `mínima`; `sem edital` sem o JSON) e o selo da regra de correção (`regra do edital`, `do concurso.yaml`, `do perfil da banca` ou `padrão`, com a confiança);
  - o que o app decidiu sozinho: regra de correção do perfil ou padrão, campos do bloco `prova` do edital vindos do perfil, do padrão ou do LLM, a data da prova vinda do LLM, e as questões com tópico sugerido por similaridade sem revisão;
  - avisos: os do `edital_estruturado.json`, concurso sem data, as linhas `error` e `warn` do `discrepancias_edital.csv` e as leituras da folha com `revisar`;
  - evolução: o `relatorio_evolucao.md` e as figuras, mais a tabela de gap para o corte (`comparar_percentual_e_gap`, uma linha por concurso e variante com corte), ou o aviso de que a evolução precisa de 2 concursos;
  - recomendações de estudo: o `consolidado/recomendacoes_estudo.md`, só quando ele existe (com `biblioteca.yaml` ou `[legislacao]`), com a fonte de cada linha; uma mudança nele também regera o índice;
  - rodapé com a versão, a data da geração e a pasta de provas.
- **Sem rede:** CSS embutido, imagens por caminho relativo e nenhum HTML bruto do markdown (o texto vem de PDFs).
- **Quando é gerado e aberto:** depois de cada análise em que algum manifesto foi regravado (algo reprocessado) ou sem `index.html`; nesse caso abre no navegador padrão (no WSL, com `wslview` ou `explorer.exe`), salvo com `--no-open` ou `CI` definido. Sem mudanças, nada é regravado, e a CLI só imprime o caminho. `report` reabre o índice do candidato escolhido; sem índice, para com uma `dica:`.
- **`export --format csv|parquet|md`:** grava o consolidado do candidato (as colunas do `consolidado.parquet`, uma linha por questão) em `export/consolidado.<formato>`; o `md` é uma tabela markdown.

**`doctor`** (`concursos.doctor`). Só leitura e sem rede. Uma linha por item, `✓`, `!` ou `✗`, e, quando há, a linha `correção:` com o comando do sistema detectado (`apt` no Linux, `brew` no macOS, `winget` no Windows):

- `uv`: ausente é `!`;
- Python: fora de 3.11 e 3.12 é `✗`;
- Tesseract: ausente do PATH é `✗`; sem o idioma `por` (`tesseract --list-langs`), `!` com o pacote do idioma;
- poppler: sempre `✓`, "não necessário";
- escrita nas pastas de provas, análises, do projeto e na home (`CONCURSO_HOME`): a pasta, ou o primeiro ancestral existente, sem permissão é `✗`;
- espaço em disco: menos de 200 MB é `✗`, menos de 1 GB é `!`;
- legislação: sem `[legislacao]` é `✓`; caminho inexistente ou sem `federal/leis-ordinarias/` é `!`, com o `git clone` parcial ou o `git sparse-checkout add`.

Sai com 2 se algum item tem `✗`, senão com 0.

**`upgrade`.** Instalado pelo `uv`, só imprime `uv tool upgrade concurso-analise`; com `--run`, executa-o pelo `uv` do PATH (sem ele, sai com 2 e a `dica:` de instalação). No executável (fase 6), consulta o manifesto do canal (`--canal stable|beta`, padrão o de `[atualizacao]`) e diz se há versão nova; com `--run`, baixa, confere e aplica (ver "Atualizador"). Com `--dry-run` ou `--offline`, não consulta nada. A ferramenta nunca se atualiza sem um pedido.

**Idempotência.** Uma execução sem mudança nas entradas não altera nenhum `mtime` em `analises/`, nem com `--dry-run`: as saídas por concurso dependem do manifesto, o `index.html` só é regerado quando algo foi reprocessado, e o consolidado (`desempenho_geral.csv`, `comparativo_concursos.md`) só é regravado quando o conteúdo muda.

**Distribuição.** `uvx --from <repositório> concurso-analise` ou `uv tool install <repositório>` (o comando principal não depende de grupos de dependência). O `Dockerfile` (`python:3.12-slim-trixie`, `tesseract-ocr-por`, `uv sync --locked --no-dev`) espera o projeto montado em `/dados`, com `CONCURSO_HOME=/dados/.concurso-home`; o `.dockerignore` deixa `provas/`, `analises/` e `.concurso/` fora da imagem. `scripts/smoke.py` é o teste de ponta a ponta: onboarding com `--yes`, análise de dois concursos sintéticos num caminho com espaço e acento e reexecuções sem mudança de `mtime`.

**GUI (fase 5).** `concurso-analise gui` (ou `concurso-analise-gui`) exige o extra `[gui]`. Abre em `127.0.0.1`, numa porta livre: janela nativa no Windows e no macOS, navegador padrão no Linux (`--browser` força o navegador em qualquer sistema). O projeto inicial é o `--project`, a pasta atual (se já tem `provas/` ou `.concurso/`) ou o último usado; o escolhido fica na configuração global; o `app.storage` do NiceGUI fica em `~/.concurso/gui` e não guarda dado pessoal.

```toml
# ~/.concurso/config.toml
[gui]
ultimo_projeto = "C:/Users/ana/Documents/Concursos"   # pasta com provas/, analises/ e .concurso/
tema = "sistema"                     # fase 6: sistema, claro ou escuro
aviso_webview2_dispensado = false    # fase 6: true depois do "Entendi" no aviso de navegador

[atualizacao]                        # fase 6
canal = "stable"                     # ou "beta"
verificar_ao_abrir = false           # consulta o GitHub ao abrir a GUI, no máximo 1 vez a cada 24 h
```

**Resultados e configurações pela GUI.** O relatório aparece num `iframe`: a pasta `analises/<candidato>/` é servida em `/_analises/<hash do caminho>/`, só em `127.0.0.1` e sem cache, e "Abrir no navegador" usa o mesmo `abrir_no_navegador` da CLI (no WSL, o navegador do Windows). As abas de recomendações e de prática mostram `consolidado/recomendacoes_estudo.md` e `pratica/resumo_pratica.md` (com as tabelas da prática), ou explicam por que ainda não existem. A tela de configurações grava `[analise]` pelo `gravar_analise`; a IA começa desmarcada, ligar grava `[llm]` com `consentimento = true` e a chave vai para `llm.guardar_chave` (keyring ou `~/.concurso/.env` com permissão 600), e desmarcar grava `provedor = "nenhum"`.

**Integrações pela GUI.** A tela Integrações tem quatro abas. Desligada, cada integração mostra só o texto de `aplicacao.integracoes.aviso_*` e o botão "Concordo e ligar", e nenhuma consulta é feita. Encontrar concursos e Provas anteriores chamam o PCI por `descobrir` e `provas_anteriores`; na primeira, UF e cidade são selects (a cidade, só com a UF), e "Acompanhar" grava em `.concurso/interesses_pci.yaml` pelo `registrar_interesse`. "Importar como simulado" roda `importar_simulado` numa thread, com a espera na pasta de downloads interrompida pelo botão Cancelar (`espera_cancelavel`); o app continua sem pedir o link do PDF ao PCI. A aba open-notebook grava `[open_notebook]` com `enabled` e `consentimento` e sincroniza com um botão. A aba Prática no TEC valida todas as exportações soltas antes de copiar a primeira; sem `[pratica]`, ela grava `entrada_tec = "tec"`. A instalação da captura usa o `dist/` do `tec-erros/` (no executável, a pasta `tec-erros/` do `_MEIPASS`); sem ele, a aba aponta para as instruções do repositório.

**Executável.** O build do PyInstaller (`empacotamento/concurso-analise.spec`, onedir) gera dois executáveis na mesma pasta: `concurso-analise` (janela, sem console no Windows) e `concurso-analise-cli` (console). Os dois rodam `concursos.empacotado.principal`: sem argumentos, a GUI; com argumentos, a CLI; com `--smoke`, a conferência do pacote (versão, perfis, Tesseract com `por` e a GUI respondendo em `127.0.0.1`), que sai com 0 ou 1. Dentro de `_internal/` ficam `tesseract/bin` e `tesseract/tessdata` (o executável põe o primeiro no `PATH` e o segundo em `TESSDATA_PREFIX`), `tec-erros/` (o `dist/` da captura) e `LICENSES/`. O `doctor` e a tela Sobre mostram o Tesseract como embutido. `CONCURSO_SMOKE_SEM_OCR=1` dispensa o Tesseract no `--smoke`, só para builds de desenvolvimento. No Windows sem WebView2, a GUI abre no navegador, com aviso (veja **Janela**). No Linux, `tesseract/bin/tesseract` é um wrapper que roda o binário com o carregador e as bibliotecas que vieram com ele (`tesseract/lib`), e o executável devolve o `LD_LIBRARY_PATH` original aos processos que abre; no macOS, a árvore do Tesseract fica em `concurso-analise.app/Contents/Frameworks/tesseract`, com as dylibs relocadas para `@executable_path/../lib`.

**Cadastro pela GUI.** O onboarding em formulário grava pelas mesmas `onboarding.aplicar` e `onboarding.gravar` do `init` e cria a pasta de provas com o `LEIA-ME.txt`, se faltar. Os arquivos soltos na tela "Novo concurso" esperam em `.concurso/envios/<aleatório>/` (apagados depois do cadastro, ou depois de um dia se abandonados) até o usuário confirmar o papel de cada um. Na confirmação, edital, prova, gabarito e resultado vão para `provas/<concurso>/` (o nome passa por `slug`) e o papel escolhido vence a detecção no `cadastrar` (`papeis`); folha e respostas vão para `candidatos/<slug>/` pelo `adicionar_respostas`; o que foi marcado para ignorar não é copiado. Se o usuário recusa ou o cadastro falha, a pasta volta a ser como era. Um arquivo com o nome de outro, diferente, já na pasta é erro, e nada é sobrescrito. As respostas digitadas viram `candidatos/<slug>/respostas.csv` (`questao,alternativa`, só as marcadas; as omitidas contam como branco), validado por `ler_respostas_csv` antes da cópia.

**Executável (fase 5).** Pasta onedir do PyInstaller, gerada por `empacotamento/concurso-analise.spec`:

| Caminho no bundle | Conteúdo |
|---|---|
| `concurso-analise(.exe)` | o launcher (`empacotamento/launcher.py`): `freeze_support`, `PATH` e `TESSDATA_PREFIX`, `--smoke`, GUI |
| `_internal/concursos/` | o pacote, com os perfis YAML (coletados pelo `hook-concursos.py`) |
| `_internal/concurso_analise-<versão>.dist-info/` | metadados: versão e entry points `concurso.banca` e `concurso.ocr` |
| `_internal/tesseract/` | o binário do Tesseract (e DLLs ou dylibs) e `tessdata/por.traineddata` (`tessdata_fast`) |
| `_internal/tec-erros/` | `caderno.html`, `tec-erros-extensao-<versão>.zip` e `tec-erros.user.js` |
| `_internal/LICENSES/` | as licenças de Tesseract, Leptonica, bibliotecas de imagem, NiceGUI, pywebview e Python |

Artefatos da release: `concurso-analise-<versão>-windows-x64-setup.exe`, `concurso-analise-<versão>-linux-x86_64.AppImage`, `concurso-analise-<versão>-macos-arm64.dmg` e `SHA256SUMS`. `concurso-analise --smoke`, no executável, confere o pacote e sai com 0 quando tudo passa; `scripts/smoke.py congelado <executável>` roda, numa pasta temporária, o `--smoke`, o doctor, o onboarding e a análise de um concurso sintético.

## Fase 6: atualizador, janela, etapas e tema

**Atualizador.** `concursos.atualizador` e `concursos.aplicacao.atualizador`, usados pelo Sobre da GUI e pelo `upgrade` do executável. O canal `stable` lê `https://github.com/LMafra/analise_concursos/releases/latest/download/atualizacao.json` e `.sig`; o `beta` lê `https://api.github.com/repos/LMafra/analise_concursos/releases?per_page=10` e usa a primeira release que não é rascunho. Cada release traz:

```json
{
  "formato": 1,
  "versao": "0.6.0",
  "canal": "stable",
  "publicado_em": "2026-12-01",
  "notas": "https://github.com/LMafra/analise_concursos/releases/tag/v0.6.0",
  "artefatos": {
    "windows-x64": {"arquivo": "concurso-analise-0.6.0-windows-x64-setup.exe", "sha256": "<64 hex>", "tamanho": 191000000},
    "linux-x86_64": {"arquivo": "concurso-analise-0.6.0-linux-x86_64.AppImage", "sha256": "<64 hex>", "tamanho": 290000000}
  }
}
```

- `atualizacao.json.sig`: 64 bytes da assinatura Ed25519 sobre os bytes exatos do `atualizacao.json`, em base64 numa linha. A assinatura é conferida antes de ler o JSON, contra qualquer chave de `atualizador.CHAVES_PUBLICAS`.
- `formato` diferente de 1, campo faltando, `canal` fora de `stable`/`beta`, `arquivo` fora de `^concurso-analise-[0-9A-Za-z.+-]+-(windows-x64-setup\.exe|linux-x86_64\.AppImage)$`, `sha256` fora de 64 hex ou `tamanho` não positivo: manifesto inválido.
- O cliente `stable` só aceita `canal: stable`; o `beta` aceita os dois. Só versão maior que a instalada (PEP 440) é oferecida.
- O artefato é baixado de `https://github.com/LMafra/analise_concursos/releases/download/v<versao>/<arquivo>`, com no máximo `tamanho` bytes, e só é usado se o SHA-256 bate. Só HTTPS e redirecionamento para `github.com`, `api.github.com`, `objects.githubusercontent.com` e `release-assets.githubusercontent.com`; o manifesto tem no máximo 64 KB.
- Windows: o setup vai para a pasta temporária; se o `.exe` em execução tem Authenticode válido, o setup precisa ter assinatura válida do mesmo signatário. Roda `setup.exe /SILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /REABRIR=1` e o app fecha; o setup espera (até 30 s) sumir o mutex `concurso-analise`, que o executável segura enquanto roda, e com `/REABRIR=1` reabre o app no fim.
- Linux: o AppImage novo é gravado num temporário na pasta de `$APPIMAGE`, recebe `chmod 755` e substitui o arquivo no mesmo caminho (`os.replace`), mantendo o nome e os atalhos; a GUI oferece reabrir. Sem `$APPIMAGE` ou sem permissão de escrita na pasta: `ErroDoUsuario` com a dica de baixar à mão.
- `verificar_ao_abrir`: a data da última consulta fica em `~/.concurso/atualizacao.json` (`{"ultima_consulta": "<ISO 8601>"}`); com menos de 24 h, não consulta. Falha nessa consulta só vai para o log.

**Janela.** `concursos.janela.decidir_janela` devolve `DecisaoJanela` (`modelo.py`): `nativa`; `navegador_pedido` (`--browser`); `navegador_linux`; `navegador_sem_webview2` (Windows sem `pv` válido em `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`, no mesmo caminho sem `WOW6432Node` ou em `HKCU\Software\...`, ou sem conseguir carregar o `WebView2Loader.dll`). Só `navegador_sem_webview2` e `CONCURSO_JANELA_FALHOU=1` (a janela nativa falhou, ou fechou sem nenhuma página ter conectado, e o app reabriu no navegador) mostram o aviso "Componente de janela indisponível; o app abre no navegador", com o link do WebView2; "Entendi" grava `[gui] aviso_webview2_dispensado`, que `CONCURSO_JANELA_FALHOU` ignora.

**Etapas da análise.** `pipeline.analisar_todos(..., ao_etapa=None)` chama `ao_etapa(concurso, Etapa)` em cada concurso processado: `lendo_arquivos`, `lendo_folha`, `corrigindo`, `classificando`, `gerando_relatorios`; e `ao_etapa('', Etapa.CONSOLIDANDO)` antes do consolidado. `Etapa` mora em `modelo.py`, e o texto mostrado ("Lendo a folha…") em `aplicacao.analise.TEXTO_DA_ETAPA`. Com `None`, as saídas não mudam.

**Exemplo.** `concursos.exemplo.criar_exemplo(raiz)` grava em `<raiz>/provas/exemplo/` um concurso sintético de múltipla escolha com 10 questões (o mesmo formato do `scripts/smoke.py`: gabarito, `respostas.txt` da candidata fictícia `exemplo` e edital manual mínimo); `aplicacao.exemplo.analisar_exemplo` recria `~/.concurso/exemplo/` a cada uso e o analisa sem OCR nem rede. O projeto real do usuário não muda.

**Tema.** `gui/tema.py` é a fonte única de cor, tipografia, espaço, raio e elevação da GUI:

| Token | Claro | Escuro |
|---|---|---|
| primária, texto sobre ela, primária como texto | `#1976D2`, `#FFFFFF`, `#1565C0` | `#64B5F6`, `#0F172A`, `#64B5F6` |
| info: fundo, ícone, texto | `#E3F2FD`, `#1976D2`, `#0D47A1` | `#0C2A4A`, `#64B5F6`, `#BFDBFE` |
| sucesso: fundo, ícone, texto | `#E8F5E9`, `#2E7D32`, `#2E7D32` | `#14301B`, `#66BB6A`, `#86EFAC` |
| erro: fundo, ícone, texto | `#FFEBEE`, `#D32F2F`, `#C62828` | `#3B1518`, `#EF5350`, `#FCA5A5` |
| alerta: fundo, ícone, texto | `#FFF8E1`, `#E65100`, `#B45309` | `#3A2A0A`, `#FFB74D`, `#FCD34D` |
| fundo, superfície | `#FAFAFA`, `#FFFFFF` | `#0F172A`, `#1E293B` |
| texto, texto suave, borda | `#1E293B`, `#475569`, `#CBD5E1` | `#F1F5F9`, `#CBD5E1`, `#334155` |

Espaço `xs` 4 px, `sm` 8, `md` 16, `lg` 24, `xl` 32; raio 8 px (cartão) e 12 px (diálogo); elevação 1 `0 1px 2px rgb(0 0 0 / .08)` e 2 `0 8px 24px rgb(0 0 0 / .16)`; fonte do sistema (`"Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif`). Texto sobre fundo e sobre superfície tem contraste de pelo menos 4,5:1, e ícone e foco, de 3:1; o teste calcula cada par. O Quasar recebe a primária como `var(--ca-primaria)`, para o modo escuro trocá-la pelo CSS. O modo (`[gui] tema`, enum `TemaGui`: `sistema`, `claro`, `escuro`) é escolhido em Configurações > Aparência; `sistema` segue o sistema operacional. Status nunca depende só da cor: `gui/componentes/` (`cartao`, `Dialogo`, `aviso`, `situacao`, `estado_vazio`, `etapas`, `Assistente`) põe ícone e texto em cada tom (`info`, `sucesso`, `alerta`, `erro`), e o passo atual do assistente leva `aria-current="step"`.

**Onboarding (fase 6).** A tela `/inicio` é um assistente de 4 passos (nome; pasta, com as pastas de provas e análises em "Avançado"; opcionais desmarcados: IA para editais e aviso de versão nova; primeiro resultado: exemplo ou cadastro). Grava pelas mesmas `onboarding.aplicar` e `onboarding.gravar`; o aviso de versão nova grava `[atualizacao] verificar_ao_abrir`, e "Pular" no passo 3 não grava nenhum dos dois. A calibração da folha fica em Configurações (`aplicacao.inicio.salvar_calibracao`, que grava o mesmo `./.concurso/folha_calibrada.yaml`; a análise seguinte pela GUI é forçada, para reler as folhas), e o `doctor` fica no Sobre ("Conferir o ambiente"). Projeto sem concursos, sem relatório, sem recomendações ou sem prática mostra um estado vazio com a próxima ação.

Artefatos da release a partir da fase 6: os da fase 5, mais `atualizacao.json`, `atualizacao.json.sig` e `RELATORIO-SMOKE.md` (o resultado dos gates de cada sistema). O `--smoke` também imprime `partida: <s>` (falha acima de `CONCURSO_SMOKE_LIMITE_PARTIDA`, se definida) e confere o OCR numa imagem gerada.

## Fase 7: estudar com o open-notebook

**Pacote de estudo.** Uma release própria por versão, tag `estudo-v<versao>`, com `<versao> = <open-notebook>-<revisao>` (ex.: `estudo-v1.15.1-1`). Anexos: `estudo-<versao>-windows-x64.zip`, `estudo-<versao>-linux-x86_64.tar.xz`, `estudo.json` e `estudo.json.sig` (Ed25519 sobre os bytes exatos, com as mesmas `atualizador.CHAVES_PUBLICAS`). Montado por `empacotamento/estudo/montar.py` a partir de `empacotamento/estudo/versao.toml`.

```json
{
  "formato": 1,
  "versao": "1.15.1-1",
  "open_notebook": "1.15.1",
  "app_minimo": "0.7.0b1",
  "canal": "beta",
  "publicado_em": "2026-11-06",
  "modelo": {"nome": "paraphrase-multilingual-MiniLM-L12-v2", "revisao": "<commit do HF>", "dimensoes": 384},
  "artefatos": {
    "windows-x64": {"arquivo": "estudo-1.15.1-1-windows-x64.zip", "sha256": "<64 hex>", "tamanho": 400000000, "tamanho_extraido": 1100000000},
    "linux-x86_64": {"arquivo": "estudo-1.15.1-1-linux-x86_64.tar.xz", "sha256": "<64 hex>", "tamanho": 300000000, "tamanho_extraido": 1200000000}
  }
}
```

- `versao` segue `^\d+\.\d+\.\d+-\d+$`; `arquivo`, `^estudo-\d+\.\d+\.\d+-\d+-(windows-x64\.zip|linux-x86_64\.tar\.xz)$`, e precisa ser do sistema da chave. `canal` é `beta` quando `app_minimo` é pré-release. Um app usa o pacote só se a versão dele é pelo menos `app_minimo` (PEP 440).
- Conteúdo, na raiz `estudo-<versao>/`: `python/` (Python 3.12 standalone com o ambiente travado do open-notebook, onnxruntime e tokenizers), `open-notebook/` (código da tag, sem `frontend/`), `bin/surreal[.exe]` (SurrealDB 2.x), `modelo/` (`model_optimized.onnx`, `tokenizer.json`), `tiktoken/` (cache do `o200k_base`), `servidor_embeddings.py`, `LICENSES/` (MIT do open-notebook, BSL 1.1 do SurrealDB, Apache-2.0 do modelo, PSF) e `estudo.toml` (`versao`, `open_notebook`, `surreal`, `modelo`, `dimensoes`, `tiktoken`).
- `servidor_embeddings.py`: `POST /v1/embeddings` no formato da OpenAI (`input` texto ou lista de até 2048 textos; corpo de até 8 MB), `GET /health` e `GET /v1/models`; só em `127.0.0.1`, com `Authorization: Bearer <EMBEDDINGS_TOKEN>`; vetores de 384 dimensões, mean pooling normalizado, até 128 tokens por texto. Imprime `porta=<n>` na primeira linha.

**Instalação na máquina do usuário** (`~/.concurso/open-notebook/`): `pacote/<versao>/estudo-<versao>/` (os 2 pacotes mais recentes), `dados/` (pasta de trabalho dos processos, com `banco/` do SurrealDB e as migrations), `backups/<versao>-<data>/` (os 2 mais recentes, verificados arquivo a arquivo), `instalado.json` e `.trava` (instância única).

```json
{"atual": "1.15.1-1", "anterior": null, "ultima_partida": "1.15.1-1"}
```

- `ultima_partida` diferente de `atual` pede um backup do banco antes de subir; se a partida da versão nova falhar, o app volta para `anterior`.
- Processos, todos em `127.0.0.1` e em portas livres: `surreal start --bind 127.0.0.1:<p1> rocksdb:dados/banco` (usuário `concurso`, senha derivada da chave de cifra, porque o SurrealDB grava o usuário na primeira partida), `servidor_embeddings.py --porta <p2>`, a API (`uvicorn api.main:app --host 127.0.0.1 --port <p3>`) e o worker (`surreal_commands.cli.worker --import-modules commands`). A senha da API (`OPEN_NOTEBOOK_PASSWORD`) e o token dos embeddings são novos a cada sessão. A chave de cifra (`OPEN_NOTEBOOK_ENCRYPTION_KEY`) fica no keyring como `CONCURSO_OPEN_NOTEBOOK_CIFRA`. A chave da IA vai só por variável de ambiente da API e do worker.
- Os embeddings são registrados como modelo `openai_compatible` do tipo `embedding`, sem credencial (`OPENAI_COMPATIBLE_BASE_URL_EMBEDDING` e `OPENAI_COMPATIBLE_API_KEY_EMBEDDING` apontam para o nosso servidor), e marcados como `default_embedding_model`.
- Saída dos processos: `~/.concurso/logs/open-notebook-<processo>.log`. Três partidas seguidas com falha deixam a busca no índice local até o app reabrir; 10 min sem uso param os processos.

**Biblioteca local** (`~/.concurso/biblioteca/`): `arquivos/<sha256>.<ext>` (os originais) e `biblioteca.sqlite`, com a tabela `livros` e o índice FTS5 `busca`.

| Coluna de `livros` | Conteúdo |
|---|---|
| `sha` | SHA-256 do arquivo (chave; o mesmo conteúdo enviado de novo só atualiza `disciplina` e `concursos`) |
| `nome` | nome do arquivo sem extensão |
| `extensao` | `.pdf`, `.epub`, `.docx` ou `.txt` |
| `tamanho` | bytes (até 300 MB) |
| `disciplina` | escolhida no envio; `Geral` sem escolha |
| `concursos` | lista JSON dos `nome` de concurso associados |
| `estado` | `EstadoLivro`: `na_fila`, `lendo`, `lido`, `enviando`, `pronto`, `erro` |
| `pagina`, `paginas` | última página lida e total (a leitura retoma de `pagina + 1`) |
| `paginas_sem_texto` | páginas que ficaram sem texto (sem Tesseract ou OCR vazio) |
| `erro` | mensagem para o usuário |
| `adicionado_em` | ISO, segundos |
| `source_id`, `notebook_id` | o source no open-notebook e o notebook `Biblioteca — <disciplina>` |

- `busca` (FTS5, `unicode61 remove_diacritics 2`): `sha` e `pagina` (não indexadas), `texto` da página e `radicais` (snowball português). A consulta casa cada radical em `radicais` ou como prefixo em `texto`, e os termos do dicionário como frase; o trecho vem de `snippet` em `texto`, com o destaque entre `«` e `»`. `meta.versao_indice` diferente de `VERSAO_INDICE` refaz os radicais.
- Página: no PDF, a página do arquivo (OCR nas páginas com menos de 20 caracteres); no EPUB, o item da ordem de leitura; no DOCX, as quebras de página gravadas; no TXT, o form feed. Sem quebra, blocos de 3000 caracteres.
- `notebooks_biblioteca` (`disciplina`, `notebook_id`): o notebook `Biblioteca — <disciplina>` de cada disciplina no open-notebook do app, compartilhado entre os projetos (achado pelo ID e, sem ele, pelo nome).

**Envio ao open-notebook do app.** Cada livro lido vira um source de texto (`async_processing` e `embed` ligados) com o título do arquivo e o texto de cada página precedido por `[p. N]`. O estado passa a `enviando` e, quando `GET /api/sources/{id}/status` devolve `completed`, a `pronto`; `failed` vira `erro`. Trocar a disciplina move o vínculo do source para o notebook da nova disciplina; remover apaga o source.

**Sincronização com o open-notebook do app.** Sem `[open_notebook] enabled` e com o pacote de estudo instalado, a análise sincroniza sozinha, sem consentimento, com o candidato como pseudônimo. Em `.concurso/open_notebook.json`, a instância se chama `gerenciada` (a porta muda a cada sessão). Os notebooks do projeto levam o nome da pasta do projeto na frente (`Meus concursos · tcu_2025 — candidato 1`) e são achados só pelo ID guardado; `Legislação` é compartilhado e também é achado pelo nome. Os livros com o concurso entre os `concursos` são vinculados ao notebook dele.

**Perguntar** (`estudo.perguntar`, `concurso-analise livros ask`). `OndeProcurar`: `livros`, `analises` ou `tudo`; a disciplina filtra os livros.

- Livros: o open-notebook do app aponta os livros (busca `vector` e `text` nos notebooks `Biblioteca — <disciplina>`), e o índice local acha os trechos com página dentro deles, seguidos dos melhores trechos do índice. Com o open-notebook fora (ou sem o pacote de estudo), só o índice local, com o aviso "A busca continua nos seus livros".
- Análises: os parágrafos dos `*.md` em `analises/<candidato>/` com mais termos da pergunta, com a seção (o último título) em que estão.
- Cada trecho leva o nome do arquivo, a página (livro) ou a seção (análise) e o caminho para "Abrir arquivo". Sem nada, o aviso "Não achei isso nos seus livros".
- IA: só com `[llm] consentimento_livros = true` na configuração global, separado do `consentimento` do edital, e fora do `--offline`. A chave vai por variável de ambiente na partida da API e do worker (`OPENAI_COMPATIBLE_BASE_URL_LLM` e `OPENAI_COMPATIBLE_API_KEY_LLM`; na Anthropic, `ANTHROPIC_API_KEY`), nunca no banco; mudar a IA sobe os processos de novo. O modelo (`[llm] modelo`) é registrado sem credencial, como `openai_compatible` (ou `anthropic`), e usado nas três funções do `POST /api/search/ask/simple`. A resposta aparece como "Resposta da IA — confira nos trechos"; os `[source:<id>]` viram "Livros citados" e os trechos desses livros vêm primeiro.
- Sugestões: uma por tópico fraco persistente (`biblioteca.topicos_fracos`), "Revisar <tópico> nos seus livros"; em Resultados, os mesmos tópicos abrem `/estudar?aba=perguntar&pergunta=<tópico>`.

## Conferência pela tela

Nenhum arquivo de entrada exige edição à mão: `aplicacao/conferencia.py` grava cada um e a GUI chama.

- **Pendências (`pendencias(contexto, concurso)`):** as questões sem revisão cuja sugestão é `nao_mapeado` ou tem `score` abaixo de `SCORE_BAIXO` (0,05), mais os campos vazios do `edital_a_confirmar.yaml`. O card do concurso mostra "Conferir (N)".
- **Tópicos (`topicos_para_conferir`, `opcoes_de_topico`, `gravar_topicos`):** as opções são os tópicos do `edital_estruturado.json` do concurso (da pasta do candidato ou de qualquer `analises/**/<concurso>/`); sem ele, as sugestões do próprio CSV. A gravação usa `topicos.gravar_revisao_editada` e devolve se o arquivo mudou.
- **Dados do edital (`campos_a_confirmar`, `gravar_campos`):** o tipo de cada campo é `TipoCampo` (`data`, `inteiro`, `numero`): `data_prova` aceita `DD/MM/AAAA` ou `AAAA-MM-DD` e grava ISO; `alternativas` é inteiro de 2 a 10; `fator_penalidade` é número de 0 a 10 (aceita vírgula); `nota_corte` é número a partir de 0. Vazio esvazia a chave. `edital_a_confirmar.gravar_valores` troca só a linha `campo:` e preserva os comentários; se `carregar_concurso` recusar o resultado, o arquivo volta ao que era e a tela mostra o erro.
- **Disciplinas (`taxonomia`, `gravar_taxonomia`, `juntar_disciplinas`, `separar_disciplina`):** os grupos vêm da `taxonomia.yaml`; os nomes soltos são os da coluna `disciplina` dos `questoes.csv` das análises que a taxonomia não conhece. Um nome só pode estar em uma disciplina, e o bloco é `geral` ou `especifico`. Grava com `gravar_se_mudou`.
- **Reanálise (`reanalisar_afetados(opcoes, concurso)`):** a análise de sempre (`aplicacao.analise.analisar`), com o concurso conferido ou todos (taxonomia). Quem não mudou é pulado pelo manifesto.
- **Manifesto:** além dos arquivos da pasta do concurso (já com `revisao/` e `edital_a_confirmar.yaml`), entram os de `Contexto.extras_do_manifesto` (`.concurso/taxonomia.yaml`), cada um só quando existe, para não invalidar os manifestos gravados antes dele. Com o dicionário de temas ligado, entra também `.concurso/taxonomia_topicos.yaml`.

## Dicionário de temas

Opcional; sem `.concurso/taxonomia_topicos.yaml` (ou com `[dicionario] usar = false`), a sugestão de tópico e as saídas são as de antes, byte a byte. O arquivo é gravado pela tela Configurações > "Disciplinas e temas" > "Dicionário de temas" ou pelo `dicionario iniciar|sugerir|avaliar`; editá-lo à mão continua valendo.

```yaml
versao: 1
lingua_portuguesa:            # slug da disciplina (canônica ou do edital)
  crase:                      # slug do tópico
    nomes: [Emprego do sinal indicativo de crase]   # opcional: nomes exatos de tópicos do edital
    termos: [crase, acento grave]
    expressoes: [à medida que, às vezes]
    origem: [tcu_25]          # concursos de onde o termo foi tirado (aceito de uma sugestão)
recusados: [lingua_portuguesa/crase/fusao]
```

- **Validação (`ler_dicionario`):** campo desconhecido, versão diferente de 1 ou termo vazio ou com mais de 6 palavras é `ErroDoUsuario` (código 1), com o caminho do campo.
- **Casamento com o edital:** a disciplina casa pelo slug, pelo nome canônico da `taxonomia.yaml` ou pelas palavras-chave (uma contida na outra); o tópico casa por `nomes` (palavras-chave iguais) ou, sem `nomes`, quando as palavras do slug estão no nome do tópico.
- **Expansão:** a questão que cita um termo (palavra inteira, sem acento, caixa nem plural simples) ganha a marca `tema_<disciplina>_<topico>`, no máximo 3, as dos termos mais longos primeiro, e só das disciplinas permitidas para ela; o documento do tópico casado ganha só a marca. Um termo que já nomeia outro tópico da mesma disciplina no edital não marca nada, e a questão que o cita fica sem marcas da disciplina: o edital decide sozinho. A versão expandida decide `topico_sugerido` e `score`; a sem dicionário fica em `topico_tfidf` e `score_tfidf`.
- **Prática no TEC e livros:** o mesmo dicionário entra na ligação dos assuntos do TEC aos tópicos e, na busca nos livros, acrescenta em OR os outros termos dos temas que a pergunta cita.
- **Ganho (`avaliar_ganho`, `.concurso/ganho_dicionario.md`):** a verdade são as linhas da revisão com `topico` preenchido; o texto é o `enunciado` da revisão, e o edital, o `edital_estruturado.json`. A sugestão roda sem e com o dicionário, e as entradas cuja `origem` inclui o concurso ficam fora da avaliação dele. O relatório traz o acerto antes e depois (com n e Δ em p.p.), as corrigidas e as quebradas, o número de scores abaixo de 0,05 e a tabela por disciplina (n < 5 marcado como amostra insuficiente). O alerta liga quando há mais quebradas que corrigidas ou quando uma disciplina com n ≥ 5 cai, e a tela oferece desligar o dicionário.
- **Sugestões (`sugerir_termos`):** palavras (mais de 3 letras, fora das vazias) e pares de palavras que se repetem em ao menos 2 questões revisadas para o mesmo tópico, que não são termo dele, não estão em `recusados` e não estão só no nome do tópico; até 5 por tópico, dos mais frequentes e mais exclusivos do tópico para os outros. Aceitar grava o termo (par de palavras vai para `expressoes`) com a `origem`; recusar grava a chave `disciplina/topico/termo` em `recusados`.
- **Dicionário inicial (`concursos/dicionarios/inicial.yaml`):** Direito Administrativo, Direito Constitucional, Língua Portuguesa e Raciocínio Lógico; "Começar com o dicionário inicial" acrescenta só os tópicos que o projeto ainda não tem e liga o dicionário.

## Nome do concurso

A pasta (`provas/<id>`, o `nome` do `concurso.yaml`) é o identificador e nunca é renomeada. No cadastro pela tela, ela é automática: `sigla_ano` pela leitura rápida do edital (sem OCR nem IA), com `_2`, `_3` se já existir; sem edital, `concurso_AAAAMMDD`. O `add <pasta>` continua aceitando uma pasta explícita.

O nome mostrado (`nome_do_concurso`, em `analytics/nome_concurso.py`) tem título e subtítulo:

- **Título:** "SIGLA ANO — Cargo" ("TCU 2025 — Auditor Federal de Controle Externo"). Com a sigla tirada só das iniciais, o nome oficial fica no lugar dela.
- **Subtítulo:** o nome oficial, sem a sigla do fim, e o edital curto ("Tribunal de Contas da União, Edital nº 1/2025").

**Sigla e ano (`identificacao.sigla`, `identificacao.ano`).**

- **Sigla:** antes do número na linha do edital ("EDITAL ENAP Nº 114/2025") ou depois do travessão ("EDITAL Nº 1 – TCU/AUFC", sem os prefixos de processo `PSS`, `PS`, `PSE` e `CP`). Senão, entre parênteses ou depois do travessão no fim do nome oficial. Senão, as iniciais das palavras com maiúscula do nome oficial, sem de/da/do, com confiança 0,3 (`CONFIANCA_SIGLA_PELAS_INICIAIS`).
- **Ano:** o "nº X/AAAA" da linha do edital, senão o último "DE AAAA" dela, senão o ano de `data_prova` (fonte `config`).

**Precedência do nome**, com `fonte` e `confianca`:

1. `titulo` do `concurso.yaml` (fonte `config`, confiança 1);
2. a retificação mais recente;
3. o edital;
4. `pci.titulo` (fonte `pci`, confiança 0,6);
5. a IA, quando ligada, com trecho literal;
6. o nome do arquivo do edital ou do caderno, quando não é genérico (`edital`, `prova`, `caderno`, `gabarito`, `anexo`, `retificacao`);
7. a pasta.

Abaixo do edital, o nome leva o selo "a confirmar" na tela e no `index.html`, e "O que o app decidiu sozinho" diz de onde ele veio. "Corrigir nome" grava `titulo`; vazio, apaga o campo e volta ao do edital.

**Rótulo dos notebooks (`rotulo_do_concurso`):** "slug: nome oficial — cargo"; sem nome oficial ou cargo, só o slug.
