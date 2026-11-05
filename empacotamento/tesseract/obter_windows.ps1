# Copia o Tesseract do MSYS2 (mingw64) para empacotamento/construcao/tesseract: o tesseract.exe, as DLLs de que
# ele depende (pelo ldd do MSYS2), o por.traineddata do tessdata_fast e as licenças.
#
# O modelo é o do tessdata_fast, o mesmo do pacote tesseract-ocr-por do Debian e do Ubuntu, para o OCR do
# executável dar o mesmo texto que o da imagem Docker e o das instalações com apt.
#
# Uso: pwsh empacotamento/tesseract/obter_windows.ps1 [-Msys C:\msys64]
param(
    [string]$Msys = 'C:\msys64'
)
$ErrorActionPreference = 'Stop'

$Modelo = 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/por.traineddata'
$Destino = Join-Path $PSScriptRoot '..\construcao\tesseract'
$Bash = Join-Path $Msys 'usr\bin\bash.exe'
$Mingw = Join-Path $Msys 'mingw64\bin'

if (-not (Test-Path $Bash)) { throw "MSYS2 não encontrado em $Msys" }
$env:MSYSTEM = 'MINGW64'
$env:CHERE_INVOKING = '1'

& $Bash -lc 'pacman -S --noconfirm --needed mingw-w64-x86_64-tesseract-ocr'
if ($LASTEXITCODE -ne 0) { throw 'pacman não instalou o tesseract' }

if (Test-Path $Destino) { Remove-Item -Recurse -Force $Destino }
$Bin = New-Item -ItemType Directory -Force (Join-Path $Destino 'bin')
$Tessdata = New-Item -ItemType Directory -Force (Join-Path $Destino 'tessdata')
$Licencas = New-Item -ItemType Directory -Force (Join-Path $Destino 'licencas')

Copy-Item (Join-Path $Mingw 'tesseract.exe') $Bin

# Só as DLLs do mingw64; as do Windows (system32) já estão em qualquer máquina.
$Dlls = & $Bash -lc "ldd /mingw64/bin/tesseract.exe | awk '/\/mingw64\/bin\// {print `$3}'"
if ($LASTEXITCODE -ne 0 -or -not $Dlls) { throw 'ldd não listou as DLLs do tesseract' }
foreach ($Dll in $Dlls) {
    Copy-Item (Join-Path $Mingw (Split-Path $Dll -Leaf)) $Bin
}

Invoke-WebRequest $Modelo -OutFile (Join-Path $Tessdata 'por.traineddata')

$Pacotes = & $Bash -lc "pactree -u mingw-w64-x86_64-tesseract-ocr"
foreach ($Pacote in $Pacotes) {
    $Pasta = Join-Path $Msys "mingw64\share\licenses\$($Pacote -replace '^mingw-w64-x86_64-', '')"
    if (Test-Path $Pasta) {
        Copy-Item -Recurse $Pasta (Join-Path $Licencas (Split-Path $Pasta -Leaf))
    }
}

$env:TESSDATA_PREFIX = $Tessdata
$Idiomas = & (Join-Path $Bin 'tesseract.exe') --list-langs
if ($Idiomas -notcontains 'por') { throw "o tesseract copiado não lista o português: $Idiomas" }
$Tamanho = (Get-ChildItem -Recurse $Destino | Measure-Object -Sum Length).Sum / 1MB
Write-Host ("Tesseract em {0} ({1:N0} MB, {2} DLLs)" -f $Destino, $Tamanho, $Dlls.Count)
