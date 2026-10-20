# Análise de Desempenho em Concursos

Pipeline local que corrige suas provas de concurso e mostra **em quais disciplinas e tópicos do edital você perde pontos**, por concurso e entre concursos.

Para cada concurso, a partir do edital, dos cadernos, dos gabaritos e da sua folha de resposta (ou de um `respostas.txt`), gera:

- respostas extraídas, com a confiança da leitura;
- desempenho por disciplina e por tópico;
- gráficos;
- um relatório em markdown.

O consolidado responde: _"em quais tópicos meu desempenho é consistentemente baixo entre concursos?"_

Bancas suportadas: Cebraspe (certo/errado, um erro anula um acerto), FGV, SELECON e Quadrix (múltipla escolha).

## Instalação

1. Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/) e rode na raiz do projeto:

   ```bash
   uv sync
   ```

2. Opcional: o [Tesseract](https://github.com/tesseract-ocr/tesseract), só necessário para PDFs escaneados (sem camada de texto). No Ubuntu/WSL:

   ```bash
   sudo apt install tesseract-ocr tesseract-ocr-por
   ```

O comando da CLI é `uv run concursos` (ou `concursos`, com o ambiente virtual ativado).

## Fluxo: coletar, cadastrar e analisar

O jeito mais fácil é o assistente interativo, que guia cada passo e chama os comandos abaixo:

```bash
./scripts/novo_concurso.sh
```

Passo a passo manual:

1. **Coletar:** crie `provas/<concurso>/` (ex.: `provas/tcu_25/`) e copie os arquivos com os nomes que vieram da banca:
   - edital e anexos;
   - cadernos de prova;
   - gabaritos (preliminar ou definitivo; PDFs com vários cargos são aceitos);
   - folha de resposta (PDF ou imagem) ou `respostas.txt`;
   - opcional: o resultado oficial com a sua nota.
2. **Cadastrar:**

   ```bash
   uv run concursos adicionar provas/tcu_25
   ```

   O cadastro detecta o papel de cada arquivo (edital, prova, gabarito, folha, respostas, resultado), a banca e o status do gabarito. Pergunta só o que for ambíguo (cargo, tipo do caderno, gabarito a usar) e mostra o `concurso.yaml` antes de gravar. Com `--aceitar-sugestoes`, não pergunta nada e falha se algo for ambíguo.
3. **Analisar:**

   ```bash
   uv run concursos analisar              # todos os concursos que mudaram
   uv run concursos analisar --concurso tcu_25
   uv run concursos analisar --forcar     # reprocessa tudo (ex.: mudou um limiar)
   ```

   A análise é incremental: um concurso só é reprocessado se algum arquivo da pasta mudou (inclusive o `concurso.yaml` e a revisão de tópicos).

### Situação dos concursos

```bash
uv run concursos status
```

Mostra cada concurso com:

- **situação:** `completo`, `incompleto` (falta respostas, gabarito ou edital, com o caminho do arquivo ausente) ou `desatualizado` (arquivo novo não cadastrado ou configuração inválida; rode `adicionar` de novo);
- **status do gabarito:** `preliminar`, `definitivo` ou `misto`.

## Formato do `respostas.txt`

Use quando não tiver a folha de resposta. Escreva uma questão por linha:

```text
# comentários começam com #
1 A
02: C
3-E
4 -
```

- Múltipla escolha aceita de `A` a `E`; certo/errado (Cebraspe) aceita `C` ou `E`.
- `-` ou valor vazio indicam branco. Questões omitidas também contam como branco.
- Separadores aceitos: espaço, `:`, `;`, `,`, `.` e `-`. Zeros à esquerda são ignorados.
- Erros indicam o número da linha.

Um gabarito em texto usa o mesmo formato, com `X` ou `*` para questão anulada.

## Revisão de tópicos

Com o edital cadastrado, cada questão recebe uma disciplina e um tópico sugeridos. A sugestão compara o texto da questão (na Cebraspe, o bloco "julgue os itens") com os tópicos do edital, por similaridade TF-IDF, e vem com um score.

Na primeira análise é criado `provas/<concurso>/revisao/questoes_revisado.csv`, com:

- as sugestões;
- o score;
- um trecho do enunciado;
- as colunas `disciplina` e `topico` vazias.

Preencha essas colunas só nas questões que quiser corrigir e rode `analisar` de novo. A revisão tem prioridade sobre a sugestão e entra no desempenho por tópico. O relatório lista as sugestões com score baixo ainda não revisadas.

Se o conteúdo programático não puder ser extraído do edital, a análise para com uma mensagem. Nesse caso, forneça um edital manual em YAML (veja [docs/modelo.md](docs/modelo.md#edital-manual)).

## Troca de gabarito preliminar para definitivo

Analise com o gabarito preliminar enquanto o definitivo não sai; o relatório mostra o selo **Gabarito preliminar (provisório)**. Quando o definitivo sair, coloque-o na pasta (ou sobrescreva o arquivo do preliminar) e rode `analisar`.

Se o definitivo casar com a prova configurada (mesma banca, cargo/tipo e faixa de itens), a análise:

- atualiza o `concurso.yaml`;
- move o preliminar para `ignorar` e registra o evento em `historico`;
- guarda as saídas anteriores em `analises/<concurso>/historico/`;
- gera `diff_gabarito.csv`, com as questões alteradas e anuladas, sua resposta e o acerto antes e depois;
- adiciona ao relatório a seção "Preliminar → Definitivo".

Em qualquer outro caso (outro cargo, dois candidatos, arquivo desconhecido), o concurso fica `desatualizado` até você rodar `adicionar`.

## Saídas

Por concurso, em `analises/<concurso>/`:

| Arquivo | Conteúdo |
|---|---|
| `respostas_extraidas.csv` | Todas as questões: alternativa marcada, estado, `confianca_ocr`, `revisar`, origem, arquivo, página |
| `desempenho_por_disciplina.csv`, `desempenho_por_topico.csv` | `concurso, prova, disciplina, topico, total, acertos, erros, percentual, em_branco, anuladas, nota_liquida` |
| `questoes.csv` | Por questão: disciplina, tópico sugerido e final, score, gabarito, resposta, resultado |
| `relatorio.md` e `graficos/*.png` | Resumo, gráficos, tópicos mais fracos, questões para revisar, validação oficial |
| `edital_estruturado.json` | Conhecimento → disciplina → tópicos do cargo |
| `diff_gabarito.csv`, `historico/` | Só após a troca de gabarito |
| `depuracao/*.png` | Bolhas detectadas na folha de resposta |

No consolidado, em `analises/consolidado/`:

- `desempenho_geral.csv`: o desempenho por tópico de todos os concursos;
- `comparativo_concursos.md`: tópicos e disciplinas abaixo do limiar em pelo menos dois concursos, concursos incompletos, status do gabarito e validação com o resultado oficial.

O percentual é de mérito: anuladas contam como acerto, mas ficam fora do percentual.

## Configuração

O `config.yaml` na raiz guarda os limiares globais e é opcional:

- `limiar_confianca` (0,75): leituras abaixo dele ficam com `revisar = True`;
- `limiar_topico_baixo` (0,6): define o desempenho baixo no comparativo.

Depois de mudar um limiar, rode `analisar --forcar`.

O `concurso.yaml` de cada pasta é gerado pelo `adicionar` e pode ser editado à mão. O schema completo está em [docs/modelo.md](docs/modelo.md).

## Privacidade

`provas/` e `analises/` ficam fora do git (`.gitignore`) por conterem dados pessoais (nome, CPF, notas). Modelos de OCR também são ignorados.

## Desenvolvimento

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

O pre-commit roda ruff e pytest antes de cada commit (`uv run pre-commit install`). A especificação está em [docs/spec.md](docs/spec.md) e o modelo de domínio em [docs/modelo.md](docs/modelo.md).
