; Instalador do Windows: por usuário (sem pedir administrador), atalho no menu Iniciar e desinstalador.
; Compile depois do PyInstaller, a partir da raiz do repositório:
;   iscc /DVersao=0.5.0 empacotamento\inno\concurso-analise.iss
; Os dados do candidato (a pasta do projeto e ~/.concurso) ficam fora de {app} e sobrevivem à desinstalação.

#ifndef Versao
  #define Versao "0.0.0"
#endif
#define Nome "concurso-analise"
#define Executavel "concurso-analise.exe"
#define WebView2 "Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

[Setup]
AppId={{6F3C2A51-8D0B-4E7A-9C1F-2B5D7E4A9C30}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=LMafra
AppPublisherURL=https://github.com/LMafra/analise_concursos
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

[Icons]
Name: "{autoprograms}\{#Nome}"; Filename: "{app}\{#Executavel}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; Tasks: atalho

[Run]
Filename: "{app}\{#Executavel}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent

[Code]
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

procedure CurStepChanged(CurStep: TSetupStep);
var
  Codigo: Integer;
begin
  if (CurStep = ssPostInstall) and not WebView2Instalado() and not WizardSilent() then
    if MsgBox('O concurso-analise abre numa janela própria com o Microsoft Edge WebView2, que não está ' +
              'instalado neste computador. Sem ele, o programa abre no seu navegador.' + #13#10#13#10 +
              'Abrir a página de download do WebView2 (gratuito, da Microsoft)?',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '',
                SW_SHOWNORMAL, ewNoWait, Codigo);
end;
