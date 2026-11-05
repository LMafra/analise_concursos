#!/usr/bin/env bash
# Assina ad hoc o dist/concurso-analise.app (sem conta de desenvolvedor: o usuário abre com "Abrir Mesmo
# Assim" na primeira vez) e monta dist/concurso-analise-<versão>-macos-arm64.dmg com o atalho para Aplicativos.
#
# Uso: bash empacotamento/macos/criar_dmg.sh <versão>
set -euo pipefail

VERSAO=$1
RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
cd "$RAIZ"

APP=dist/concurso-analise.app
SAIDA="dist/concurso-analise-$VERSAO-macos-arm64.dmg"

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

brew list create-dmg >/dev/null 2>&1 || brew install create-dmg
PALCO=build/dmg
rm -rf "$PALCO" "$SAIDA"
mkdir -p "$PALCO"
cp -R "$APP" "$PALCO/"
# --skip-jenkins: sem o AppleScript do Finder, que trava em runner sem sessão gráfica.
create-dmg \
    --volname "concurso-analise $VERSAO" \
    --volicon empacotamento/icones/concurso-analise.icns \
    --app-drop-link 400 180 \
    --skip-jenkins \
    "$SAIDA" "$PALCO"
echo "DMG em $SAIDA ($(du -h "$SAIDA" | cut -f1))"
