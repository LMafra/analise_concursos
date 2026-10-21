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

A `pontuacao` continua alimentando a `nota_liquida` dos CSVs; o modelo de correção alimenta a análise evolutiva.

**Pontuação por item.** Cada questão não anulada recebe três pontuações:

| versão | acerto | erro | branco |
|---|---|---|---|
| bruta | 1 | 0 | 0 |
| corrigida (regra do edital) | 1 | \(-f\) | 0 |
| ajustada ao acaso | 1 | \(-1/(k-1)\) | 0 |

\(f\) é o fator de penalidade, e \(k\) é o número de alternativas: 2 em `certo_errado` (erro vale −1) e 5 em `multipla_escolha` (erro vale −0,25). A versão ajustada é a métrica padrão para comparar concursos, porque um chute puro vale 0 nos dois formatos.

As anuladas ficam fora das três versões (não medem conhecimento) e os percentuais podem ser negativos. O peso do item não entra nessas pontuações. A exceção é a nota do concurso, que segue o edital: soma das pontuações corrigidas multiplicadas pelo peso de cada item, com cada anulada valendo o seu peso. A nota normalizada é \(\max(0, \text{nota}/\text{nota máxima} \times 100)\), truncada em 0 só ela. Na Cebraspe, a nota corrigida é igual à soma da `nota_liquida` legada.

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
- **`edital_estruturado.json`:** `fonte`, `cargo` e `conhecimentos[].disciplinas[].topicos[]`. Cada tópico tem `numero`, `nome`, `descricao` e `peso`.
- **`correcao.json`:** lista de configurações de correção (uma por variante; uma só quando o concurso não tem variantes). Campos:
  - `modelo`, `fator_penalidade`, `nota_maxima`, `nota_corte`;
  - `pesos`: lista de `{inicio, fim, peso}` (vazia quando todos os itens valem 1);
  - `fonte` (`edital | config | default`), `confianca`;
  - `trecho_origem`, `documento_origem`, `pagina_origem` (preenchidos quando a fonte é o edital);
  - `variante` (`null` quando o concurso não tem variantes);
  - `data_prova` (ISO 8601 ou `null`) e `fonte_data` (`edital | config`, `null` sem data), iguais em todas as variantes.
- **`validacao_oficial.json`:** `arquivo`, `descricao` e `alerta`. Só existe quando há resultado oficial.
- **`relatorio.md` e `graficos/*.png`:** o relatório; os gráficos ficam na pasta indicada.
- **`historico/<data>_gabarito_preliminar/`:** cópia das saídas anteriores à troca de gabarito.

No consolidado, em `analises/consolidado/`:

- **`desempenho_geral.csv`:** junção dos `desempenho_por_topico.csv` de todos os concursos analisados, com as mesmas colunas.
- **`comparativo_concursos.md`:** reúne:
  - desempenho e status do gabarito por concurso;
  - tópicos e disciplinas abaixo de `limiar_topico_baixo` em pelo menos dois concursos (nomes comparados por palavras-chave);
  - concursos incompletos ou desatualizados, com o motivo;
  - validação com o resultado oficial.
- **`consolidado.parquet`:** cache da análise evolutiva (`concursos.analytics.consolidado`), com uma linha por questão de cada concurso que tem `questoes.csv`, `correcao.json` e `concurso.yaml`. É reconstruído quando um `questoes.csv`, `correcao.json` ou `concurso.yaml` fica mais novo que ele, ou quando o conjunto de concursos analisados muda. Colunas:
  - de `questoes.csv`: `concurso` (nome da pasta), `prova`, `questao`, `disciplina`, `topico`, `gabarito`, `anulada`, `resposta`, `resultado` (`acerto | erro | branco`);
  - do `concurso.yaml`: `formato`, `banca`, `cargo`, `nivel` (`federal | estadual | municipal | nao_informado`), `escolaridade` (`superior | medio | nao_informado`);
  - do `correcao.json` (a primeira configuração, quando há variantes): `data_prova` (data, vazia sem data), `modelo_correcao` (`bruta | liquida | ponderada`), `fator_penalidade`, `nota_maxima`, `nota_corte` (vazia sem corte), `fonte_correcao` (`edital | config | default`), `confianca_correcao`;
  - `pontos_bruta`, `pontos_corrigida` e `pontos_ajustada`: a pontuação por item da tabela acima, sem peso, vazia nas anuladas;
  - `peso__<variante>`: o peso do item em cada variante (`peso__padrao` quando o concurso não tem variantes), vazio nos concursos sem aquela variante;
  - `ordem`: posição cronológica do concurso pela data da prova, a partir de 1 (datas iguais empatam), vazia sem data;
  - `n_topico`: quantidade de questões do tópico naquela prova (o `total` de `desempenho_por_topico.csv`).

  `validar_schema` confere colunas, tipos, domínios, a existência de ao menos uma coluna `peso__` e o número de linhas igual à soma das linhas de todos os `questoes.csv` (um concurso analisado que ficou fora reprova a contagem).
