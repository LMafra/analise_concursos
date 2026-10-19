# 03: Gabarito Cebraspe em PDF

**What to build:** o usuário aponta no `concurso.yaml` o PDF oficial de gabarito da Cebraspe e a análise funciona sem transcrição manual. O parser lê as linhas Item/Gabarito, reconhece "X" como anulada, ignora os zeros de preenchimento, valida a contagem contra a faixa de itens e detecta se o gabarito é preliminar ou definitivo. Isso inclui a camada de extração de texto (pdfplumber por página, com fallback para Tesseract e erro claro se ele não estiver instalado).

**Blocked by:** 01

**Status:** done

- [x] Trechos reais anonimizados dos gabaritos Cebraspe (CG e CE) são interpretados corretamente nos testes de texto para estrutura.
- [x] Contagem diferente da faixa configurada gera erro apontando arquivo, prova e contagens.
- [x] O status preliminar ou definitivo é detectado pelo texto.
- [x] Os gabaritos reais de `cd_25`, `funpresp_jud`, `infrasa`, `tcu_25`, `pf_perito` e `telebras` extraem as faixas esperadas (verificação manual registrada no ticket).
- [x] Um PDF sem texto com Tesseract ausente gera erro claro com instrução de instalação.

## Verificação manual (19/10/2026)

| Gabarito | Faixa | Itens | Anuladas | Status |
|---|---|---|---|---|
| cd_25 CG / CE | 1-90 / 91-180 | 90 / 90 | 2 / 2 | definitivo |
| funpresp_jud CG / CE | 1-50 / 51-120 | 50 / 70 | 4 / 0 | definitivo |
| infrasa CG / CE | 1-40 / 41-100 | 40 / 60 | 1 / 1 | definitivo |
| pf_perito CB / CE | 1-50 / 51-120 | 50 / 70 | 4 / 1 | definitivo |
| tcu_25 CB / CE | 1-100 / 101-200 | 100 / 100 | 3 / 12 | definitivo |
| telebras CB / CE | 1-50 / 51-120 | 50 / 70 | 1 / 0 | definitivo |
