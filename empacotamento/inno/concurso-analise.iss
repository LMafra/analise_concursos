; Instalador do Windows: por usuário (sem pedir administrador), atalho no menu Iniciar e desinstalador.
; Compile depois do PyInstaller, a partir da raiz do repositório:
;   iscc /DVersao=0.6.0b1 /DVersaoNumerica=0.6.0.0 empacotamento\inno\concurso-analise.iss
; Os dados do candidato (a pasta do projeto e ~/.concurso) ficam fora de {app} e sobrevivem à desinstalação.

#ifndef Versao
  #define Versao "0.0.0"
#endif
#ifndef VersaoNumerica
  #define VersaoNumerica "0.0.0.0"
#endif
#define Nome "concurso-analise"
#define Executavel "concurso-analise.exe"
#define Mutex "concurso-analise"
#define WebView2 "Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

[Setup]
AppId={{6F3C2A51-8D0B-4E7A-9C1F-2B5D7E4A9C30}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=LMafra
AppPublisherURL=https://github.com/LMafra/analise_concursos
VersionInfoVersion={#VersaoNumerica}
VersionInfoProductName={#Nome}
VersionInfoProductVersion={#VersaoNumerica}
VersionInfoProductTextVersion={#Versao}
VersionInfoCompany=LMafra
VersionInfoDescription=Instalador do {#Nome}
VersionInfoCopyright=Copyright (c) 2026 LMafra. Licença MIT.
DefaultDirName={localappdata}\Programs\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=concurso-analise-{#Versao}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#Executavel}
UninstallDisplayName={#Nome}
#ifexist "..\icones\concurso-analise.ico"
SetupIconFile=..\icones\concurso-analise.ico
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\{#Nome}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifexist "..\construcao\MicrosoftEdgeWebview2Setup.exe"
  #define ComBootstrapper
Source: "..\construcao\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy
#endif

[Icons]
Name: "{autoprograms}\{#Nome}"; Filename: "{app}\{#Executavel}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; Tasks: atalho

[Run]
Filename: "{app}\{#Executavel}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#Executavel}"; Flags: nowait; Check: DeveReabrir

[Code]
// A atualização pelo app roda este setup com /REABRIR=1 e fecha em seguida; o setup espera o app sumir
// (o mutex que o executável segura) antes de copiar, e o reabre no fim.
function DeveReabrir(): Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

function InitializeSetup(): Boolean;
var
  Tentativas: Integer;
begin
  Tentativas := 0;
  while CheckForMutexes('{#Mutex}') and (Tentativas < 60) do
  begin
    Sleep(500);
    Tentativas := Tentativas + 1;
  end;
  if Tentativas > 0 then
    Log(Format('esperou o concurso-analise fechar por %d ms', [Tentativas * 500]));
  Result := True;
end;

function VersaoValida(Raiz: Integer; Chave: String): Boolean;
var
  Versao: String;
begin
  Result := RegQueryStringValue(Raiz, Chave, 'pv', Versao) and (Versao <> '') and (Versao <> '0.0.0.0');
end;

function WebView2Instalado(): Boolean;
begin
  Result := VersaoValida(HKLM, 'SOFTWARE\WOW6432Node\{#WebView2}')
    or VersaoValida(HKLM, 'SOFTWARE\{#WebView2}')
    or VersaoValida(HKCU, 'Software\{#WebView2}');
end;

function InstalarWebView2(): Boolean;
var
  Codigo: Integer;
begin
  Result := False;
#ifdef ComBootstrapper
  WizardForm.StatusLabel.Caption := 'Instalando o Microsoft Edge WebView2 (componente de janela)...';
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '',
          SW_HIDE, ewWaitUntilTerminated, Codigo) then
    Log(Format('WebView2: bootstrapper terminou com %d', [Codigo]))
  else
    Log(Format('WebView2: bootstrapper não rodou: %s', [SysErrorMessage(Codigo)]));
  Result := WebView2Instalado();
#endif
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Codigo: Integer;
begin
  if (CurStep <> ssPostInstall) or WebView2Instalado() or InstalarWebView2() then
    Exit;
  Log('WebView2 ausente depois do setup: o app abre no navegador, com aviso');
  if not WizardSilent() then
    if MsgBox('Componente de janela indisponível; o app abre no navegador.' + #13#10#13#10 +
              'O concurso-analise abre numa janela própria com o Microsoft Edge WebView2, que não pôde ser ' +
              'instalado agora (sem internet?). Tudo funciona igual no navegador.' + #13#10#13#10 +
              'Abrir a página de download do WebView2 (gratuito, da Microsoft)?',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '',
                SW_SHOWNORMAL, ewNoWait, Codigo);
end;
