# Spec: Generalização, Portabilidade e UX de 1 Comando (Fase 4)

Tickets: `.scratch/generalizacao-portabilidade/issues/`. Pesquisa de apoio (bancas, UX de CLI, OMR, distribuição): `docs/pesquisa-fase4.md`.

## Problem Statement

As fases 1 a 3 entregaram um pipeline que corrige e analisa provas de concurso, mas ele só funciona para um candidato, numa máquina e com as bancas que esse candidato já fez.

Para operá-lo, é preciso clonar o repositório e rodar `uv sync` dentro dele. A raiz do projeto é achada procurando um `pyproject.toml`, e a configuração (`config.yaml`) e a taxonomia de disciplinas ficam na raiz do código.

Um concurso de banca nova exige editar Python:

- As bancas aceitas são uma lista fixa: Cebraspe, FGV, Selecon e Quadrix.
- O cadastro, a segmentação da prova e o leitor de gabarito têm ramos `banca == 'cebraspe'`.
- Os modelos de folha são três templates com nome de concurso.
- A múltipla escolha supõe 5 alternativas, mas editais reais de IBFC e Idecan usam 4.

Uma segunda pessoa não tem lugar no projeto: folha, respostas e inscrição moram no `concurso.yaml`, misturadas aos dados do concurso, e as saídas não separam candidatos.

As falhas não dão caminho de correção:

- Um edital fora do padrão gera exceção ou campo vazio.
- Uma folha fora dos três templates não é lida.
- Uma disciplina fora da taxonomia reprova a validação inteira.
- Os erros chegam como log técnico, sem dizer o que fazer.

Para usar no dia a dia, o candidato precisa saber quais comandos existem, em que ordem rodá-los, onde fica cada arquivo e como abrir resultados espalhados entre markdown, PNG e notebooks.

## Solution

Um único comando, `uvx concurso-analise`, sem clonar nada.

Na primeira execução, ele faz até 6 perguntas em português, com padrão sugerido, e migra com backup os dados que encontrar das fases 1 a 3. Em toda execução, varre a pasta de provas, processa só o que é novo ou mudou para cada par (candidato, concurso) e abre no navegador um relatório HTML por candidato.

Banca, edital ou folha nova entram sem editar código:

- **Perfis de banca** declaram formato, alternativas, penalidade, peso, corte, desempate, leitor de gabarito e segmentação. Vêm embutidos para Cebraspe, FGV, FCC, Vunesp, IBFC, Idecan, Selecon, Quadrix e `generic`, e outros podem ser instalados como plugin.
- **Um edital desconhecido** passa por camadas, na ordem: perfil, LLM opcional com citação obrigatória, heurística genérica e modo mínimo. Se ainda faltar algo, o app gera um arquivo de confirmação para o usuário completar.
- **Uma folha desconhecida** também passa por camadas: perfil, detecção automática, calibração com uma folha de amostra, CSV de revisão e, por fim, CSV digitado.

Cada decisão automática aparece no log e no relatório, com fonte e confiança.

No layout multi-candidato, o concurso guarda os arquivos comuns e cada candidato tem uma subpasta com as próprias respostas; as saídas ficam em `analises/<candidato>/<concurso>/`.

Erros saem em português, com uma linha de dica executável e sem traceback, e o comando `doctor` diagnostica o ambiente.

## User Stories

### Primeira execução e onboarding

