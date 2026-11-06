# Baixa o bootstrapper do Microsoft Edge WebView2 para o instalador embutir.
# Rode da raiz do repositório, antes do iscc:
#   .\empacotamento\windows\obter_webview2.ps1
# O bootstrapper (~2 MB) baixa o runtime na máquina do usuário; só é executado quando o WebView2 falta.
param(
    [string]$Destino = 'empacotamento\construcao\MicrosoftEdgeWebview2Setup.exe'
)

$ErrorActionPreference = 'Stop'
$url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'

New-Item -ItemType Directory -Force -Path (Split-Path $Destino) | Out-Null
Invoke-WebRequest -Uri $url -OutFile $Destino -UseBasicParsing

$assinatura = Get-AuthenticodeSignature $Destino
if ($assinatura.Status -ne 'Valid') {
    throw "o bootstrapper do WebView2 não tem assinatura válida: $($assinatura.Status)"
}
if ($assinatura.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw "o bootstrapper do WebView2 não é assinado pela Microsoft: $($assinatura.SignerCertificate.Subject)"
}
Write-Host "WebView2: bootstrapper em $Destino, assinado por $($assinatura.SignerCertificate.Subject)"
