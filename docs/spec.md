# Spec: Análise de Desempenho em Concursos

Status: `ready-for-agent`

## Problem Statement

Faço muitos concursos públicos (Cebraspe, FGV, SELECON, Quadrix) e não sei com precisão em quais disciplinas e tópicos do edital eu perco pontos. Os materiais de cada concurso ficam espalhados em PDFs com nomes arbitrários: edital, cadernos de prova (às vezes em vários tipos), gabaritos preliminares e definitivos com dezenas de cargos misturados, a imagem da minha folha de resposta e, às vezes, o resultado oficial. Corrigir manualmente, cruzar cada questão com o conteúdo programático e comparar concursos diferentes é lento e sujeito a erro. Além disso, cada banca tem layout de folha, formato de gabarito e regra de pontuação próprios. Ainda há a pontuação Cebraspe, em que um erro anula um acerto. E o gabarito muda entre a versão preliminar e a definitiva.

## Solution

Uma ferramenta local de linha de comando com fluxo em três passos:

1. **Coletar:** eu crio uma pasta por concurso e copio os arquivos que tiver: edital, provas, gabaritos, e a folha de resposta ou um arquivo de texto com minhas respostas. O resultado oficial é opcional. Os nomes dos arquivos são livres.
2. **Cadastrar:** um assistente lê o conteúdo de cada arquivo, identifica o papel, a banca, as faixas de itens e os cargos/tipos disponíveis no gabarito. Ele só pergunta o que não consegue inferir e grava uma configuração explícita dentro da pasta do concurso.
3. **Analisar:** um comando processa apenas o que é novo ou mudou e gera, por concurso, as respostas extraídas (com confiança da leitura), o desempenho por disciplina e por tópico, gráficos e um relatório legível. Também gera um consolidado que responde: "em quais tópicos meu desempenho é consistentemente baixo entre concursos?".

Quando o gabarito definitivo sai, basta colocá-lo na pasta. A análise troca o preliminar pelo definitivo, guarda a versão anterior e mostra o que mudou.

## User Stories

### Coleta e cadastro de concursos
1. Como candidato, quero criar uma pasta por concurso e soltar os arquivos com qualquer nome, para não precisar renomear dezenas de PDFs baixados.
2. Como candidato, quero rodar um comando de cadastro apontando para a pasta, para que a ferramenta descubra sozinha o que é cada arquivo.
3. Como candidato, quero que o cadastro identifique edital, caderno de prova, gabarito, folha de resposta, arquivo de respostas e resultado oficial pelo conteúdo, para que nomes como hashes ou datas não atrapalhem.
4. Como candidato, quero que a banca seja detectada automaticamente, para não ter que informá-la.
5. Como candidato, quero que as faixas de itens de cada prova (por exemplo, conhecimentos gerais 1–90 e específicos 91–180) sejam inferidas do gabarito, para não contá-las à mão.
6. Como candidato, quero escolher meu cargo e meu tipo de caderno numa lista extraída do próprio gabarito, para não errar a digitação de nomes longos.
7. Como candidato, quero que o cadastro pergunte quando houver ambiguidade (dois gabaritos, arquivos duplicados, arquivo não reconhecido) em vez de decidir sozinho, para confiar no resultado.
8. Como candidato, quero que arquivos duplicados (mesmo conteúdo) sejam detectados por hash, para que cópias como "arquivo (1).pdf" não gerem confusão.
9. Como candidato, quero que arquivos irrelevantes (cadernos de outros cargos ou tipos, arquivos compactados, metadados do Windows) fiquem numa lista de ignorados, para que a pasta possa conter material extra.
10. Como candidato, quero ver um resumo do que foi detectado e confirmar antes de gravar, para corrigir erros de detecção.
11. Como candidato, quero que a configuração fique dentro da pasta do concurso, para que adicionar um concurso seja só adicionar uma pasta.
12. Como candidato, quero rodar o cadastro de novo numa pasta já configurada e ver o que mudou antes de sobrescrever, para não perder ajustes.
13. Como candidato, quero um modo não interativo que aceite as sugestões e falhe se algo for ambíguo, para automatizar cadastros simples.
14. Como candidato, quero um assistente guiado (script interativo) que me leve do zero até a análise, para não decorar comandos.

