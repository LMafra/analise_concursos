# 15: Calibração do OCR no wizard

**What to build:** a pergunta 4 do wizard ("Tem uma folha preenchida para calibrar?") passa a funcionar. O usuário aponta o arquivo e digita as respostas reais das 5 primeiras questões.

Com isso, o app:

1. detecta a grade;
2. ajusta o limiar de marcação e confirma o número de alternativas;
3. grava um perfil de OCR do projeto e a imagem de depuração.

**Blocked by:** 12, 14

**Status:** ready-for-agent

- [ ] Numa folha sintética com preenchimento fraco, a calibração ajusta o limiar, e as 5 questões passam a ser lidas certo.
- [ ] Respostas digitadas que contradizem a grade detectada reprovam a calibração com mensagem e `dica:`, e nada é gravado.
- [ ] O perfil calibrado é usado nas leituras seguintes do projeto.
