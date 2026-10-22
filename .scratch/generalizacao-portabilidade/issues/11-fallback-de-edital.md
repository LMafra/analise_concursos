# 11: Fallback de edital sem LLM

**What to build:** um edital de banca desconhecida, ou ilegível, não aborta mais a análise.

A extração passa pelas camadas perfil, heurística genérica e modo mínimo (só o conteúdo programático), e cada campo registra a camada que o preencheu. Se ainda faltar algo, o app gera `provas/<concurso>/edital_a_confirmar.yaml` com o que foi extraído e os campos faltantes vazios. Esse arquivo entra no manifesto.

A confiança agregada do edital vira um selo por concurso no `index.html`.

**Blocked by:** 08, 10

**Status:** ready-for-agent

- [ ] Um edital em imagem de banca fictícia, sem Tesseract, cai no modo mínimo, avisa com `dica:` e gera o `edital_a_confirmar.yaml`.
- [ ] Preencher o arquivo e rodar de novo aplica os valores com fonte `config` e reprocessa todos os candidatos do concurso.
- [ ] O arquivo editado não é sobrescrito. Ele só ganha campos novos.
- [ ] O `edital_estruturado.json` traz a camada e a confiança de cada campo, além da confiança agregada.
- [ ] O selo (alta, média, baixa ou mínima) aparece por concurso no `index.html`.
- [ ] O `docs/modelo.md` descreve o `edital_a_confirmar.yaml` e a confiança agregada.
