#!/usr/bin/env bash
# Monta dist/gabarito-vivo-<versão>-linux-x86_64.AppImage a partir do onedir em dist/gabarito-vivo.
#
# O AppDir leva o .desktop com X-AppImage-Version, o .DirIcon e o ícone no hicolor, que o AppImageLauncher e o
# Gear Lever usam para pôr o app no menu.
#
# Uso: bash empacotamento/linux/montar_appimage.sh <versão>
set -euo pipefail

VERSAO=$1
APPIMAGETOOL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
AQUI=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(cd "$AQUI/../.." && pwd)
cd "$RAIZ"

ONEDIR=dist/gabarito-vivo
if [ ! -d "$ONEDIR" ]; then
  ONEDIR=dist/concurso-analise
fi
bash "$AQUI/verificar_bibliotecas.sh" "$ONEDIR"

APPDIR=build/AppDir
ICONES="$APPDIR/usr/share/icons/hicolor/256x256/apps"
rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$ICONES"
NOME_DIR=$(basename "$ONEDIR")
cp -a "$ONEDIR" "$APPDIR/$NOME_DIR"
ICONE_PNG=empacotamento/icones/gabarito-vivo-256.png
if [ ! -f "$ICONE_PNG" ]; then
  ICONE_PNG=empacotamento/icones/concurso-analise-256.png
fi
cp "$ICONE_PNG" "$ICONES/gabarito-vivo.png"
cp "$ICONE_PNG" "$APPDIR/gabarito-vivo.png"
ln -s gabarito-vivo.png "$APPDIR/.DirIcon"
{
    cat "$AQUI/concurso-analise.desktop"
    echo "X-AppImage-Version=$VERSAO"
} > "$APPDIR/gabarito-vivo.desktop"
if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate "$APPDIR/gabarito-vivo.desktop"
fi
install -m 755 "$AQUI/AppRun" "$APPDIR/AppRun"

FERRAMENTA=build/appimagetool-x86_64.AppImage
if [ ! -x "$FERRAMENTA" ]; then
    curl -fsSLo "$FERRAMENTA" "$APPIMAGETOOL"
    chmod +x "$FERRAMENTA"
fi
SAIDA="dist/gabarito-vivo-$VERSAO-linux-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$FERRAMENTA" --no-appstream "$APPDIR" "$SAIDA"
echo "AppImage em $SAIDA ($(du -h "$SAIDA" | cut -f1))"