### Respostas
15. Como candidato, quero que minha folha de resposta (PDF ou imagem) seja lida automaticamente, para não digitar dezenas de respostas.
16. Como candidato, quero, como alternativa, informar minhas respostas num arquivo de texto com uma questão por linha, para os concursos em que não tenho a folha.
17. Como candidato, quero que o arquivo de texto aceite formatos variados ("1 A", "01: A", "1-C", minúsculas), para não me preocupar com a formatação exata.
18. Como candidato, quero marcar questão em branco com "-", com linha sem resposta ou simplesmente omitindo a questão, para registrar o que deixei em branco.
19. Como candidato, quero usar linhas de comentário no arquivo de texto, para anotar observações.
20. Como candidato, quero erros claros com número da linha quando o arquivo de texto tiver resposta inválida, número duplicado ou fora da faixa, para corrigir rápido.
21. Como candidato, quero que cada resposta lida da folha venha com um nível de confiança, para saber o quanto confiar na leitura.
22. Como candidato, quero que respostas com confiança abaixo de um limiar sejam marcadas para revisão, para conferir só o que importa.
23. Como candidato, quero que marcações duplas, em branco e ambíguas apareçam explicitamente na lista de respostas, para que nenhuma questão suma.
24. Como candidato, quero rastrear cada leitura até arquivo, página e questão, e ter uma imagem de depuração com as bolhas detectadas sobrepostas, para investigar erros de leitura.
25. Como candidato, quero que folhas Cebraspe com grades diferentes (7×15, 8×15, 9×20, 10×20, em posições variadas) sejam lidas sem que eu configure coordenadas, para que novos concursos funcionem de imediato.
26. Como candidato, quero que folhas FGV (70 questões em blocos e o cartão de 90 questões do CPNU) sejam lidas, para cobrir as bancas que já fiz.

### Gabaritos
27. Como candidato, quero que gabaritos Cebraspe (grade Item/Gabarito), FGV (seções por cargo e tipo) e de lista "01: A" (SELECON, Quadrix) sejam interpretados, para não transcrever gabaritos.
28. Como candidato, quero que questões anuladas sejam reconhecidas ("X" ou "*"), para que sejam tratadas corretamente.
29. Como candidato, quero que o pipeline confira se o número de questões do gabarito bate com a faixa configurada, para detectar erros de extração.
30. Como candidato, quero poder fornecer um gabarito manual em texto/CSV quando a extração do PDF falhar, para não ficar bloqueado.
31. Como candidato, quero analisar com o gabarito preliminar enquanto o definitivo não sai, para ter uma visão antecipada.
32. Como candidato, quero ver claramente no relatório que a análise usa gabarito preliminar (provisório), para não tomar conclusões definitivas.
33. Como candidato, quero apenas colocar o gabarito definitivo na pasta e rodar a análise, para que a troca seja automática.
34. Como candidato, quero que a troca só aconteça quando o novo gabarito tiver a mesma banca, cargo, tipo e faixa de itens, para evitar trocas erradas.
35. Como candidato, quero que, se o novo arquivo não casar ou houver mais de um candidato, o concurso fique marcado como desatualizado com instrução para recadastrar, para não ter troca silenciosa.
36. Como candidato, quero que sobrescrever o gabarito com o mesmo nome também dispare a troca quando o status mudar de preliminar para definitivo, para não depender de nome de arquivo.
37. Como candidato, quero que a análise anterior (com o preliminar) seja guardada num histórico, para comparar depois.
38. Como candidato, quero uma lista das questões alteradas e anuladas entre preliminar e definitivo, com minha resposta e se meu acerto mudou, para entender o impacto.
39. Como candidato, quero que o relatório mostre o efeito da troca nos acertos e na nota líquida, para saber se ganhei ou perdi pontos.
40. Como candidato, quero que a troca fique registrada no histórico da configuração do concurso (data, arquivo anterior, arquivo novo), para ter auditoria.
41. Como candidato, quero que, quando a pasta já tiver preliminar e definitivo, o definitivo seja usado e o preliminar ignorado, para não precisar apagar arquivos.

