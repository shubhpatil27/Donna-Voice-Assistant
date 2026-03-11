; DonnaInstaller.iss

[Setup]
AppName=Donna
AppVersion=1.0
DefaultDirName={localappdata}\Donna
DefaultGroupName=Donna
OutputDir=installer_output
OutputBaseFilename=DonnaInstaller
Compression=lzma
SolidCompression=yes

; Fix warnings:
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

SetupIconFile=installer_files\donna_icon.ico
UninstallDisplayIcon={app}\donna_app.exe

[Files]
Source: "installer_files\donna_app.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_files\donna_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_files\donna.jpg"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\installer_files\donna.jpg'))

[Icons]
; Start Menu shortcut
Name: "{group}\Donna"; Filename: "{app}\donna_app.exe"; IconFilename: "{app}\donna_icon.ico"
; Desktop shortcut for the installing user
Name: "{userdesktop}\Donna"; Filename: "{app}\donna_app.exe"; IconFilename: "{app}\donna_icon.ico"

[Run]
Filename: "{app}\donna_app.exe"; Description: "Run Donna now"; Flags: nowait postinstall skipifsilent
