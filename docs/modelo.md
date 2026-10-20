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
- modelo: `bruta` (acerto vale 1, sem desconto) ou `liquida` (cada erro anula `fator_penalidade` acertos);
- fator de penalidade (1,0 na Cebraspe; 0 nas FGV analisadas);
- nota máxima e nota de corte do conjunto das provas objetivas;
- fonte: `edital`, `config` ou `default`;
- confiança da extração (0–1) e o trecho, o documento e a página de onde a regra foi lida.

A regra é extraída por regex do texto dos documentos do edital (anexos primeiro, sem OCR). A precedência é edital, depois `concurso.yaml`, depois default (`bruta`, fator 0). A nota máxima e a nota de corte seguem a mesma ordem, campo a campo. Sem nota máxima em nenhuma fonte, ela é o número de itens do concurso.

A análise emite aviso quando:
- a regra cai no default (o aviso é mais forte se o edital mencionar penalidade: "ponto negativo", "desconto de", "descontado", "anula um acerto");
- o fator do bloco `correcao` difere do edital (vale o edital);
- a `pontuacao` declarada contradiz a regra vinda do edital ou do bloco `correcao` (`cebraspe` com fator diferente de 1, ou `simples` com fator diferente de 0). No default, vale só o aviso de default.

A `pontuacao` continua alimentando a `nota_liquida` dos CSVs; o modelo de correção alimenta a análise evolutiva.

**Pontuação por item.** Cada questão não anulada recebe três pontuações:

| versão | acerto | erro | branco |
|---|---|---|---|
| bruta | 1 | 0 | 0 |
| corrigida (regra do edital) | 1 | \(-f\) | 0 |
| ajustada ao acaso | 1 | \(-1/(k-1)\) | 0 |

\(f\) é o fator de penalidade, e \(k\) é o número de alternativas: 2 em `certo_errado` (erro vale −1) e 5 em `multipla_escolha` (erro vale −0,25). A versão ajustada é a métrica padrão para comparar concursos, porque um chute puro vale 0 nos dois formatos.

As anuladas ficam fora das três versões (não medem conhecimento) e os percentuais podem ser negativos. A exceção é a nota do concurso, que segue o edital: soma das pontuações corrigidas, com cada anulada valendo 1 ponto. A nota normalizada é \(\max(0, \text{nota}/\text{nota máxima} \times 100)\), truncada em 0 só ela. Na Cebraspe, a nota corrigida é igual à soma da `nota_liquida` legada.

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
resultado_oficial:             # opcional
  arquivo: resultado.pdf
  identificador: '12345678'    # inscrição do candidato
  pesos:                       # opcional; peso por faixa de itens
    - {itens: [101, 200], peso: 2}
correcao:                      # opcional; complementa ou substitui a regra extraída do edital
  modelo: liquida              # bruta | liquida (liquida exige fator > 0; bruta exige fator 0)
  fator_penalidade: 1          # acertos anulados por erro
  nota_maxima: 200             # padrão: número de itens
  nota_corte: 60               # nota mínima no conjunto das provas objetivas
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
- **`correcao.json`:** lista de configurações de correção (uma por variante; hoje sempre uma). Campos:
  - `modelo`, `fator_penalidade`, `nota_maxima`, `nota_corte`;
  - `fonte` (`edital | config | default`), `confianca`;
  - `trecho_origem`, `documento_origem`, `pagina_origem` (preenchidos quando a fonte é o edital);
  - `variante` (`null` quando o concurso não tem variantes).
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