### Edital, disciplinas e tópicos
42. Como candidato, quero que o conteúdo programático do edital seja extraído como conhecimento, disciplina e tópicos (com peso, se houver), para analisar por tópico.
43. Como candidato, quero que apenas o conteúdo do meu cargo seja considerado em editais com vários cargos, para não misturar matérias.
44. Como candidato, quero que o conteúdo possa vir de um anexo separado do edital (caso do CPNU), para cobrir editais fragmentados.
45. Como candidato, quero fornecer um edital estruturado manualmente quando a extração falhar, para não ficar bloqueado.
46. Como candidato, quero que, nas provas FGV, a disciplina de cada questão venha dos cabeçalhos do caderno, para ter atribuição exata.
47. Como candidato, quero que, nas provas Cebraspe (sem cabeçalhos de disciplina), disciplina e tópico sejam sugeridos por similaridade entre o bloco de comando e os tópicos do edital, para ter uma primeira classificação automática.
48. Como candidato, quero revisar e corrigir as sugestões de disciplina e tópico num arquivo de revisão que tem prioridade sobre a sugestão, para garantir a qualidade.
49. Como candidato, quero ver o score de similaridade de cada sugestão, para priorizar a revisão das mais fracas.
50. Como candidato, quero que alterar a revisão dispare o reprocessamento do concurso, para que os relatórios reflitam minhas correções.

### Correção e agregação
51. Como candidato, quero que provas de múltipla escolha sejam corrigidas com pontuação simples, para ter o número de acertos.
52. Como candidato, quero que provas Certo/Errado sejam corrigidas pela regra Cebraspe (erro anula acerto, branco vale zero), para ter a nota líquida real.
53. Como candidato, quero que questões anuladas contem como acerto, com sinalização, e fiquem fora do percentual de mérito, para não distorcer minha análise.
54. Como candidato, quero desempenho agregado por disciplina e por tópico, com total, acertos, erros, brancos, anuladas, percentual e nota líquida, para identificar fraquezas.
55. Como candidato, quero que os totais sempre fechem (acertos + erros + brancos = total, total = faixa de itens), para confiar nos números.
56. Como candidato, quero que meus acertos calculados sejam comparados com o resultado oficial quando eu fornecê-lo, para validar a leitura da folha e o gabarito.
57. Como candidato, quero um alerta destacado no relatório e no log quando houver divergência com o resultado oficial, para investigar.

### Relatórios e consolidado
58. Como candidato, quero um relatório por concurso com resumo, gráficos por disciplina e tópico e lista de questões para revisar, para entender meu desempenho rapidamente.
59. Como candidato, quero um consolidado com o desempenho de todos os concursos, para ver a evolução.
60. Como candidato, quero que o consolidado responda em quais tópicos meu desempenho é consistentemente baixo (abaixo de um limiar em pelo menos dois concursos), para focar meus estudos.
61. Como candidato, quero que o consolidado liste os concursos incompletos e o motivo, para saber o que falta fornecer.
62. Como candidato, quero que o consolidado indique quais concursos ainda usam gabarito preliminar, para ponderar as conclusões.

