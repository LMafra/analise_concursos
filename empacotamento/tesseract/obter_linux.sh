#!/usr/bin/env bash
# Extrai o Tesseract do AppImage do AlexanderP para empacotamento/construcao/tesseract. O AppImage traz a própria
# glibc e o próprio carregador, então o binário roda em qualquer distribuição; bin/tesseract é um script que o
# chama por esse carregador, só com as bibliotecas dele (o LD_LIBRARY_PATH do executável fica de fora).
#
# O modelo é o do tessdata_fast, o mesmo do pacote tesseract-ocr-por do Debian e do Ubuntu.
#
# Uso: bash empacotamento/tesseract/obter_linux.sh
set -euo pipefail

APPIMAGE=${TESSERACT_APPIMAGE:-v5.5.4/tesseract-5.5.4_lept-1.87-x86_64.AppImage}
URL="https://github.com/AlexanderP/tesseract-appimage/releases/download/$APPIMAGE"
MODELO=https://github.com/tesseract-ocr/tessdata_fast/raw/main/por.traineddata
AQUI=$(cd "$(dirname "$0")" && pwd)
DESTINO="$AQUI/../construcao/tesseract"
TEMP=$(mktemp -d)
trap 'rm -rf "$TEMP"' EXIT

curl -fsSLo "$TEMP/tesseract.AppImage" "$URL"
chmod +x "$TEMP/tesseract.AppImage"
(cd "$TEMP" && ./tesseract.AppImage --appimage-extract >/dev/null)
EXTRAIDO="$TEMP/squashfs-root"

rm -rf "$DESTINO"
mkdir -p "$DESTINO/bin" "$DESTINO/libexec" "$DESTINO/tessdata" "$DESTINO/licencas"
cp -a "$EXTRAIDO/usr/lib" "$DESTINO/lib"
cp "$EXTRAIDO/ld-linux-x86-64.so.2" "$DESTINO/lib/"
cp "$EXTRAIDO/usr/bin/tesseract" "$DESTINO/libexec/tesseract"
cp -a "$EXTRAIDO/usr/share/doc/." "$DESTINO/licencas/"

cat > "$DESTINO/bin/tesseract" <<'SCRIPT'
#!/bin/sh
AQUI="$(dirname "$(readlink -f "$0")")"
exec "$AQUI/../lib/ld-linux-x86-64.so.2" --library-path "$AQUI/../lib" "$AQUI/../libexec/tesseract" "$@"
SCRIPT
chmod +x "$DESTINO/bin/tesseract" "$DESTINO/libexec/tesseract" "$DESTINO/lib/ld-linux-x86-64.so.2"

curl -fsSLo "$DESTINO/tessdata/por.traineddata" "$MODELO"

if ! TESSDATA_PREFIX="$DESTINO/tessdata" "$DESTINO/bin/tesseract" --list-langs | grep -qx por; then
    echo "o tesseract extraído não lista o português" >&2
    exit 1
fi
echo "Tesseract em $DESTINO ($(du -sh "$DESTINO" | cut -f1))"
