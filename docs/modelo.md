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
