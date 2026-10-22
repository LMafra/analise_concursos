# 13: `doctor`

**What to build:** `concurso-analise doctor` diagnostica o ambiente e marca cada item com ✓, ! ou ✗, com o comando de correção para o sistema do usuário (apt, brew ou winget). Itens verificados:

- uv;
- versão do Python;
- Tesseract e idioma `por`;
- poppler, só informativo, porque não é necessário;
- permissão de escrita nas pastas;
- espaço em disco.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Com o Tesseract fora do PATH, o item sai com ✗ e o comando de instalação do sistema detectado, e o código de saída é diferente de zero.
- [ ] Com o Tesseract presente mas sem `por`, o item sai com ! e o comando do pacote de idioma.
- [ ] Uma pasta sem permissão de escrita sai com ✗ e a pasta citada.
- [ ] O poppler aparece como "não necessário".
- [ ] Com tudo certo, o código de saída é 0.
