# 08: AppImage e DMG arm64

**What to build:** AppImage montado num contêiner `manylinux_2_28`, com o Tesseract do AppImage oficial; `.app` num DMG (create-dmg) no `macos-latest`, com o Tesseract enxuto relocado por `delocate`; jobs no `release.yml`.

**Blocked by:** 07

**Status:** done no Linux; macOS escrito, à espera do primeiro run do `release.yml`

- [x] O AppImage roda o `--smoke` num contêiner `debian:12` sem Python e sem Tesseract (versão, 9 perfis de banca, Tesseract embutido com `por`, GUI em 127.0.0.1) e o `doctor` sai com 0.
- [x] `scripts/smoke.py congelado` contra o AppImage: onboarding e análise em 4 s, com o Tesseract embutido.
- [ ] O `.app` roda o `--smoke` no runner; o DMG abre depois do "Abrir Mesmo Assim".

## Notas

- AppImage de 241 MB (Python 3.12 do uv, porque o do manylinux não tem a libpython compartilhada).
- O Tesseract do AppImage do AlexanderP traz a própria glibc e o próprio carregador; o `bin/tesseract` embutido é um wrapper que chama `ld-linux --library-path ../lib ../libexec/tesseract`. O executável restaura o `LD_LIBRARY_PATH` original (`LD_LIBRARY_PATH_ORIG`) antes de chamar processos do sistema, como o navegador.
- O PyInstaller 6 reclassifica `.so` de `datas` como binários e puxa as dependências deles para a raiz: a `libstdc++` do Tesseract (GLIBC_2.38) foi parar em `_internal/` e quebrou o executável no Debian 12. Por isso o `.spec` copia a árvore do Tesseract depois do `COLLECT` (`copiar_tesseract`).
- Desvio do plano no macOS: em vez de compilar um Tesseract enxuto e relocar com `delocate`, `obter_macos.sh` copia o `tesseract` do Homebrew e relocaliza só as dylibs de que ele depende com o `dylibbundler` (`@executable_path/../lib`), com assinatura ad hoc. O resultado é o mesmo (sem caminho do Homebrew, conferido com `otool -L`), sem manter uma receita de compilação.
- O gate do macOS monta o DMG, copia o `.app` para fora, confere a assinatura e roda `scripts/smoke.py congelado` com `PATH=/usr/bin:/bin:/usr/sbin:/sbin`.
- O job `publicar` cria a release como rascunho com o `SHA256SUMS`: ela só é publicada depois do checklist manual do Windows Sandbox (ticket 07).
