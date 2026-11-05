#!/usr/bin/env bash
# Monta dist/concurso-analise-<versão>-linux-x86_64.AppImage a partir do onedir em dist/concurso-analise.
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

bash "$AQUI/verificar_bibliotecas.sh" dist/concurso-analise

APPDIR=build/AppDir
ICONES="$APPDIR/usr/share/icons/hicolor/256x256/apps"
rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$ICONES"
cp -a dist/concurso-analise "$APPDIR/concurso-analise"
cp empacotamento/icones/concurso-analise-256.png "$ICONES/concurso-analise.png"
cp empacotamento/icones/concurso-analise-256.png "$APPDIR/concurso-analise.png"
ln -s concurso-analise.png "$APPDIR/.DirIcon"
{
    cat "$AQUI/concurso-analise.desktop"
    echo "X-AppImage-Version=$VERSAO"
} > "$APPDIR/concurso-analise.desktop"
if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate "$APPDIR/concurso-analise.desktop"
fi
install -m 755 "$AQUI/AppRun" "$APPDIR/AppRun"

FERRAMENTA=build/appimagetool-x86_64.AppImage
if [ ! -x "$FERRAMENTA" ]; then
    curl -fsSLo "$FERRAMENTA" "$APPIMAGETOOL"
    chmod +x "$FERRAMENTA"
fi
SAIDA="dist/concurso-analise-$VERSAO-linux-x86_64.AppImage"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$FERRAMENTA" --no-appstream "$APPDIR" "$SAIDA"
echo "AppImage em $SAIDA ($(du -h "$SAIDA" | cut -f1))"
