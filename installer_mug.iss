#define MyAppName "MUG"
#define MyAppVersion "1.3.3"
#define MyAppPublisher "ECOCEL"
#define MyAppExeName "MUG.exe"

[Setup]
AppId={{8C98D87B-4C26-4B59-B7A6-9A5B29F41220}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\MUG
DefaultGroupName=MUG

OutputDir=installer
OutputBaseFilename=MUG_Setup_v{#MyAppVersion}

Compression=lzma
SolidCompression=yes

WizardStyle=modern

SetupIconFile=assets\mug.ico
UninstallDisplayIcon={app}\MUG.exe

ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

DisableProgramGroupPage=yes

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Opções adicionais:"

[Files]
Source: "dist\MUG\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\MUG"; Filename: "{app}\MUG.exe"
Name: "{autodesktop}\MUG"; Filename: "{app}\MUG.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MUG.exe"; Description: "Executar MUG"; Flags: nowait postinstall skipifsilent