1. Como candidato que nunca viu o projeto, quero rodar um único comando com só o `uv` instalado, para não clonar repositório nem conhecer Python.
2. Como candidato novo, quero que a primeira execução me faça no máximo 6 perguntas com padrões entre colchetes, para terminar o onboarding em menos de 90 segundos.
3. Como candidato, quero aceitar todos os padrões apertando Enter, para começar sem decidir o que não entendo.
4. Como candidato, quero ver o progresso `[n/6]` em cada pergunta, para saber quanto falta.
5. Como candidato, quero ver um resumo do que será gravado e confirmar antes, para não ter arquivos criados sem saber.
6. Como candidato, quero que, se a pasta de provas não existir, o app ofereça criá-la com instruções do que colocar dentro.
7. Como candidato com uma folha preenchida, quero calibrar o OCR digitando as respostas reais das 5 primeiras questões, para que a leitura fique confiável sem clicar em nada.
8. Como candidato, quero escolher se uso LLM e qual provedor, sabendo que ele vem desligado por padrão.
9. Como candidato, quero que o wizard rode o `doctor` no fim, para descobrir na hora o que falta instalar.
10. Como candidato que roda em CI ou sem terminal interativo, quero que o app use os padrões sem perguntar.
11. Como power user, quero responder a cada pergunta do wizard por flag ou variável de ambiente, para automatizar a instalação.
12. Como candidato, quero refazer o onboarding com `init`, para trocar de candidato ou de pastas.

### Execução recorrente e idempotência

13. Como candidato, quero rodar sempre o mesmo comando, sem subcomando, para não decorar uma sequência de passos.
14. Como candidato, quero que a segunda execução seguida não reprocesse nada, para que seja rápida e não altere arquivos.
15. Como candidato, quero que trocar um arquivo de um concurso reprocesse só aquele concurso.
16. Como candidato, quero que trocar a folha de um candidato reprocesse só aquele par (candidato, concurso).
17. Como candidato, quero que corrigir o `edital_a_confirmar.yaml` reprocesse o concurso para todos os candidatos, já que o edital é comum.
18. Como candidato, quero `--force` para reprocessar mesmo sem mudança.
19. Como candidato, quero `--dry-run` para listar o que seria feito sem gravar nada, nem configuração nem migração.
20. Como candidato, quero ver o progresso por concurso e por etapa, para saber que o app não travou.
21. Como candidato, quero que o relatório abra no navegador só na primeira vez ou quando algo mudou; nas outras vezes, o app só imprime o caminho.
22. Como candidato, quero `--quiet` e `--verbose`, para ajustar quanto o app fala.
23. Como candidato, quero que o gabarito definitivo novo seja detectado e aplicado sozinho, como já é hoje.

### Multi-candidato

24. Como candidato, quero minhas respostas numa subpasta minha dentro do concurso, para que edital, prova e gabarito não sejam duplicados.
25. Como segundo candidato, quero acrescentar minha folha com `add <arquivo> --candidate <nome>`.
26. Como candidato, quero que uma subpasta de candidato sem perfil crie o candidato com aviso na varredura, para que copiar a pasta baste.
27. Como usuário com mais de um candidato, quero `--candidate`, cujo padrão é o último usado neste projeto.
28. Como usuário, quero as saídas em `analises/<candidato>/<concurso>/` e um consolidado por candidato, para que os resultados nunca se misturem.
29. Como usuário, quero `--all-candidates` para um comparativo entre candidatos.
30. Como candidato, quero que minha inscrição no resultado oficial fique no meu `candidato.yaml`, para que outro candidato não a herde.

### Migração das fases 1 a 3

31. Como usuário das fases 1 a 3, quero que a primeira execução da v4 migre meus dados automaticamente.
32. Como usuário das fases 1 a 3, quero um backup completo, verificado por hash, antes de qualquer mudança.
33. Como usuário das fases 1 a 3, quero que nenhuma saída se perca e que `correcao.json`, os CSVs e o parquet mantenham schema e valores.
34. Como usuário das fases 1 a 3, quero que `config.yaml` e `taxonomia.yaml` migrem para a configuração do projeto, para que o pacote não tenha dado meu.
35. Como usuário, quero que uma pasta antiga copiada depois da migração seja migrada na hora, com aviso.
36. Como usuário, quero que a migração rode uma vez só e fique registrada.
37. Como usuário, quero ver no `--dry-run` a lista de operações que a migração faria.
38. Como usuário do CLI antigo, quero que `concursos adicionar/analisar/status` continue funcionando, com aviso de obsoleto.

### Perfis de banca