### Execução e operação
63. Como candidato, quero que a análise processe apenas concursos novos ou alterados, para que rodadas futuras sejam rápidas.
64. Como candidato, quero um modo forçado que reprocesse tudo, para quando eu mudar regras ou limiares.
65. Como candidato, quero analisar um único concurso, para iterar rápido na calibração.
66. Como candidato, quero um comando de status que mostre cada concurso como completo, incompleto ou desatualizado, o status do gabarito e o que falta, para ter visão geral.
67. Como candidato, quero que concursos incompletos não quebrem a análise dos demais, para não ficar refém de um arquivo faltando.
68. Como candidato, quero mensagens de erro que apontem o arquivo e o motivo exatos, para corrigir sem depurar código.
69. Como candidato, quero que o OCR de texto (Tesseract) só seja exigido quando um PDF não tiver camada de texto, e com erro claro se não estiver instalado, para não instalar dependências desnecessárias.
70. Como candidato, quero que meus dados pessoais (folhas com CPF, resultados com dados de terceiros) e as saídas nunca sejam versionados, para proteger minha privacidade.
71. Como candidato, quero limiares (confiança da leitura, tópico baixo) configuráveis globalmente, para ajustar a sensibilidade sem mexer em código.
72. Como desenvolvedor, quero um README que explique como adicionar um novo concurso, para retomar o projeto meses depois.
73. Como desenvolvedor, quero hooks de pre-commit com lint e testes, para manter a qualidade.

## Implementation Decisions

### Fluxo e interface
- A aplicação é uma CLI Python com três comandos: **adicionar** (cadastro assistido de uma pasta de concurso), **analisar** (processamento incremental, com opções para um concurso específico e para forçar o reprocessamento) e **status**. Um script bash interativo guia o usuário e chama esses comandos.
- Logs usam `logging`, nunca prints de depuração.
- Configuração em dois níveis: uma configuração global só com defaults (limiar de confiança da leitura = 0.75; limiar de tópico baixo = 0.6) e um arquivo de configuração por pasta de concurso, gerado pelo cadastro e editável à mão.

### Configuração do concurso (schema)
- Campos: nome, banca (`cebraspe | fgv | selecon | quadrix`), formato (`multipla_escolha | certo_errado`), pontuação (`simples | cebraspe`), cargo e tipo (obrigatórios quando o gabarito tem múltiplas seções), edital (arquivo principal e anexos opcionais), mapa de provas (chave da prova → arquivo do caderno, gabarito com arquivo e status `preliminar | definitivo`, faixa de itens `[inicio, fim]`), respostas (folha + template + parâmetros de grade, ou arquivo de texto), resultado oficial opcional (arquivo + identificador do candidato), lista `ignorar` e lista `historico` de eventos (data, tipo, prova, arquivo anterior, arquivo novo).
- Para cada concurso, o status é derivado: `completo`, `incompleto` (com motivo: falta edital, respostas, gabarito ou prova) ou `desatualizado` (arquivo novo não cadastrado ou configuração inválida).

### Módulos
- **Configuração do concurso:** carrega, valida o schema e a existência dos arquivos, e calcula o status. Arquivo ausente gera erro específico com o caminho completo.
- **Extração de texto:** texto por página via pdfplumber, imagens embutidas via pypdfium2, e fallback para Tesseract por página sem camada de texto (erro claro se o Tesseract não estiver instalado).
- **Detecção:** a partir do texto e de metadados (número de páginas, presença de imagem), classifica o papel do arquivo, a banca e o status do gabarito. Os marcadores vêm dos 12 concursos reais: "EDITAL Nº", "GABARITO", "PRELIMINAR"/"DEFINITIVO", "FOLHA DE RESPOSTAS"/"CARTÃO-RESPOSTA", PDF de uma página só com imagem, "RESULTADO", "julgue os itens"/"caderno".
- **Assistente de cadastro:** orquestra a detecção, as perguntas e a confirmação. A entrada e a saída são injetáveis para teste.
- **Gabarito:** três parsers selecionados pela banca:
  - grade Cebraspe: linhas Item/Gabarito, "X" = anulada, ignora os zeros de preenchimento;
  - seções FGV: "cargo - tipo - turno" ou "cargo - TIPO n", "*" = anulada;
  - lista "NN: R": seções por código/cargo e "PROVA A/B", "X" ou "*" = anulada.

  Expõe também a listagem de seções (para o assistente) e a validação de contagem. O CSV/TXT manual é o formato canônico de fallback.
