# Gate de máquina limpa do instalador do Windows: instala em silêncio, tira Python e Tesseract do PATH, roda o
# smoke do executável (versão, perfis, Tesseract embutido com português, GUI em 127.0.0.1, doctor e a análise
# de dois concursos com idempotência) e desinstala.
#
# Uso: pwsh scripts/smoke_maquina_limpa.ps1 -Instalador dist\concurso-analise-0.5.0-windows-x64-setup.exe
#
# No CI, roda no próprio runner. Antes de publicar uma release, rode também no Windows Sandbox (ou numa VM sem
# Python nem Tesseract) e siga o checklist de docs/spec-fase5.md.
param(
    [Parameter(Mandatory = $true)][string]$Instalador
)
$ErrorActionPreference = 'Stop'

$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
$Smoke = Join-Path $PSScriptRoot 'smoke.py'
$Destino = Join-Path ([IO.Path]::GetTempPath()) 'concurso-analise-maquina-limpa'
if (Test-Path $Destino) { Remove-Item -Recurse -Force $Destino }

$Instalacao = Start-Process -FilePath $Instalador -Wait -PassThru -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', "/DIR=`"$Destino`""
)
if ($Instalacao.ExitCode -ne 0) { throw "o instalador saiu com código $($Instalacao.ExitCode)" }
$Janela = Join-Path $Destino 'concurso-analise.exe'
$Cli = Join-Path $Destino 'concurso-analise-cli.exe'
foreach ($Arquivo in @($Janela, $Cli, (Join-Path $Destino 'unins000.exe'))) {
    if (-not (Test-Path $Arquivo)) { throw "$Arquivo não foi instalado" }
}
$Atalho = Join-Path ([Environment]::GetFolderPath('Programs')) 'concurso-analise.lnk'
if (-not (Test-Path $Atalho)) { throw "o atalho do menu Iniciar não foi criado em $Atalho" }

$PathOriginal = $env:PATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
foreach ($Variavel in 'PYTHONHOME', 'PYTHONPATH', 'TESSDATA_PREFIX', 'CONCURSO_SMOKE_SEM_OCR') {
    Remove-Item "Env:$Variavel" -ErrorAction SilentlyContinue
}
try {
    foreach ($Programa in 'python', 'python3', 'tesseract', 'uv') {
        if (Get-Command $Programa -ErrorAction SilentlyContinue) { throw "$Programa ainda está no PATH limpo" }
    }

    $Gui = Start-Process -FilePath $Janela -ArgumentList '--smoke' -Wait -PassThru
    if ($Gui.ExitCode -ne 0) { throw "o executável da janela saiu com código $($Gui.ExitCode) no --smoke" }

    if (-not $Python) { throw 'sem Python no runner para conduzir scripts/smoke.py' }
    & $Python $Smoke congelado $Cli
    if ($LASTEXITCODE -ne 0) { throw 'scripts/smoke.py congelado falhou' }
}
finally {
    $env:PATH = $PathOriginal
}

$Desinstalacao = Start-Process -FilePath (Join-Path $Destino 'unins000.exe') -Wait -PassThru -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
)
if ($Desinstalacao.ExitCode -ne 0) { throw "o desinstalador saiu com código $($Desinstalacao.ExitCode)" }
Start-Sleep -Seconds 3
if (Test-Path $Janela) { throw 'a desinstalação deixou o executável' }
if (Test-Path $Atalho) { throw 'a desinstalação deixou o atalho do menu Iniciar' }
Write-Host 'máquina limpa: ok'
