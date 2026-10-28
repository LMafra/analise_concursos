# Bugs encontrados na revisão de código

Revisão feita sobre as mudanças desde o commit inicial `9c59679`. Os três primeiros bugs foram corrigidos em `a611ef1` e o quarto em `251190e`. As duas lacunas em relação à spec, registradas no fim do documento, foram fechadas no commit seguinte.

Ambiente comum a todos os relatos:

- **Dispositivo**: Desktop
- **SO**: Linux (WSL2, kernel 6.18)
- **Versão**: Python 3.12.3, pacote `concursos` (CLI `concurso-analise`), `VERSAO_ANALISE = 9`
- **Usuário**: local, sem autenticação

| Bug | Severidade | Situação |
| --- | --- | --- |
| [Consolidado quebra quando um concurso analisado perde o `concurso.yaml`](#bug-1) | Alta | Corrigido em `a611ef1` |
| [`banca` e status do gabarito aceitam qualquer valor](#bug-2) | Média | Corrigido em `a611ef1` |
| [Diff preliminar → definitivo se perde ou fica defasado](#bug-3) | Alta | Corrigido em `a611ef1` |
| [Nomes de tópicos cortados em 150 caracteres](#bug-4) | Baixa | Corrigido em `251190e` |

---

<a id="bug-1"></a>

# Bug Report: `concursos analisar` quebra no consolidado quando um concurso analisado perde o `concurso.yaml`

## Description

Se a pasta de um concurso já analisado fica sem `concurso.yaml` (apagado, renomeado ou com a pasta recriada), a etapa de consolidação tentava ler as saídas desse concurso como se ele estivesse completo e acessava a configuração ausente. A análise de todos os concursos terminava em erro e `analises/consolidado/` não era atualizado.

## Severity

Alta — impede a geração do consolidado para todos os concursos por causa de um único concurso incompleto.

## Steps to Reproduce

1. Cadastrar e analisar dois concursos `a` e `b` (`concursos adicionar provas/a`, `concursos adicionar provas/b`, `concursos analisar`).
2. Apagar `provas/b/concurso.yaml`.
3. Rodar `concursos analisar`.

## Expected Behavior

O concurso `b` aparece como incompleto em `comparativo_concursos.md` ("Concursos incompletos ou desatualizados") e fica fora de `desempenho_geral.csv`; o consolidado é gerado com os demais.

## Actual Behavior

A consolidação falhava ao acessar a configuração de `b`, que é `None` para pastas sem cadastro.

## Possible Fix

Aplicado: o filtro `analisados` em `src/concursos/consolidado.py` passou a exigir `s.situacao is Situacao.COMPLETO`. Coberto pelo teste novo em `tests/test_cli_consolidado.py`.

---

<a id="bug-2"></a>

# Bug Report: `concurso.yaml` aceita `banca` e status do gabarito inválidos sem aviso

## Description

`banca` e `provas.<chave>.gabarito.status` eram lidos como texto livre. Um erro de digitação (`cespe`, `Preliminar`) passava pela validação. A leitura do gabarito, a segmentação do caderno e a correspondência de cargo na troca de gabarito dependem de `banca == 'cebraspe'`; o selo de gabarito preliminar e a troca automática dependem de `status == 'preliminar'`.

## Severity

Média — gera erro enganoso ou relatório errado, mas só com edição manual do yaml.

## Steps to Reproduce

1. Cadastrar um concurso Cebraspe com `concursos adicionar provas/<concurso>`.
2. Editar `provas/<concurso>/concurso.yaml` e trocar `banca: cebraspe` por `banca: cespe`.
3. Rodar `concursos status`.

## Expected Behavior

O concurso aparece como incompleto, com uma mensagem indicando o valor inválido e as opções aceitas.

## Actual Behavior

O concurso aparecia como completo. Na análise:

- com gabarito em PDF, falhava com `leitura de gabarito em PDF da banca 'cespe' não suportada`, mensagem que não aponta o erro de digitação;
- com gabarito em txt, o caderno era segmentado como prova de múltipla escolha, e as sugestões de tópico saíam erradas;
- com `status: Preliminar`, o relatório não mostrava o selo de gabarito provisório e a troca para o definitivo nunca era detectada.

## Possible Fix

Aplicado: `BANCAS` e `STATUS_GABARITO` em `src/concursos/concurso_config.py`, validados por `_opcao(valor, opcoes, campo)`. `cadastro.py` passou a importar `BANCAS` daí. Coberto por testes novos em `tests/test_cli_status.py`.

---

<a id="bug-3"></a>

# Bug Report: diff preliminar → definitivo se perde se a análise falha após a troca e fica defasado quando as respostas mudam

## Description

Na troca de gabarito preliminar por definitivo, `trocar_gabaritos` lia o `questoes.csv` anterior e devolvia essa tabela para `analisar_concurso`, que gravava `diff_gabarito.csv` uma única vez. Havia dois problemas:

1. **Troca não atômica**: o snapshot em `historico/` e o `concurso.yaml` eram atualizados antes da análise. Se a análise falhasse logo depois, a próxima execução já não via troca pendente e o diff nunca era gerado.
2. **Diff defasado**: o diff gravado guardava o acerto "antes" calculado com as respostas daquele momento. Corrigir uma resposta depois mantinha os números antigos na seção "Preliminar → Definitivo" do relatório.

## Severity

Alta — a seção "Preliminar → Definitivo" do relatório some ou mostra acertos e nota errados, sem aviso.

## Steps to Reproduce

1. Cadastrar um concurso com gabarito preliminar e analisar (`concursos analisar`).
2. Adicionar o gabarito definitivo à pasta e rodar `concursos analisar` (a troca é feita e o diff é gerado).
3. Corrigir uma resposta de uma questão alterada no `respostas.txt` (por exemplo, `-` → `E`).
4. Rodar `concursos analisar --forcar`.

## Expected Behavior

O relatório mostra o impacto da troca com as respostas atuais (no teste: "Acertos: 5 → 6").

## Actual Behavior

O relatório continuava com os acertos calculados antes da correção da resposta. Se `diff_gabarito.csv` fosse apagado ou a análise do passo 2 falhasse, a seção não voltava mais.

## Possible Fix

Aplicado: `trocar_gabaritos` só guarda o snapshot e atualiza o yaml. A cada análise, `questoes_preliminares(destino)` lê o snapshot mais antigo de `historico/` (anterior à primeira troca), e `_diff_da_troca` em `pipeline.py` recalcula o diff com as respostas atuais, regravando `diff_gabarito.csv` (ou apagando-o quando não há snapshot). Coberto por `test_diff_e_recalculado_com_as_respostas_atuais_e_sobrevive_a_reanalise` em `tests/test_cli_gabarito_definitivo.py`.

---

<a id="bug-4"></a>

# Bug Report: nomes de tópicos do edital são cortados em 150 caracteres, inclusive no meio de palavras

## Description

`_topico` em `src/concursos/edital.py` grava `Topico(numero, nome[:150], descricao)`. Tópicos longos do edital aparecem truncados em `desempenho_por_topico.csv`, no `relatorio.md`, nos gráficos e no consolidado. Nos dados reais, 42 linhas de `desempenho_por_topico.csv` em 7 concursos estão truncadas (tcu_25: 25; cd_25: 6; agsus: 4; cprm: 3; funpresp_jud: 2; infrasa: 1; telebras: 1).

## Severity

Baixa — o texto completo continua em `descricao` e a classificação por TF-IDF não é afetada; o impacto é de leitura. Há um risco teórico de dois tópicos diferentes com os mesmos 150 primeiros caracteres serem somados no consolidado, que agrupa pelas palavras-chave do nome.

## Steps to Reproduce

1. Rodar `concursos analisar`.
2. Abrir `analises/infrasa/desempenho_por_topico.csv`.
3. Procurar o tópico sobre ameaças e vulnerabilidades em aplicações.

## Expected Behavior

O nome do tópico aparece completo, ou é abreviado num limite de palavra com indicação de corte ("…").

## Actual Behavior

```
Ameaças e vulnerabilidades em aplicações: injection (SQL, LDAP), cross-site scripting (XSS), quebra de autenticação e gerenciamento de sessão, referên
```

## Additional Notes

O corte existe para manter tabelas e gráficos legíveis. Se for mantido, deve ser feito só na apresentação (relatório e gráficos), não no dado que vai para os CSVs e para a chave do consolidado.

## Possible Fix

Aplicado: `edital.py` guarda o nome inteiro, e só a apresentação abrevia, com `abreviar(texto, limite)` de `texto.py`, que corta no último espaço e acrescenta "…". O `relatorio.md` usa `LIMITE_TOPICO = 150`; os gráficos, o notebook e o catálogo mantêm os limites que já tinham. CSVs, parquet e `chave_topico` ficam com o nome completo, e `VERSAO_ANALISE` subiu para 9. Nos dados reais, a reanálise mudou só nomes de tópico, `chave_topico`, `topico_sugerido` e `score`: 33 nomes que estavam cortados voltaram inteiros, e nenhuma sugestão trocou de tópico. Coberto por `test_nome_de_topico_longo_fica_inteiro` em `tests/test_edital.py` e `test_nome_de_topico_longo_fica_inteiro_nos_csvs_e_abreviado_no_relatorio` em `tests/test_cli_topicos.py`.

---

## Lacunas em relação à spec (fechadas)

Eram escolhas de tickets anteriores, registradas para reavaliação. As duas foram fechadas:

- **`status` não acusava edital ausente.** Agora o edital é obrigatório: sem `edital` no `concurso.yaml` (nem `arquivo`, nem `manual`), o concurso fica incompleto, com o motivo "edital ausente; adicione o PDF do edital à pasta e rode `concurso-analise add <pasta>`". O `add` grava o yaml mesmo sem edital e avisa que o concurso fica incompleto. Um edital sem conteúdo programático continua no modo mínimo, com os tópicos `nao_mapeado`.
- **A revisão manual de tópicos só existia com edital.** `revisao/questoes_revisado.csv` passou a ser criado também sem tópicos do edital (modo mínimo ou edital manual sem conhecimentos), com a disciplina sugerida pelas faixas do `concurso.yaml` (ou `nao_mapeado`), o tópico sugerido `nao_mapeado` e o enunciado do caderno, quando houver. A revisão se aplica como antes.