- **Respostas:** parser do arquivo de texto (formatos flexíveis, brancos, comentários, validação com número da linha) e adaptador para a leitura da folha. Ambos produzem a mesma estrutura de resposta marcada (questão, alternativa, estado `marcada | branco | multipla`, confiança, origem `folha | manual`, arquivo, página).
- **Leitura da folha:** extrai a imagem embutida, binariza, corrige inclinação e alinha pelos marcadores de canto. Localiza a grade pelo agrupamento das bolhas em colunas e linhas, a partir de `itens_por_coluna` e `total_itens`. Mede a taxa de preenchimento de cada bolha. A confiança é a margem entre a bolha mais preenchida e a segunda. Templates: Cebraspe C/E (parametrizado), FGV 70 questões em blocos e FGV cartão de 90 questões. Gera uma imagem de depuração.
- **Edital:** localiza o conteúdo programático, filtra pelo cargo e produz a estrutura conhecimento → disciplina → tópicos (peso opcional), persistida como JSON por concurso. Edital manual estruturado como fallback.
- **Prova:** segmenta o caderno em questões. Na Cebraspe, agrupa os itens por bloco de comando; na FGV e SELECON, extrai os cabeçalhos de disciplina e suas faixas.
- **Tópicos:** sugestão por TF-IDF (scikit-learn) do bloco ou enunciado contra os tópicos do edital, com score. O arquivo de revisão manual tem prioridade. Sem LLM.
- **Correção:** regras `simples` e `cebraspe`, tratamento de anuladas (acerto sinalizado, fora do percentual de mérito) e de brancos.
- **Agregação:** por prova, disciplina, tópico e concurso, com verificação de fechamento de totais.
- **Validação oficial:** extrai do resultado oficial os acertos ou notas do candidato e compara com o calculado. Divergência vira alerta.
- **Manifesto:** hash dos arquivos de entrada, da configuração e da revisão. Decide o que reprocessar.
- **Atualização de gabarito:** antes de processar, varre arquivos não cadastrados. Um gabarito definitivo que casa com a seção configurada (mesma banca, cargo/tipo e faixa de itens) substitui o preliminar: a configuração é atualizada, o preliminar vai para `ignorar`, o evento entra no histórico, as saídas atuais são copiadas para o histórico e o diff é gerado. Qualquer outro caso marca o concurso como `desatualizado`.
- **Relatórios:** gráficos (matplotlib), relatório markdown por concurso (selo de gabarito provisório, seção "Preliminar → Definitivo", questões para revisar, alertas de validação oficial) e consolidado comparativo.

### Contratos de saída (por concurso e consolidado)
- Respostas extraídas: concurso, prova, questão, alternativa marcada, estado, confiança da leitura, revisar, origem, arquivo, página. Inclui todas as questões.
- Desempenho por disciplina e por tópico: concurso, prova, disciplina, tópico, total, acertos, erros, percentual, mais brancos, anuladas e nota líquida.
- Diff de gabarito: prova, questão, gabarito preliminar, gabarito definitivo, mudança (`alterada | anulada`), resposta do candidato, acerto antes, acerto depois.
- Artefatos intermediários: edital estruturado em JSON, tabela de questões (número, disciplina, tópico sugerido e confirmado, score, gabarito, anulada) e arquivo de revisão.
- Consolidado: desempenho geral e comparativo em markdown, com tópicos consistentemente baixos, status de cada concurso, status do gabarito e divergências com o resultado oficial.

### Projeto
- Python 3.12, gerenciado com uv e pyproject com entrypoint da CLI. Dependências: pandas, pdfplumber, pypdfium2, pytesseract, opencv-python-headless, pillow, scikit-learn, pyyaml, matplotlib. Dev: pytest, ruff, pre-commit.
- Repositório git com pre-commit (ruff e pytest). As pastas de provas e de análises ficam fora do versionamento por conterem dados pessoais.
- A documentação do modelo de domínio (Concurso, Prova, Questão, Disciplina/Tópico, RespostaMarcada, Resultado, Gabarito com status, EventoHistórico) fica num documento próprio, junto do README.

## Testing Decisions

