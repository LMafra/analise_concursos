# Contrato do arquivo exportado (v1)

O arquivo `tec-erros-<aparelho>-<data>.json` é o único contrato entre a captura (extensão do Chrome e userscript), o `caderno.html` e o `concurso-analise`. Campo desconhecido é ignorado com aviso, nunca é erro.

Os exemplos de `tests/contrato_tec/` (na raiz do monorepo) valem como especificação executável: `test/contrato.test.js` e `tests/test_contrato_tec.py` mesclam as mesmas exportações e comparam com `mesclagem_esperada.json`. Mudou uma regra abaixo, mude as fixtures e os dois lados juntos.

```json
{
  "app": "tec-erros",
  "v": 1,
  "em": "2026-11-02T21:15:03-03:00",
  "dev": "d3f9a1c2",
  "erros": [Erro],
  "cads": [Caderno]
}
```

## Erro

```json
{
  "id": "q12345678",
  "fp": "o contribuinte optante pelo simples nacional ...",
  "d": "2026-11-02",
  "t": 1762128903000,
  "v": 2,
  "ds": ["2026-11-02T21:15:03-03:00", "2026-11-05T08:02:44-03:00"],
  "dev": "d3f9a1c2",
  "origem": "tempo_real",
  "mat": "Direito Tributário", "ass": "Simples Nacional", "cad": "Caderno 20. Simples Nacional",
  "banca": "CEBRASPE", "orgao": "SEFAZ-DF", "ano": "2020",
  "enun": "texto do enunciado", "alts": [{"l": "A", "t": "..."}],
  "marc": "B", "gab": "C", "com": "comentário do professor", "prof": "Nome",
  "url": "https://www.tecconcursos.com.br/..."
}
```

- `id`: `q<idQuestao>` do TEC; sem ele, `h<hash>` dos primeiros 600 caracteres do enunciado (FNV-1a de 32 bits, em hexadecimal).
- `fp`: impressão digital, o enunciado sem acentos, em minúsculas, com espaços simples, cortado em 300 caracteres. O mesmo texto pode aparecer com ids diferentes; a mesclagem casa por `id` ou por `fp`.
- `ds`: data e hora ISO **locais**, com o fuso, de cada vez que você errou em tempo real; ordenada e sem repetição. Erros feitos no computador e no tablet no mesmo dia continuam distintos.
- `v`: o número de eventos de `ds`; um registro de histórico sem data conta 1 só quando não há nenhum evento de tempo real.
- `d`: a data (AAAA-MM-DD) do primeiro evento, ou da captura no modo histórico. `t`: quando o registro mudou pela última vez (milissegundos).
- `dev`: o aparelho que criou o registro, gerado uma vez e guardado.
- `origem`: `tempo_real` (você errou com o script rodando) ou `historico` (a questão já apareceu errada, resolvida no app). Um registro com algum evento de tempo real é `tempo_real`.
- Os demais campos podem faltar ou vir vazios; a mesclagem preenche o que faltava e nunca apaga o que já havia. O comentário (`com`, `prof`) só existe depois de "Ver resolução", então chega depois.

## Caderno

```json
{"id": "c87654321", "cad": "Caderno 20. Simples Nacional", "mat": "Direito Tributário",
 "tot": 484, "res": 2, "ac": 0, "er": 2, "d": "2026-11-02", "t": 1762128903000, "dev": "d3f9a1c2"}
```

`res`, `ac` e `er` só são atualizados quando `res` não diminui, no mesmo aparelho e na mesclagem entre aparelhos (a página pode estar carregando, e o progresso fica na conta do TEC).

## Mesclagem

1. Por `id`; sem casar por `id`, pela `fp` (quando não vazia).
2. `ds` é a união; `v = len(ds)`, ou 1 quando `ds` está vazia.
3. Campos vazios são preenchidos pelo outro registro; `com` fica com o texto mais longo.
4. `origem` é `tempo_real` se algum dos dois for; `d` é a menor; `t` é a maior; `dev` é o do registro mais antigo.
5. Se nada mudou, o resultado é o mesmo objeto (não regrava).

Cadernos: por `id`, fica o de maior `res`; no empate, o de maior `t`.

## Estado do caderno de erros (`caderno-estado.json`)

Exportado pelo `caderno.html`, para o `concurso-analise` reaproveitar as escolhas:

```json
{
  "app": "tec-erros-caderno", "v": 1,
  "status": {"q123": "revisado"},
  "removidos": ["q456", "fp:texto..."],
  "aliases": {"Simples Nacional": "Simples Nacional: regime e tributos", "Outro assunto": null},
  "materias": {"Direito Tributário": "Legislação Tributária"},
  "cadernos": {"c87654321": {"modo": "daqui", "base": {"res": 2, "ac": 0, "er": 2}}}
}
```

`aliases` com `null` é "não pertence a nenhum tópico". `modo` é `tudo` (a base é zero) ou `daqui` (a base é o total do primeiro registro).
