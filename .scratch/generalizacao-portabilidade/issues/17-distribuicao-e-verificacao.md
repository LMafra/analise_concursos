# 17: Distribuição e verificação nos 3 ambientes

**What to build:** a ferramenta fica pronta para distribuir e é verificada nos três ambientes disponíveis:

- um Dockerfile, com `tesseract-ocr-por`, e um smoke test em container limpo;
- verificação no Windows nativo pelo `powershell.exe`;
- o workflow de CI escrito (Ubuntu, macOS e Windows; Python 3.11 e 3.12), ainda sem execução porque não há remoto;
- o teste de idempotência por `mtime`;
- o comando `upgrade`.

**Blocked by:** 05, 09, 15, 16

**Status:** ready-for-agent

- [ ] Num container com só o uv, `uvx --from . concurso-analise --yes` faz o onboarding e gera o relatório de um concurso sintético em até 5 minutos.
- [ ] `uvx --from . concurso-analise --dry-run --yes` funciona no Linux/WSL, no container e no Windows nativo.
- [ ] Duas execuções seguidas, e também duas com `--dry-run`, não alteram nenhum `mtime` em `analises/`.
- [ ] `upgrade` imprime ou roda `uv tool upgrade concurso-analise`, e só quando o usuário pede.
- [ ] O workflow de CI está escrito, e o macOS está registrado como não verificado.
