# Smoke local do AppImage (fatia D)

Build no contêiner `quay.io/pypa/manylinux_2_28_x86_64` com `bash empacotamento/linux/construir.sh` (versão 0.5.0 do pacote, árvore da fatia D).

- `verificar_bibliotecas.sh`: Tesseract com 29 bibliotecas, todas de `tesseract/lib`; 326 arquivos ELF do bundle conferidos por `ldd`; ok. Tirando `libc.so.6` da lista permitida, o script falha (325 problemas), o que confirma que ele pega biblioteca do sistema.
- AppDir: `.DirIcon` → `concurso-analise.png`, ícone em `usr/share/icons/hicolor/256x256/apps/`, `.desktop` com `X-AppImage-Version=0.5.0`, válido no `desktop-file-validate`.

| Contêiner | `--smoke` | OCR | Partida | `doctor` |
|---|---|---|---|---|
| `debian:12` | ok | leu "CONCURSO 2026" | 2,4 s | sem erros |
| `ubuntu:22.04` | ok | leu "CONCURSO 2026" | 2,6 s | sem erros |

`scripts/smoke.py congelado` no host (Ubuntu no WSL): onboarding e análise de dois concursos em 3,8 s, idempotente.

## Fatia F (tema, onboarding, etapas)

Build no mesmo contêiner, a partir de `git archive` do commit da fatia F (versão 0.5.0), com `cryptography` e `packaging` congelados.

| Contêiner | `--smoke` | OCR | Partida | `doctor` | `upgrade --help` |
|---|---|---|---|---|---|
| `debian:12` | ok | leu "CONCURSO 2026" | 2,6 s | sem erros | ok |
| `ubuntu:22.04` | ok | leu "CONCURSO 2026" | 3,2 s | sem erros | ok |

A partida inclui a extração do AppImage (`APPIMAGE_EXTRACT_AND_RUN=1`, sem FUSE no contêiner); com FUSE, ela não acontece a cada abertura. O gate da CI usa 10 s.

`scripts/smoke.py congelado` no host: onboarding e análise em 4,2 s, idempotente.

GUI pelo AppImage, com `HOME` vazio, no navegador: pasta do projeto, assistente de 4 passos, "Pular" no passo 3 (nada gravado em `[llm]` nem `[atualizacao]`), "Ver com um exemplo" com o relatório na tela em poucos segundos. O teste achou dois defeitos, corrigidos e conferidos no navegador pela GUI de desenvolvimento:

- Botões do cabeçalho azuis sobre o azul: o NiceGUI põe o `!important` do Quasar na camada `quasar_importants`, que vence qualquer `!important` sem camada. As regras com `!important` do `gui/tema.py` foram para `@layer overrides` (teste em `tests/gui/test_tema.py`).
- Ícone do título do cartão com ~10 px: `size='sm'`.

Conferido também: modo escuro (cabeçalho, cartões, abas, estado vazio de Concursos e de Resultados), e "Conferir o ambiente" no Sobre (o botão agora mostra carregando durante os ~5 s do `doctor`).
