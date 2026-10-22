# 03: Configuração e taxonomia do projeto, sem dado pessoal no pacote

**What to build:** os limiares, o concurso-alvo e a taxonomia de disciplinas saem da raiz do código e passam para a configuração do projeto (`./.concurso/config.toml` e `./.concurso/taxonomia.yaml`).

- **Disciplina desconhecida:** deixa de reprovar a validação e vira canônica de si mesma, com aviso.
- **Notebooks:** carregam a configuração sem montar caminho.
- **Registro do edital:** o de "candidatos à descoberta" passa a se chamar "pistas do edital".
- **Dado pessoal:** um teste garante que o pacote não contém nenhum.

**Blocked by:** 02

**Status:** done

- [x] Os limiares e o concurso-alvo são lidos do `config.toml` do projeto, com a mesma validação de hoje: campo desconhecido ou valor fora de 0 a 1 gera erro com o campo e as opções.
- [x] A taxonomia vem de `./.concurso/taxonomia.yaml`. Sem o arquivo, todas as disciplinas viram canônicas de si mesmas.
- [x] Uma disciplina fora da taxonomia vira canônica de si mesma, com bloco vindo da prova ou `nao_informado`, e gera aviso com a lista de nomes, em vez de reprovar.
- [x] Os notebooks usam a configuração do contexto e não citam `config.yaml` nem `raiz_do_projeto()`.
- [x] O registro de pistas do edital troca de nome, e o campo serializado de versão do `edital_estruturado.json` não muda.
- [x] Um teste procura no pacote os slugs dos concursos de exemplo, padrões de CPF e caminhos absolutos de usuário.
- [x] O `docs/modelo.md` descreve o `config.toml` do projeto.
- [x] A paridade com os dados reais não mostra diferença.
