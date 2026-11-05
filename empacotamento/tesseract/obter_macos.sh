#!/usr/bin/env bash
# Copia o Tesseract do Homebrew (arm64) para empacotamento/construcao/tesseract, só com as dylibs de que o
# binário depende. O dylibbundler troca os caminhos absolutos do Homebrew por @executable_path/../lib, e tudo é
# assinado de novo ad hoc, porque o macOS arm64 não carrega binário com a assinatura quebrada.
#
# As ferramentas de treino do Tesseract (e o cairo e o pango que elas puxam) ficam de fora: só o binário
# `tesseract` e as dependências dele entram.
#
# O modelo é o do tessdata_fast, o mesmo do pacote tesseract-ocr-por do Debian e do Ubuntu.
#
# Uso: bash empacotamento/tesseract/obter_macos.sh
set -euo pipefail

MODELO=https://github.com/tesseract-ocr/tessdata_fast/raw/main/por.traineddata
AQUI=$(cd "$(dirname "$0")" && pwd)
DESTINO="$AQUI/../construcao/tesseract"

brew list tesseract >/dev/null 2>&1 || brew install tesseract
brew list dylibbundler >/dev/null 2>&1 || brew install dylibbundler
PREFIXO=$(brew --prefix tesseract)

rm -rf "$DESTINO"
mkdir -p "$DESTINO/bin" "$DESTINO/lib" "$DESTINO/tessdata" "$DESTINO/licencas"
cp "$PREFIXO/bin/tesseract" "$DESTINO/bin/tesseract"
chmod u+w "$DESTINO/bin/tesseract"

dylibbundler --overwrite-dir --bundle-deps \
    --fix-file "$DESTINO/bin/tesseract" \
    --dest-dir "$DESTINO/lib" \
    --install-path @executable_path/../lib/

codesign --force --sign - "$DESTINO"/lib/*.dylib "$DESTINO/bin/tesseract"

if otool -L "$DESTINO/bin/tesseract" "$DESTINO"/lib/*.dylib | grep -E '/(opt/homebrew|usr/local)/'; then
    echo "sobrou caminho absoluto do Homebrew nas bibliotecas acima" >&2
    exit 1
fi

for formula in tesseract $(brew deps --installed tesseract); do
    pasta=$(brew --prefix "$formula")
    for licenca in "$pasta"/LICENSE* "$pasta"/COPYING* "$pasta"/NOTICE*; do
        if [ -f "$licenca" ]; then
            mkdir -p "$DESTINO/licencas/$formula"
            cp "$licenca" "$DESTINO/licencas/$formula/"
        fi
    done
done

curl -fsSLo "$DESTINO/tessdata/por.traineddata" "$MODELO"

if ! env -i PATH=/usr/bin:/bin TESSDATA_PREFIX="$DESTINO/tessdata" "$DESTINO/bin/tesseract" --list-langs | grep -qx por; then
    echo "o tesseract copiado não lista o português" >&2
    exit 1
fi
echo "Tesseract em $DESTINO ($(du -sh "$DESTINO" | cut -f1))"