39. Como candidato de banca conhecida, quero que o app detecte a banca pelo texto dos PDFs e aplique o perfil dela.
40. Como candidato de prova Cebraspe certo/errado, quero a penalidade de um erro por acerto aplicada por padrão.
41. Como candidato de prova Cebraspe de múltipla escolha, quero que o edital vença o perfil e não haja penalidade.
42. Como candidato de IBFC ou Idecan, quero que folhas e gabaritos de 4 alternativas sejam aceitos.
43. Como candidato, quero que o perfil só preencha o que o edital e o `concurso.yaml` não disseram, com fonte `perfil` e confiança menor.
44. Como candidato da FCC com escore padronizado, ou de concurso com corte por quantidade de classificados, quero um aviso de "corte não calculável localmente", em vez de um número inventado.
45. Como candidato, quero a regra de não zerar disciplina (FGV, Idecan) tratada como corte, para que o "atingido" a respeite.
46. Como mantenedor, quero adicionar uma banca com um YAML e, se preciso, um leitor registrado por entry point, sem tocar no núcleo.
47. Como mantenedor, quero um template documentado de banca nova, a partir do `generic`.
48. Como usuário, quero que nenhum perfil embutido contenha dado pessoal.

### Edital desconhecido

49. Como candidato de banca nunca vista, quero que o app siga com o que conseguiu extrair e avise o que faltou, em vez de abortar.
50. Como candidato, quero que o modo mínimo extraia ao menos disciplinas e tópicos do conteúdo programático.
51. Como candidato, quero um `edital_a_confirmar.yaml` na pasta do concurso, com o que foi extraído e os campos faltantes vazios e comentados.
52. Como candidato, quero que salvar esse arquivo e rodar o comando de novo aplique as correções.
53. Como candidato com edital escaneado, quero saber se falta o Tesseract e como instalá-lo, em vez de receber um edital vazio.
54. Como candidato, quero no relatório um selo por concurso com o nível de confiança da extração do edital.
55. Como candidato, quero que todo valor do edital continue com trecho, documento e página, como na fase 3.

### Folha desconhecida

56. Como candidato com folha fora dos perfis, quero que o app detecte a grade sozinho.
57. Como candidato, quero uma confiança em cada leitura, e as leituras de confiança baixa com `revisar=true` no CSV.
58. Como candidato, quero corrigir o CSV no Excel ou no LibreOffice e rodar `analyze <id> --reuse-csv`.
59. Como candidato, quero que a revisão vire entrada do meu candidato e vença a folha.
60. Como candidato, quero um aviso se a folha mudar depois da revisão.
61. Como candidato sem folha, ou com OCR inutilizável, quero informar as respostas num CSV `questao,alternativa`.
62. Como candidato, quero a imagem de depuração da leitura, como hoje.

### LLM opcional

63. Como candidato, quero que nenhuma chamada de rede aconteça sem eu ter configurado o LLM.
64. Como candidato, quero que só o texto do edital e dos anexos seja enviado, nunca respostas, folha, notas ou inscrição.
65. Como candidato, quero ver, na primeira chamada, o provedor e o que vai ser enviado, e confirmar uma vez.
66. Como candidato, quero que todo valor do LLM traga um trecho literal do edital, e que um valor sem trecho conferível seja descartado.
67. Como candidato, quero poder usar OpenAI, OpenRouter, Gemini, Ollama local ou Anthropic.
68. Como candidato, quero que a chave venha de variável de ambiente ou do keyring e nunca fique em texto plano sem aviso.
69. Como candidato, quero `--no-llm` e `--offline` para forçar o caminho local.

### Relatório

70. Como candidato, quero um relatório HTML por candidato que abra no navegador sem instalar Jupyter.
71. Como candidato, quero ver os concursos, o desempenho por disciplina e por tópico, a evolução e o gap para o corte, reaproveitando os textos e gráficos das fases 1 a 3.
72. Como candidato, quero que o relatório diga o que o app decidiu sozinho e por quê.
73. Como candidato, quero `report` para reabrir o último relatório.
74. Como candidato, quero `export --format csv|parquet|md`.
75. Como power user, quero que os notebooks continuem funcionando com a configuração nova.

