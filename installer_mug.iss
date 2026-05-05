#define MyAppName "MUG"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "ECOCEL"
#define MyAppExeName "MUG.exe"

[Setup]
AppId={{B8E0C4C9-3A44-4B9B-9D24-MUG100000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=MUG_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Opções adicionais:"; Flags: unchecked

[Files]
Source: "dist\MUG\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MUG"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\MUG"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar MUG"; Flags: nowait postinstall skipifsilent