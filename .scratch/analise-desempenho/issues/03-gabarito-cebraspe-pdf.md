# 03: Gabarito Cebraspe em PDF

**What to build:** o usuário aponta no `concurso.yaml` o PDF oficial de gabarito da Cebraspe e a análise funciona sem transcrição manual. O parser lê as linhas Item/Gabarito, reconhece "X" como anulada, ignora os zeros de preenchimento, valida a contagem contra a faixa de itens e detecta se o gabarito é preliminar ou definitivo. Isso inclui a camada de extração de texto (pdfplumber por página, com fallback para Tesseract e erro claro se ele não estiver instalado).

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Trechos reais anonimizados dos gabaritos Cebraspe (CG e CE) são interpretados corretamente nos testes de texto para estrutura.
- [ ] Contagem diferente da faixa configurada gera erro apontando arquivo, prova e contagens.
- [ ] O status preliminar ou definitivo é detectado pelo texto.
- [ ] Os gabaritos reais de `cd_25`, `funpresp_jud`, `infrasa`, `tcu_25`, `pf_perito` e `telebras` extraem as faixas esperadas (verificação manual registrada no ticket).
- [ ] Um PDF sem texto com Tesseract ausente gera erro claro com instrução de instalação.