### Erros e doctor

76. Como candidato, quero toda mensagem de erro em português, com até duas linhas e uma linha `dica:` com o comando que resolve.
77. Como candidato, quero nunca ver traceback; o detalhe técnico fica num log cujo caminho a mensagem informa.
78. Como candidato que rodou sem a pasta de provas, quero uma mensagem que diga onde ela era esperada e como criá-la ou apontar outra.
79. Como candidato, quero que o `doctor` verifique `uv`, Python, Tesseract com português, permissão de escrita, espaço em disco e a chave do LLM, cada item com ✓, ! ou ✗ e o comando de correção para o meu sistema.
80. Como candidato, quero que o `doctor` explique que o poppler não é necessário.
81. Como candidato, quero que o `doctor` saia com código diferente de zero quando houver problema.
82. Como candidato, quero que configuração inválida diga qual campo, qual valor e quais são os aceitos, como hoje.

### Distribuição e portabilidade

83. Como candidato no Linux, no macOS ou no Windows (via WSL2 no mínimo), quero o mesmo comando funcionando.
84. Como candidato no WSL, quero que o relatório abra no navegador do Windows.
85. Como candidato sem `uv`, quero uma alternativa de uma linha com Docker, já com `tesseract-ocr-por`.
86. Como candidato, quero que caminhos com espaço e acento funcionem.
87. Como candidato, quero `upgrade` para atualizar a ferramenta quando eu pedir, nunca sozinha.
88. Como mantenedor, quero o lockfile commitado e o Python 3.11 e 3.12 suportados.

### Extensão e manutenção

89. Como mantenedor, quero perfis de banca, de OCR e de edital carregáveis por entry point, com fallback embutido.
90. Como mantenedor, quero que o pacote nunca contenha nome, CPF, inscrição ou slug de candidato, verificado por teste.
91. Como mantenedor, quero que toda saída gerada traga origem e data.
92. Como mantenedor, quero o `AGENTS.md` com as convenções de perfil, o template de banca nova e a lista do que está fora de escopo.

## Implementation Decisions

### Distribuição e entrada

- **Pacote e executáveis:**
  - A distribuição e o executável se chamam `concurso-analise`, e o import continua `concursos`.
  - O executável antigo `concursos` continua como alias, com aviso de obsoleto uma vez por execução, até a fase 5.
- **Python e dependências de sistema:**
  - Python `>=3.11,<3.13`.
  - Tesseract e poppler não vêm pelo pip. O PDF já é rasterizado pelo `pypdfium2`, então o poppler não é necessário. O Tesseract com `por` é opcional e só serve a PDF escaneado.
  - Extras opcionais: `llm` (cliente HTTP e keyring) e `notebooks`.
- **CLI:**
  - Typer, com comando padrão sem subcomando.
  - Subcomandos: `init`, `add`, `analyze`, `status`, `report`, `doctor`, `export` e `upgrade`.
  - Flags universais: `--yes`, `--quiet`, `--verbose`, `--dry-run`, `--force`, `--data-dir`, `--candidate`, `--all-candidates`, `--no-llm`, `--offline` e `--no-open`.
  - O wizard só abre com TTY e fora de CI.
- **Erros:**
  - Toda exceção de domínio vira uma mensagem de até duas linhas: a causa e uma `dica:` com comando.
  - Uma exceção inesperada vira uma mensagem genérica com o caminho do log.
  - O log técnico, com traceback, fica na pasta de logs global.
  - Código de saída: 0 para sucesso, 1 para falha do usuário ou dos dados, 2 para falha do ambiente.

### Contexto, configuração e layout

- **Resolvedor de contexto:** todo caminho vem dele, e nada mais procura o `pyproject.toml`.
  - A pasta global é `~/.concurso/`, sobreposta por `CONCURSO_HOME`.
  - A configuração do projeto fica em `.concurso/`, no diretório atual, sobreposta por `--data-dir`.
  - Precedência: flag, variável de ambiente, configuração do projeto, configuração global, padrão.