- **O que é um bom teste:** valida comportamento externo observável (arquivos gerados, conteúdo dos CSVs, mensagens de erro e status), nunca detalhes internos. Fixtures pequenas e determinísticas. Dados reais só como trechos de texto anonimizados.
- **Seam principal: CLI ponta a ponta.** Os testes rodam `adicionar` (com entradas simuladas), `analisar` e `status` sobre uma pasta temporária com concursos sintéticos, usando gabarito em texto e arquivo de respostas. Verificam:
  - schema e fechamento de totais dos CSVs;
  - regras simples e Cebraspe, anuladas e brancos;
  - execução incremental: nada reprocessa sem mudança, e a alteração de revisão reprocessa;
  - troca de gabarito: preliminar recebe definitivo, com snapshot, diff, histórico e reprocessamento; casos não casados resultam em `desatualizado`;
  - status `incompleto` sem quebrar os demais;
  - consolidado com tópicos consistentemente baixos;
  - divergência com o resultado oficial gera alerta.
- **Seam 2: texto extraído para estrutura.** Parsers de gabarito (um trecho real de cada formato), detecção de papel, banca e status (cabeçalhos reais de cada tipo de arquivo), edital (trecho de conteúdo programático com múltiplos cargos), segmentação de prova (bloco de comando Cebraspe e cabeçalho FGV) e parser do arquivo de respostas (casos de borda).
- **Seam 3: imagem da folha para marcações.** Imagens sintéticas geradas no próprio teste com OpenCV: bolha cheia, vazia, dupla, parcial, grade rotacionada e grades Cebraspe de dimensões diferentes. Verificam alternativa, estado, confiança e flag de revisão. A calibração com folhas reais é verificação manual, conferida pelo resultado oficial quando existir (CPNU), e não entra na suíte automatizada.
- **Prior art:** projeto greenfield, sem testes existentes. Esta suíte estabelece o padrão: pytest, fixtures em diretório próprio e geração de imagens em fixture compartilhada.
- **Desenvolvimento:** TDD para os parsers, a leitura de bolhas, a correção e a troca de gabarito. O critério de pronto é a suíte verde, os CSVs no schema e os totais fechando.

## Out of Scope

- Classificação de tópicos por LLM ou APIs externas.
- Provas discursivas, redação e títulos; o escopo é só a prova objetiva.
- Interface web ou gráfica; o escopo é só CLI e relatórios em markdown e PNG.
- Download automático de editais, provas e gabaritos dos sites das bancas.
- Suporte a bancas além de Cebraspe, FGV, SELECON e Quadrix, que precisa de novo parser ou template.
- Tipos de caderno com reordenação de questões mapeados automaticamente entre si; o usuário deve fornecer o caderno do mesmo tipo da folha.
- Gabarito preliminar para definitivo em sentido inverso, ou múltiplas versões além dessas duas.
- Publicação ou compartilhamento das análises.

## Further Notes

- **Estado atual dos dados (12 concursos):**
  - Completos: `cd_25`, `funpresp_jud`, `infrasa`, `tcu_25`, `pf_perito`, `telebras` (Cebraspe), e `agsus`, `cprm` (Tipo 1), `cpnu` (Bloco 3, Tipo 2) (FGV).
  - Faltando respostas: `dataprev_2024` (também falta informar o tipo), `senappen` (falta informar Prova A/B) e `creci` (cargo 101 – Analista de TI).
- **Resultados oficiais disponíveis para validação:** CPNU (acertos por eixo), Dataprev, SENAPPEN e CRECI. Antes de usar a nota final da CRECI, conferir no edital se ela inclui a prova discursiva.
- O tipo de caderno da CPNU (Tipo 2) não aparece no espelho. A confirmação vem da validação contra o resultado oficial.
- Tesseract não está instalado no ambiente. Instalação opcional: `sudo apt install tesseract-ocr tesseract-ocr-por`.
- Não há issue tracker configurado. Este spec fica no repositório. Para publicar em um tracker, configure-o antes.
- O plano de execução por fases complementa este spec. Ordem: esqueleto, gabaritos e respostas, cadastro, folha, edital/tópicos, correção/incremental/troca, relatórios.
