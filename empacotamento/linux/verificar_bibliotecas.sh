#!/usr/bin/env bash
# Confere que o onedir do Linux não depende de biblioteca que a máquina do usuário pode não ter.
#
# - Tesseract: listado pelo carregador embutido, com as bibliotecas dele; tudo precisa vir de tesseract/lib.
# - O resto (executáveis e .so do PyInstaller): por ldd, com o LD_LIBRARY_PATH que o bootloader usa; fora do
#   bundle, só o que está em bibliotecas_do_sistema.txt.
# Um "not found" falha sempre.
#
# Uso: bash empacotamento/linux/verificar_bibliotecas.sh dist/concurso-analise
set -euo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
ONEDIR=$(readlink -f "$1")
INTERNO="$ONEDIR/_internal"
TESSERACT="$INTERNO/tesseract"
PERMITIDAS=$(grep -v '^#' "$AQUI/bibliotecas_do_sistema.txt" | sed '/^$/d')
falhas=0

falha() {
    echo "erro: $*" >&2
    falhas=$((falhas + 1))
}

if [ -x "$TESSERACT/lib/ld-linux-x86-64.so.2" ]; then
    lista=$("$TESSERACT/lib/ld-linux-x86-64.so.2" --list --library-path "$TESSERACT/lib" "$TESSERACT/libexec/tesseract") \
        || falha "o carregador embutido não listou as bibliotecas do Tesseract"
    while read -r nome _ caminho _; do
        case "$nome" in linux-vdso.so.*) continue ;; esac
        if [ "$caminho" = "not" ]; then
            falha "Tesseract: $nome não encontrada"
        elif [ "$(readlink -f "$(dirname "$caminho")")" != "$(readlink -f "$TESSERACT/lib")" ]; then
            falha "Tesseract: $nome vem de fora do bundle ($caminho)"
        fi
    done <<< "$lista"
    echo "Tesseract: $(grep -c '=>' <<< "$lista") bibliotecas, todas de tesseract/lib"
else
    falha "falta o Tesseract embutido em $TESSERACT"
fi

conferidos=0
while IFS= read -r -d '' arquivo; do
    head -c 4 "$arquivo" 2>/dev/null | grep -q 'ELF' || continue
    conferidos=$((conferidos + 1))
    saida=$(LD_LIBRARY_PATH="$INTERNO" ldd "$arquivo" 2>&1) || continue
    while read -r linha; do
        case "$linha" in
            *'not found'*) falha "${arquivo#"$ONEDIR"/}: ${linha%% *} não encontrada" ;;
            *'=> /'*)
                caminho=$(sed -E 's/.*=> ([^ ]+).*/\1/' <<< "$linha")
                case "$(readlink -f "$caminho")" in "$ONEDIR"/*) continue ;; esac
                nome=$(basename "$caminho")
                grep -qxF "$nome" <<< "$PERMITIDAS" \
                    || falha "${arquivo#"$ONEDIR"/}: $nome vem do sistema ($caminho) e não está em bibliotecas_do_sistema.txt"
                ;;
        esac
    done <<< "$saida"
done < <(find "$ONEDIR" -path "$TESSERACT" -prune -o -type f \( -name '*.so*' -o -perm -u+x \) -print0)

echo "bundle: $conferidos arquivos ELF conferidos por ldd"
if [ "$falhas" -gt 0 ]; then
    echo "$falhas problema(s) de bibliotecas" >&2
    exit 1
fi
echo "bibliotecas: ok"