- **Configuração global (TOML):** preferências, candidatos conhecidos, consentimento do LLM, provedor e nome da variável da chave. Nunca guarda a chave.
- **Perfil de candidato (TOML):** nome de exibição e slug.
- **Configuração do projeto (TOML):**
  - pasta de provas, pasta de análises e último candidato usado;
  - os limiares atuais (`limiar_confianca` e `limiar_topico_baixo`) e o concurso-alvo;
  - os perfis de OCR calibrados e a taxonomia do projeto.
- **Entrada:**
  - A pasta do concurso guarda os arquivos comuns, o `concurso.yaml`, a revisão de tópicos e o `edital_a_confirmar.yaml`.
  - A subpasta de cada candidato guarda folha, `respostas.txt` ou CSV, `respostas_revisadas.csv` e `candidato.yaml`. Este traz a fonte de respostas, o template ou perfil de OCR, o total de itens e o identificador no resultado oficial.
  - A seção de respostas e o identificador saem do `concurso.yaml`.
- **Saída:** `analises/<candidato>/<concurso>/`, o consolidado por candidato e o `index.html` por candidato. O comparativo entre candidatos só sai com `--all-candidates`.
- **Manifesto:**
  - É por par (candidato, concurso). O hash cobre os arquivos comuns (inclusive o `edital_a_confirmar.yaml`), os arquivos do candidato, a versão da análise, a versão dos perfis usados e os campos de configuração que afetam o resultado.
  - Mudar um arquivo comum invalida todos os candidatos do concurso.
- **Taxonomia:**
  - Fica na configuração do projeto.
  - Uma disciplina sem entrada vira canônica de si mesma, com aviso em vez de reprovar a validação. O bloco vem da prova, do perfil ou fica não informado.

### Migração

- **Detecção:** saídas de concurso direto em `analises/`, ou `config.yaml`/`taxonomia.yaml` na raiz do projeto, sem o registro de migração.
- **Passos:**
  1. Backup com hash verificado na pasta global.
  2. Criação do candidato padrão.
  3. Movimentação das saídas para a pasta do candidato.
  4. Extração da seção de respostas e do identificador de cada `concurso.yaml` para o `candidato.yaml`. A folha fica no lugar, referenciada por caminho relativo.
  5. Conversão da configuração e cópia da taxonomia.
  6. Registro da migração e recálculo dos manifestos, sem reprocessar.
- **Pasta legada copiada depois:** a mesma função a migra na hora, só aquela pasta.
- **`--dry-run`:** lista as operações e não grava nada.

### Perfis

- **Carga:** três tipos, carregados por entry point (`concurso.banca`, `concurso.ocr`, `concurso.edital`). Os embutidos são YAML versionados dentro do pacote. Leitores e segmentadores específicos são funções registradas por nome, e o YAML os referencia.
- **Perfil de banca:**
  - Identificação: id e marcas de detecção.
  - Formato padrão (certo/errado ou múltipla escolha), alternativas, rótulos e fator de penalidade.
  - Unidade de peso: por questão, por prova ou por disciplina.
  - Tipos de corte, cada um com:
    - escopo: total, prova, bloco ou disciplina;
    - unidade: pontos, acertos, percentual, nota de 0 a 10 ou nota padronizada;
    - se é calculável.

    "Não zerar disciplina" também é um tipo de corte.
  - Ordem típica de desempate e seções típicas do edital.
  - Leitor de gabarito, segmentação da prova (por item ou por cabeçalho de disciplina), blocos por chave de prova e leitor de resultado oficial.
  - Embutidos: `cebraspe`, `fgv`, `fcc`, `vunesp`, `ibfc`, `idecan`, `generic`, `selecon` e `quadrix`.
