# Code smells encontrados na revisão de código

Revisão feita sobre as mudanças desde o commit inicial `9c59679`. Nenhum destes itens altera o comportamento hoje: são pontos que tornam a próxima mudança mais cara ou mais arriscada. Os bugs estão em [bugs.md](bugs.md).

| Smell | Onde | Prioridade | Situação |
| --- | --- | --- | --- |
| [Strings mágicas para banca e status](#banca-e-status-como-strings) | `cadastro`, `pipeline`, `gabarito`, `atualizacao`, `relatorio`, `consolidado` | Alta | Aberto |
| [Arquivos referenciados calculados em três lugares](#arquivos-referenciados-em-tres-lugares) | `cadastro`, `atualizacao`, `status` | Média | Aberto |
| [Duas funções `normalizar` divergentes](#normalizacao-duplicada) | `deteccao`, `gabarito` | Média | Aberto |
| [Heurística por nome de arquivo para gabarito em txt](#gabarito-txt-pelo-nome) | `deteccao` | Média | Aberto |
| [Grupo de argumentos em `carregar_gabarito`](#grupo-de-argumentos-em-carregar_gabarito) | `gabarito` | Baixa | Aberto |
| [Acesso encadeado ao yaml como dicionário](#acesso-encadeado-ao-yaml) | `cadastro`, `atualizacao` | Baixa | Aberto |
| [`_caderno_pdf` fora de `ProvaConfig`](#_caderno_pdf-fora-de-provaconfig) | `pipeline` | Baixa | Aberto |
| [Parâmetro e propriedade sem uso](#codigo-sem-uso) | `deteccao` | Baixa | Aberto |
| [Duas funções `_juntar` com regras diferentes](#duas-funcoes-_juntar) | `edital`, `prova` | Baixa | Aberto |
| [Nome `_casa` pouco descritivo](#nome-_casa) | `atualizacao` | Baixa | Corrigido em `a611ef1` |

## Banca e status como strings

Os valores `'cebraspe'`, `'preliminar'` e `'definitivo'` aparecem como literais espalhados pelo código:

- `banca == 'cebraspe'`: `cadastro.py` (linhas 153, 174, 177, 238, 294), `pipeline.py:260`, `gabarito.py:183`, `atualizacao.py:182`;
- `status == 'preliminar'` ou `'definitivo'`: `cadastro.py:192`, `relatorio.py:62`, `consolidado.py:96`, `atualizacao.py` (linhas 52, 58, 66, 211).

**Risco:** um erro de digitação num desses pontos falha em silêncio, e acrescentar uma banca exige procurar todos os `if`. A validação de `BANCAS` e `STATUS_GABARITO` em `concurso_config.py` protege a entrada, mas não o código.

**Sugestão:** `class Banca(StrEnum)` e `class StatusGabarito(StrEnum)` em `concurso_config.py`, convertidos ao carregar o yaml. As decisões por banca (template da folha, segmentação, leitor de gabarito) podem virar propriedades da enum, por exemplo `Banca.certo_errado`.

## Arquivos referenciados em três lugares

O conjunto de arquivos que o `concurso.yaml` referencia é montado três vezes:

- `Cadastro._ignorados` (`cadastro.py:324`), a partir do dicionário do yaml;
- `_nao_cadastrados` (`atualizacao.py`), a partir de `ConcursoConfig`;
- `avaliar` (`status.py`), que verifica arquivo a arquivo com uma mensagem própria para cada um.

**Risco:** um novo campo de arquivo no yaml precisa ser lembrado nos três lugares; se `atualizacao` esquecer o campo, o arquivo é tratado como "não cadastrado" e o concurso fica desatualizado para sempre, mesmo depois de rodar `concursos adicionar`.

**Sugestão:** uma propriedade `ConcursoConfig.arquivos_referenciados -> dict[str, str]` (caminho → papel) usada por `atualizacao` e `status`. O `cadastro` trabalha antes de existir um `ConcursoConfig`, mas pode montar um a partir do dicionário gerado.

## Normalização duplicada

`deteccao.normalizar` (`deteccao.py:62`) e `gabarito._normalizar` (`gabarito.py:132`) removem acentos e espaços extras, mas divergem: a primeira converte para maiúsculas e troca `–` e `—` por `-`; a segunda usa `casefold` e só troca `–`.

**Risco:** comparações entre textos normalizados pelas duas funções não batem, e uma correção feita numa não chega à outra.

**Sugestão:** uma única função num módulo comum (por exemplo `texto.py`), com a caixa como parâmetro ou com a comparação feita sempre em `casefold`.

## Gabarito txt pelo nome

`classificar_texto_manual` (`deteccao.py:148`) classifica um txt ou csv como gabarito quando a palavra "gabarito" aparece no nome do arquivo ou no texto; caso contrário, se as linhas forem válidas, ele vira respostas.

**Risco:** um arquivo `respostas_conferidas_com_gabarito.txt` vira gabarito; um gabarito chamado `definitivo.txt` sem a palavra no conteúdo vira respostas. O erro aparece como notas absurdas, não como mensagem.

**Sugestão:** exigir um cabeçalho explícito no txt (por exemplo `# gabarito definitivo`) ou perguntar no `concursos adicionar` quando o papel não for inequívoco.

## Grupo de argumentos em `carregar_gabarito`

`carregar_gabarito(caminho, formato, banca, cargo, tipo)` (`gabarito.py:170`) recebe cinco valores que sempre vêm juntos da mesma `ProvaConfig` e do mesmo `ConcursoConfig`, e repassa parte deles para `_ler_secoes` e `selecionar_secao`.

**Sugestão:** um dataclass `FonteGabarito(caminho, formato, banca, cargo, tipo)` montado a partir da configuração, ou passar `ProvaConfig` e `banca` diretamente.

## Acesso encadeado ao yaml

`Cadastro._ignorados` e `_atualizar_config` navegam no dicionário cru do yaml: `prova['gabarito']['arquivo']`, `(dados.get('respostas') or {}).get('folha')`, `dados['provas'][troca.prova]['gabarito'] = ...`.

**Risco:** a estrutura do yaml fica conhecida em mais de um lugar além de `concurso_config.py`; mudar o formato quebra esses pontos sem erro de tipo.

**Sugestão:** concentrar leitura e escrita do yaml em `concurso_config.py` (por exemplo `ConcursoConfig.com_gabarito(prova, arquivo, status)` devolvendo o dicionário a gravar).

## `_caderno_pdf` fora de `ProvaConfig`

`_caderno_pdf(prova)` (`pipeline.py:204`) só olha atributos de `ProvaConfig`.

**Sugestão:** propriedade `ProvaConfig.caderno_pdf`.

## Código sem uso

- O parâmetro `nome` de `classificar_texto` (`deteccao.py:67`) não é usado no corpo da função.
- A propriedade `ArquivoDetectado.nome` (`deteccao.py:58`) não é usada; o cadastro usa `Cadastro._nome`, que devolve o caminho relativo.

**Sugestão:** remover os dois.

## Duas funções `_juntar`

`edital._juntar` (`edital.py:348`) junta linhas desfazendo hifenização; `prova._juntar` (`prova.py:122`) só junta e colapsa espaços. Mesmo nome, regras diferentes.

**Risco:** baixo hoje, mas o texto do caderno também chega com palavras hifenizadas na quebra de linha, o que piora o TF-IDF.

**Sugestão:** uma função pública em módulo comum que desfaz hifenização, usada pelos dois.

## Nome `_casa`

A função que verifica se um gabarito não cadastrado corresponde a uma prova chamava-se `_casa`. Foi renomeada para `_corresponde_a_prova` em `a611ef1`.
