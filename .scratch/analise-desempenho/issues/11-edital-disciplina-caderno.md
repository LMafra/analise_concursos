# 11: Edital estruturado e disciplina pelo caderno

**What to build:** a análise extrai do edital (ou de um anexo, como no CPNU) o conteúdo programático do cargo configurado como conhecimento, disciplina e tópicos (peso opcional) e salva o edital estruturado em JSON. Se a extração falhar, exige um edital manual estruturado com erro claro. Nos cadernos FGV e SELECON, a disciplina de cada questão passa a vir dos cabeçalhos do caderno, sem depender das faixas manuais. A tabela de questões (número, disciplina, gabarito, anulada) é gerada por concurso.

**Blocked by:** 01

**Status:** done

- [x] Teste com trecho de edital com vários cargos: só o cargo configurado é extraído.
- [x] Teste com trecho de caderno FGV: as faixas por disciplina são extraídas.
- [x] Edital manual tem precedência quando presente, e a falha sem ele gera mensagem clara.
- [x] A verificação manual nos editais reais de `cd_25`, `agsus` e `cpnu` (anexo do Bloco 3) produz disciplinas coerentes.

## Verificação

- `edital.py` estrutura o conteúdo programático (anexos antes do principal; OCR só se o texto puro falhar) e grava `edital_estruturado.json`. Cobre títulos `CARGO/EMPREGO N:` e `NNN -`, área (`ÁREA:`) sob cargo, `Módulo I - Conhecimentos básicos`, títulos quebrados em duas linhas, eixos como disciplinas, disciplinas `NOME:`/`NOME 1.`/sem numeração (tópicos por frase) e restrições `(SOMENTE/EXCETO PARA ...)`. Edital com vários cargos sem `cargo` configurado falha listando os cargos.
- `edital.manual` (YAML) tem precedência; sem ele, falha de extração para a análise com mensagem que aponta `edital.manual` (formato a documentar em `docs/modelo.md`, ticket 15).
- `caderno.py`: faixas por disciplina pelos títulos em negrito (FGV Calibri-Bold 14; SELECON Arial-Bold 11), por coluna, ignorando capa. Faixas manuais do `concurso.yaml` têm precedência.
- `questoes.csv` (questao, prova, disciplina, gabarito, anulada) por concurso.
- O cadastro Cebraspe passa a preencher `cargo` pelo cabeçalho do gabarito de específicos e preserva `cargo`, `edital.manual` e `resultado_oficial.pesos` no recadastro.

| Concurso | Edital (cargo) | Disciplinas pelo caderno |
|---|---|---|
| cd_25 | Técnico Legislativo: 5 gerais + 4 específicas | Cebraspe (ticket 12) |
| agsus | 4 gerais + bloco TI (5) | LP 1-15, RLM 16-20, Legislação 21-30, Informática 31-40, TI 41-70 |
| cpnu (anexo) | Conhecimentos Gerais + eixos 1-5 | Gerais 1-30, eixos 31-42/43-54/55-66/67-78/79-90 |
| cprm | Básicos (LP, RLM, Atualidades) + ADS I-IX | LP 1-10, RLM 11-20, Atualidades 21-30, ADS 31-70 |
| senappen (caderno) | - | LP 1-8, Redação Oficial 9-12, Ética 13-20, Específicos 21-60 |
| infrasa, telebras, funpresp_jud, pf_perito, tcu_25, creci | cargo correto, disciplinas coerentes | - |