- **Perfil de OCR:** alternativas, itens por coluna (opcional), modo de marcação, limiares de vazio, cheio e marcada, e largura de normalização. Os valores atuais viram os padrões.
- **Perfil de edital:** seções a procurar, padrões extras de peso, corte e cronograma, e formato dos anexos. O `generic` é o pipeline de regex atual.
- **Precedência de valores:**
  - A ordem é edital, `concurso.yaml`, perfil e `generic`.
  - A fonte nova `perfil` entra no domínio de fonte da correção e no parquet. Os concursos existentes não mudam de valor.
- **Múltipla escolha:** aceita N alternativas, vindas do concurso ou do perfil. O valor serializado `cebraspe` da pontuação continua aceito.
- **Ramos por banca:** os ramos espalhados por cadastro, segmentação, leitores e agregação viram atributos ou chamadas do perfil. A penalidade é testada pelo fator, não pelo nome da banca.
- **Renomeação:** o registro de "candidatos à descoberta" passa a se chamar "pistas do edital", para liberar a palavra "candidato" ao domínio da pessoa. O campo serializado de versão no edital estruturado mantém o nome.

### Fallback de edital

- **Ordem por campo:**
  1. regex do perfil de banca;
  2. LLM, se configurado, online e permitido;
  3. heurística genérica (as regras da fase 3);
  4. modo mínimo, só com o conteúdo programático;
  5. `edital_a_confirmar.yaml`.

  Cada campo grava a camada que o preencheu.
- **Confiança agregada do edital:** é gravada no edital estruturado e define o selo do relatório (alta, média, baixa ou mínima).
- **`edital_a_confirmar.yaml`:**
  - É gerado só quando faltam campos.
  - Nunca é sobrescrito depois que o usuário o edita, só ganha campos novos.
  - O que o usuário preenche vira fonte `config`.
- **Corte não calculável:** escore padronizado e quantidade de classificados são registrados com aviso e ficam fora do "atingido".

### Fallback de folha

- **Ordem:**
  1. perfil de OCR da banca ou do candidato;
  2. detecção automática da grade (contornos, retificação e agrupamento em linhas e colunas);
  3. perfil calibrado do projeto;
  4. CSV de revisão;
  5. CSV manual.
- **Confiança por questão:** é a diferença entre os dois maiores preenchimentos. Abaixo do limiar, a leitura sai com `revisar=true`.
- **Calibração:**
  - Detecta a grade numa folha de amostra e a compara com as 5 respostas digitadas.
  - Ajusta o limiar de marcação, confirma o número de alternativas e grava um perfil de OCR do projeto.
- **`--reuse-csv`:**
  - Copia o CSV corrigido para a subpasta do candidato como respostas revisadas, que vencem a folha.
  - Se o hash da folha mudar depois, o app avisa.

### LLM

- **Clientes:** um cliente HTTP no formato compatível com OpenAI e um adaptador Anthropic, com timeout e sem retry agressivo.
- **O que é enviado:** só texto do edital e dos anexos, em trechos por seção.
- **Contrato da resposta:**
  - JSON com valor e `trecho_origem` por campo.
  - O trecho precisa existir literalmente no texto enviado, depois de normalizar espaços e acentos. Sem isso, o valor é descartado.
  - A confiança fica abaixo da do perfil e acima da da heurística.
- **Consentimento:** uma vez por instalação, gravado na configuração global.
- **Chave:** variável de ambiente, depois keyring, depois `.env` com permissão 600 e aviso.
- **Desligamento:** `--offline` e `--no-llm` desligam a camada.

### Relatório

- **Formato:** HTML estático por candidato, que reaproveita o markdown e os PNGs das fases 1 a 3.
- **Conteúdo:**
  - índice de concursos com o selo do edital;
  - o que o app decidiu sozinho e por quê;
  - avisos;
  - origem e data da geração.
- **Abertura:** no navegador padrão (no WSL, no do Windows), na primeira execução ou quando algo foi reprocessado.

### Wizard e doctor

- **Wizard:**
  - Seis perguntas: nome, pasta de provas, pasta de análises, calibração, LLM e se roda o `doctor`.
  - Cada uma tem flag e variável de ambiente.
  - Só pergunta o que falta e confirma antes de gravar.
