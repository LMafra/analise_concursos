# Code smells encontrados na revisão de código

Revisão feita sobre as mudanças desde o commit inicial `9c59679`. Nenhum destes itens alterava o comportamento: eram pontos que tornavam a próxima mudança mais cara ou mais arriscada. Os bugs estão em [bugs.md](bugs.md). Todos foram resolvidos: os refactors sem mudança de saída em `b54ec2c` (paridade sem diferença), e o txt ambíguo e o `_juntar` em `251190e`, porque mudam o comportamento.

| Smell | Onde | Prioridade | Situação |
| --- | --- | --- | --- |
| [Strings mágicas para banca e status](#banca-e-status-como-strings) | `cadastro`, `pipeline`, `gabarito`, `atualizacao`, `relatorio`, `consolidado` | Alta | Corrigido: banca nos perfis da fase 4, status em `b54ec2c` |
| [Arquivos referenciados calculados em três lugares](#arquivos-referenciados-em-tres-lugares) | `cadastro`, `atualizacao`, `status` | Média | Corrigido em `b54ec2c` |
| [Duas funções `normalizar` divergentes](#normalizacao-duplicada) | `deteccao`, `gabarito` | Média | Corrigido em `b54ec2c` |
| [Heurística por nome de arquivo para gabarito em txt](#gabarito-txt-pelo-nome) | `deteccao` | Média | Corrigido em `251190e` |
| [Grupo de argumentos em `carregar_gabarito`](#grupo-de-argumentos-em-carregar_gabarito) | `gabarito` | Baixa | Corrigido em `b54ec2c` |
| [Acesso encadeado ao yaml como dicionário](#acesso-encadeado-ao-yaml) | `cadastro`, `atualizacao` | Baixa | Corrigido em `b54ec2c` |
| [`_caderno_pdf` fora de `ProvaConfig`](#_caderno_pdf-fora-de-provaconfig) | `pipeline` | Baixa | Corrigido em `b54ec2c` |
| [Parâmetro e propriedade sem uso](#codigo-sem-uso) | `deteccao` | Baixa | Corrigido em `b54ec2c` |
| [Duas funções `_juntar` com regras diferentes](#duas-funcoes-_juntar) | `edital`, `prova` | Baixa | Corrigido em `251190e` |
| [Nome `_casa` pouco descritivo](#nome-_casa) | `atualizacao` | Baixa | Corrigido em `a611ef1` |

## Banca e status como strings

Os valores `'cebraspe'`, `'preliminar'` e `'definitivo'` aparecem como literais espalhados pelo código:

- `banca == 'cebraspe'`: `cadastro.py` (linhas 153, 174, 177, 238, 294), `pipeline.py:260`, `gabarito.py:183`, `atualizacao.py:182`;
- `status == 'preliminar'` ou `'definitivo'`: `cadastro.py:192`, `relatorio.py:62`, `consolidado.py:96`, `atualizacao.py` (linhas 52, 58, 66, 211).

**Risco:** um erro de digitação num desses pontos falha em silêncio, e acrescentar uma banca exige procurar todos os `if`. A validação de `BANCAS` e `STATUS_GABARITO` em `concurso_config.py` protege a entrada, mas não o código.

**Sugestão:** `class Banca(StrEnum)` e `class StatusGabarito(StrEnum)` em `concurso_config.py`, convertidos ao carregar o yaml. As decisões por banca (template da folha, segmentação, leitor de gabarito) podem virar propriedades da enum, por exemplo `Banca.certo_errado`.

**Resolução:** a banca virou perfil YAML na fase 4 (`perfis/bancas/`), e as decisões por banca são campos do perfil, não `if`. O status virou `StatusGabarito(StrEnum)` em `modelo.py`, sem membro `misto` (`ConcursoConfig.status_gabarito` continua devolvendo `'misto'` como texto). O yaml grava `.value`, porque o `yaml.safe_dump` recusa `StrEnum`. O parâmetro `cebraspe` de `prova.segmentar` virou `por_itens`.

## Arquivos referenciados em três lugares

O conjunto de arquivos que o `concurso.yaml` referencia é montado três vezes:

- `Cadastro._ignorados` (`cadastro.py:324`), a partir do dicionário do yaml;
- `_nao_cadastrados` (`atualizacao.py`), a partir de `ConcursoConfig`;
- `avaliar` (`status.py`), que verifica arquivo a arquivo com uma mensagem própria para cada um.

**Risco:** um novo campo de arquivo no yaml precisa ser lembrado nos três lugares; se `atualizacao` esquecer o campo, o arquivo é tratado como "não cadastrado" e o concurso fica desatualizado para sempre, mesmo depois de rodar `concursos adicionar`.

**Sugestão:** uma propriedade `ConcursoConfig.arquivos_referenciados -> dict[str, str]` (caminho → papel) usada por `atualizacao` e `status`. O `cadastro` trabalha antes de existir um `ConcursoConfig`, mas pode montar um a partir do dicionário gerado.

**Resolução:** como sugerido. O `cadastro` monta o `ConcursoConfig` com `validar_dados`, o que também passou a cobrir o `edital.manual`. O `status` usa o papel na mensagem e, em `251190e`, trata caderno e resultado oficial ausentes como aviso, sem tirar o concurso de completo.

## Normalização duplicada

`deteccao.normalizar` (`deteccao.py:62`) e `gabarito._normalizar` (`gabarito.py:132`) removem acentos e espaços extras, mas divergem: a primeira converte para maiúsculas e troca `–` e `—` por `-`; a segunda usa `casefold` e só troca `–`.

**Risco:** comparações entre textos normalizados pelas duas funções não batem, e uma correção feita numa não chega à outra.

**Sugestão:** uma única função num módulo comum (por exemplo `texto.py`), com a caixa como parâmetro ou com a comparação feita sempre em `casefold`.

**Resolução:** `texto.normalizar`, com o comportamento da antiga `deteccao.normalizar` (maiúsculas, `–` e `—` viram `-`). `gabarito._normalizar` deixou de existir.

## Gabarito txt pelo nome

`classificar_texto_manual` (`deteccao.py:148`) classifica um txt ou csv como gabarito quando a palavra "gabarito" aparece no nome do arquivo ou no texto; caso contrário, se as linhas forem válidas, ele vira respostas.

**Risco:** um arquivo `respostas_conferidas_com_gabarito.txt` vira gabarito; um gabarito chamado `definitivo.txt` sem a palavra no conteúdo vira respostas. O erro aparece como notas absurdas, não como mensagem.

**Sugestão:** exigir um cabeçalho explícito no txt (por exemplo `# gabarito definitivo`) ou perguntar no `concursos adicionar` quando o papel não for inequívoco.

**Resolução:** o papel só é firme quando o nome do arquivo tem exatamente um sinal, "GABARITO" ou "RESPOSTA". Sem sinal no nome (mesmo que o conteúdo cite "gabarito") ou com os dois, `ArquivoDetectado.ambiguo` fica verdadeiro e o `add` pergunta, com a heurística antiga como sugestão. Sem TTY, a sugestão é aceita e um aviso vai para o log.

## Grupo de argumentos em `carregar_gabarito`

`carregar_gabarito(caminho, formato, banca, cargo, tipo)` (`gabarito.py:170`) recebe cinco valores que sempre vêm juntos da mesma `ProvaConfig` e do mesmo `ConcursoConfig`, e repassa parte deles para `_ler_secoes` e `selecionar_secao`.

**Sugestão:** um dataclass `FonteGabarito(caminho, formato, banca, cargo, tipo)` montado a partir da configuração, ou passar `ProvaConfig` e `banca` diretamente.

**Resolução:** `carregar_gabarito(caminho, config)`, com o `ConcursoConfig` inteiro.

## Acesso encadeado ao yaml

`Cadastro._ignorados` e `_atualizar_config` navegam no dicionário cru do yaml: `prova['gabarito']['arquivo']`, `(dados.get('respostas') or {}).get('folha')`, `dados['provas'][troca.prova]['gabarito'] = ...`.

**Risco:** a estrutura do yaml fica conhecida em mais de um lugar além de `concurso_config.py`; mudar o formato quebra esses pontos sem erro de tipo.

**Sugestão:** concentrar leitura e escrita do yaml em `concurso_config.py` (por exemplo `ConcursoConfig.com_gabarito(prova, arquivo, status)` devolvendo o dicionário a gravar).

**Resolução:** `ler_dados`, `gravar_dados` e `com_gabarito_definitivo` em `concurso_config.py`. `_atualizar_config` só grava, e o `cadastro` lê e grava pelas mesmas funções.

## `_caderno_pdf` fora de `ProvaConfig`

`_caderno_pdf(prova)` (`pipeline.py:204`) só olha atributos de `ProvaConfig`.

**Sugestão:** propriedade `ProvaConfig.caderno_pdf`.

**Resolução:** como sugerido.

## Código sem uso

- O parâmetro `nome` de `classificar_texto` (`deteccao.py:67`) não é usado no corpo da função.
- A propriedade `ArquivoDetectado.nome` (`deteccao.py:58`) não é usada; o cadastro usa `Cadastro._nome`, que devolve o caminho relativo.

**Sugestão:** remover os dois.

**Resolução:** removidos.

## Duas funções `_juntar`

`edital._juntar` (`edital.py:348`) junta linhas desfazendo hifenização; `prova._juntar` (`prova.py:122`) só junta e colapsa espaços. Mesmo nome, regras diferentes.

**Risco:** baixo hoje, mas o texto do caderno também chega com palavras hifenizadas na quebra de linha, o que piora o TF-IDF.

**Sugestão:** uma função pública em módulo comum que desfaz hifenização, usada pelos dois.

**Resolução:** `texto.juntar_linhas`, usada por `edital` e `prova`. Como o caderno passou a chegar sem hifenização, algumas sugestões de tópico mudaram de `score`.

## Nome `_casa`

A função que verifica se um gabarito não cadastrado corresponde a uma prova chamava-se `_casa`. Foi renomeada para `_corresponde_a_prova` em `a611ef1`.
