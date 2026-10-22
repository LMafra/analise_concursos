# 17: Distribuição e verificação nos 3 ambientes

**What to build:** a ferramenta fica pronta para distribuir e é verificada nos três ambientes disponíveis:

- um Dockerfile, com `tesseract-ocr-por`, e um smoke test em container limpo;
- verificação no Windows nativo pelo `powershell.exe`;
- o workflow de CI escrito (Ubuntu, macOS e Windows; Python 3.11 e 3.12), ainda sem execução porque não há remoto;
- o teste de idempotência por `mtime`;
- o comando `upgrade`.

**Blocked by:** 05, 09, 15, 16

**Status:** done

- [x] Num container com só o uv, `uvx --from . concurso-analise --yes` faz o onboarding e gera o relatório de um concurso sintético em até 5 minutos. (`scripts/smoke.py` em `ghcr.io/astral-sh/uv:0.13.0-trixie-slim`: 44 s com o download da imagem e das dependências.)
- [x] `uvx --from . concurso-analise --dry-run --yes` funciona no Linux/WSL, no container e no Windows nativo. (Linux/WSL e container verificados; o Windows nativo ficou não verificado por decisão do usuário, sem `uv` instalado no Windows.)
- [x] Duas execuções seguidas, e também duas com `--dry-run`, não alteram nenhum `mtime` em `analises/`. (`tests/test_idempotencia.py`, o smoke e os 135 arquivos dos dados reais.)
- [x] `upgrade` imprime ou roda `uv tool upgrade concurso-analise`, e só quando o usuário pede.
- [x] O workflow de CI está escrito, e o macOS está registrado como não verificado.

Achados: o pacote instalado pelo `uvx` não abria, porque `plotly`, `pyarrow` e `scipy` estavam só nos grupos de dev e análise; passaram a dependências. O `ipython` entrou no grupo dev, que o teste de HTML do notebook exige. O consolidado era regravado a cada execução; agora só grava quando o conteúdo muda.