- **Doctor:**
  - Verifica uv, versão do Python, Tesseract e o idioma `por`, poppler (só informativo), escrita nas pastas, espaço em disco e a chave do LLM (validada só fora do `--offline`).
  - Mostra ✓, ! ou ✗, com o comando de correção por sistema (apt, brew, winget).
  - Sai com código diferente de zero se houver algum ✗.

## Testing Decisions

### O que é um bom teste

Um bom teste valida o comportamento observável: arquivos gerados, valores, avisos, mensagens, código de saída e `mtime`. Nunca detalhes internos.

- **Fixtures:** pequenas e determinísticas.
- **Valor esperado:** vem de cálculo manual ou do edital, nunca recalculado do jeito que o código calcula.
- **Dados reais:** só como trechos curtos de editais públicos.

### Ponto de teste 1: o comando ponta a ponta

Estende os testes de CLI atuais. A CLI nova roda com:

- `CONCURSO_HOME` e o projeto numa pasta temporária;
- stdin roteirizado e TTY simulado;
- PATH controlado para simular a falta do Tesseract;
- URL do LLM apontando para um servidor HTTP local de teste.

Casos:

- **Onboarding:** com todos os padrões, grava as três configurações e gera o `index.html`. Sem TTY ou com `CI=true`, nada é perguntado.
- **Idempotência:** a segunda execução não altera nenhum `mtime` em `analises/` e registra "sem mudanças". O mesmo vale para `--dry-run` rodado duas vezes.
- **`--dry-run` na primeira execução:** não grava nada e lista a migração.
- **Reprocessamento seletivo:** mudar um arquivo de um candidato reprocessa só aquele par. Mudar um arquivo comum reprocessa todos os candidatos do concurso.
- **Multi-candidato:**
  - `--candidate alice` e `--candidate bob` geram árvores e consolidados separados e corretos.
  - `add <arquivo> --candidate bob` cria o candidato.
- **Migração:**
  - Uma árvore legada sintética migra preservando o hash de cada saída e gerando o backup, e não migra de novo.
  - Uma pasta legada copiada depois é migrada.
- **Fallback de edital:**
  - Um edital em imagem de banca fictícia, sem Tesseract, cai no modo mínimo, avisa e gera o `edital_a_confirmar.yaml`.
  - Preencher o arquivo e rodar de novo aplica os valores com fonte `config`.
- **Fallback de folha:**
  - Uma folha fora do padrão gera `revisar=true`.
  - O `--reuse-csv` aplica a revisão e vence a folha.
  - Um CSV manual `questao,alternativa` roda o pipeline inteiro.
- **Mensagens de erro:** sem `Traceback`, com até duas linhas e uma `dica:`. Erros cobertos: sem pasta de provas, edital em imagem sem Tesseract, chave do LLM ausente, concurso sem respostas e YAML inválido.
- **Doctor:** com o Tesseract ausente, mostra ✗ e o comando, e sai com código diferente de zero.
- **LLM:**
  - Só recebe texto do edital; o servidor de teste inspeciona o corpo da requisição.
  - Uma resposta sem trecho conferível é descartada.
  - Com `--offline`, nenhuma requisição chega ao servidor.
- **CLI antigo:** o alias `concursos analisar` funciona e avisa.
- **Tempo:** o onboarding cronometrado termina em até 90 segundos no concurso sintético.

### Ponto de teste 2: do texto do edital às regras

É o ponto que já existe, com funções puras. Usa trechos curtos dos editais da pesquisa: PF 2025, TSE 2024, PC-PE 2023, STN 2024, CVM 2024, TRT-6 2024, MP-PI 2025, TJSP 2023, TRF-5 2024, Fortaleza 2023 e EMPARN 2025.

Casos:

- Cada perfil extrai formato, alternativas, penalidade, peso e cortes do seu trecho.
- O edital vence o perfil, e o perfil preenche o que falta, com fonte `perfil`.
- Escore padronizado e corte por classificação saem como não calculáveis.
- "Não zerar disciplina" vira corte.
- Cada camada de fallback é registrada.
- O banco de casos da fase 3 continua verde.

