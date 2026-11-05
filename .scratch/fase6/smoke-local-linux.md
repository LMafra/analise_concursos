# Smoke local do AppImage (fatia D)

Build no contêiner `quay.io/pypa/manylinux_2_28_x86_64` com `bash empacotamento/linux/construir.sh` (versão 0.5.0 do pacote, árvore da fatia D).

- `verificar_bibliotecas.sh`: Tesseract com 29 bibliotecas, todas de `tesseract/lib`; 326 arquivos ELF do bundle conferidos por `ldd`; ok. Tirando `libc.so.6` da lista permitida, o script falha (325 problemas), o que confirma que ele pega biblioteca do sistema.
- AppDir: `.DirIcon` → `concurso-analise.png`, ícone em `usr/share/icons/hicolor/256x256/apps/`, `.desktop` com `X-AppImage-Version=0.5.0`, válido no `desktop-file-validate`.

| Contêiner | `--smoke` | OCR | Partida | `doctor` |
|---|---|---|---|---|
| `debian:12` | ok | leu "CONCURSO 2026" | 2,4 s | sem erros |
| `ubuntu:22.04` | ok | leu "CONCURSO 2026" | 2,6 s | sem erros |

`scripts/smoke.py congelado` no host (Ubuntu no WSL): onboarding e análise de dois concursos em 3,8 s, idempotente.
