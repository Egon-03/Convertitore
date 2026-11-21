; Installazione di ConvertiTutto (Inno Setup 6)

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8C5E2F4A-3B7D-4E61-9A1C-C0E7A1B2D3F4}
AppName=ConvertiTutto
AppVersion={#AppVersion}
AppPublisher=ConvertiTutto
DefaultDirName={autopf}\ConvertiTutto
DefaultGroupName=ConvertiTutto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=ConvertiTutto-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\ConvertiTutto.exe
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
DiskSpanning=no

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "contextmenu"; Description: "Aggiungi ""Converti con ConvertiTutto"" al menu del tasto destro"; GroupDescription: "Integrazione con Windows:"
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; GroupDescription: "Icone:"

[Files]
Source: "..\dist\ConvertiTutto\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ConvertiTutto"; Filename: "{app}\ConvertiTutto.exe"
Name: "{autodesktop}\ConvertiTutto"; Filename: "{app}\ConvertiTutto.exe"; Tasks: desktopicon

[Registry]
; menu del tasto destro su qualsiasi file
Root: HKA; Subkey: "Software\Classes\*\shell\ConvertiTutto"; ValueType: string; ValueName: ""; ValueData: "Converti con ConvertiTutto"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\*\shell\ConvertiTutto"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\ConvertiTutto.exe"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\*\shell\ConvertiTutto"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\*\shell\ConvertiTutto\command"; ValueType: string; ValueName: ""; ValueData: """{app}\ConvertiTutto.exe"" ""%1"""; Tasks: contextmenu
; e sulle cartelle (per comprimerle)
Root: HKA; Subkey: "Software\Classes\Directory\shell\ConvertiTutto"; ValueType: string; ValueName: ""; ValueData: "Converti con ConvertiTutto"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Directory\shell\ConvertiTutto"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\ConvertiTutto.exe"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\ConvertiTutto\command"; ValueType: string; ValueName: ""; ValueData: """{app}\ConvertiTutto.exe"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\ConvertiTutto.exe"; Description: "Avvia ConvertiTutto"; Flags: nowait postinstall skipifsilent
