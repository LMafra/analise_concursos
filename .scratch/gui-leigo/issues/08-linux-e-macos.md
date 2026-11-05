# 08: AppImage e DMG arm64

**What to build:** AppImage montado num contêiner `manylinux_2_28`, com o Tesseract do AppImage oficial; `.app` num DMG (create-dmg) no `macos-latest`, com o Tesseract enxuto relocado por `delocate`; jobs no `release.yml`.

**Blocked by:** 07

**Status:** todo

- [ ] O AppImage roda o `--smoke` num contêiner `debian:12` sem Python.
- [ ] O `.app` roda o `--smoke` no runner; o DMG abre depois do "Abrir Mesmo Assim".
