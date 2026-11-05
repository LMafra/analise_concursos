#!/usr/bin/env bash
# Monta dist/concurso-analise-<versão>-linux-x86_64.AppImage a partir do onedir em dist/concurso-analise.
#
# Uso: bash empacotamento/linux/montar_appimage.sh <versão>
set -euo pipefail

VERSAO=$1
APPIMAGETOOL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
AQUI=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$AQUI/../.." && pwd)
cd "$RAIZ"

APPDIR=build/AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR"
cp -a dist/concurso-analise "$APPDIR/concurso-analise"
cp empacotamento/icones/concurso-analise.png "$APPDIR/concurso-analise.png"
cp "$AQUI/concurso-analise.desktop" "$APPDIR/"
install -m 755 "$AQUI/AppRun" "$APPDIR/AppRun"

FERRAMENTA=build/appimagetool-x86_64.AppImage
if [ ! -x "$FERRAMENTA" ]; then
    curl -fsSLo "$FERRAMENTA" "$APPIMAGETOOL"
    chmod +x "$FERRAMENTA"
fi
SAIDA="dist/concurso-analise-$VERSAO-linux-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$FERRAMENTA" --no-appstream "$APPDIR" "$SAIDA"
echo "AppImage em $SAIDA ($(du -h "$SAIDA" | cut -f1))"