### Ponto de teste 3: da imagem da folha às marcações

É o ponto que já existe, com as folhas sintéticas. Casos:

- grade de 4 alternativas;
- detecção automática sem template, com rotação leve;
- confiança baixa quando duas bolhas têm preenchimento parecido;
- calibração com as 5 respostas, que ajusta o limiar e reprova uma grade incoerente.

### Outras verificações

- **Sem dado pessoal:** um teste procura no pacote os nomes, slugs e inscrições dos dados locais e dos fixtures, padrões de CPF e caminhos absolutos de usuário.
- **Paridade com dados reais:** é local, fora do pytest e do CI.
  - O `scripts/paridade.py` grava o hash de cada saída dos 9 concursos analisados, antes de cada ticket que toca código das fases 1 a 3, e compara depois.
  - `correcao.json`, os CSVs e o parquet precisam ficar idênticos.
  - Base: as 116 saídas atuais, que se mostraram determinísticas em duas execuções seguidas com `--forcar`.
- **Verificação manual ao final:**
  - Linux/WSL, container limpo (só com Docker) e Windows nativo pelo `powershell.exe`, com `uv` instalado no Windows.
  - O workflow de CI (Ubuntu, macOS e Windows, Python 3.11 e 3.12) fica escrito. Sem remoto, o macOS fica não verificado.

### Prior art e forma de desenvolvimento

- **Prior art:**
  - os testes de CLI sobre pastas temporárias (incremental, cadastro, análise);
  - os testes puros de extração da correção e das regras do edital a partir de trechos;
  - as folhas sintéticas;
  - a factory de consolidado sintético.
- **Desenvolvimento:** TDD em fatias verticais, um ticket por vez, na ordem dos bloqueios.
- **Pronto:** suíte verde, ruff limpo, paridade sem diferença e notebooks executando do zero.

## Out of Scope

- Interface web, app mobile, servidor multiusuário com autenticação e sincronização em nuvem.
- OCR treinado próprio e idiomas além do português.
- Marketplace público de plugins: o entry point existe, mas não há catálogo.
- Telemetria, mesmo opt-in, e atualização automática silenciosa.
- LLM para classificar tópicos, ler a folha ou ler a prova.
- Calcular corte por escore padronizado ou por quantidade de classificados, e estimar colocação.
- Mover os módulos das fases 1 a 3 para um subpacote novo.
- Depender do OMRChecker: só a ideia do formato de template é aproveitada.
- Pacotes próprios de Homebrew ou Chocolatey.
- Publicar no PyPI e rodar o CI enquanto o repositório não tiver remoto.
- Cadastrar `creci`, `dataprev_2024` e `senappen`.

## Further Notes

- **Bancas:**
  - Só o Cebraspe penaliza, e só no certo/errado.
  - IBFC e Idecan variam entre 4 e 5 alternativas.
  - O peso aparece como "peso", "pontos por questão", "peso por questão" ou valor dobrado do item.
  - O corte aparece em cinco unidades, quase sempre combinadas.
  - O desempate começa quase sempre pela idade de 60 anos ou mais (Estatuto da Pessoa Idosa).
- **UX:**
  - Padrões copiados: `--yes`, perguntar só com TTY, padrão entre colchetes, resumo antes de gravar, `doctor` com o comando de correção, `dica:` separada da causa e `NO_COLOR`.
  - O keyring não tem backend no WSL sem desktop. Daí a ordem: variável de ambiente, keyring, `.env`.
- **Riscos:**
  - Os pisos atuais de numpy e pandas foram resolvidos só para 3.12. Se algum excluir 3.11, o piso baixa.
  - A presença do `uv` no Windows não foi confirmada.
  - A detecção automática de folha não tem amostra real fora dos três templates atuais. A primeira folha real que falhar entra como fixture mínima antes da correção.
- **Selecon e Quadrix:** ficam como perfis que reproduzem o comportamento atual, marcados como "sem edital público verificado".
