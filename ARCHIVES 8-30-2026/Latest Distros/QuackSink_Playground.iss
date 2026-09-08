#define MyAppName "QuackSink Playground"
#define MyAppVersion "Current"
#define MyPublisher "Cozmo / QuackSink"
#define MyInstallDir "QuackSink"

[Setup]
AppId={{B7C4E6A1-7D2D-4A8D-9B7F-QUACKSINKPLAY}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}

DefaultDirName=C:\QuackSink
DefaultGroupName={#MyAppName}

PrivilegesRequired=lowest

OutputDir=.
OutputBaseFilename=QuackSink_Playground_Installer

Compression=lzma
SolidCompression=yes

Uninstallable=yes
UninstallDisplayName={#MyAppName}

WizardStyle=modern

[Files]
Source: "QuackSink\*"; DestDir: "{app}\QuackSink"; Flags: recursesubdirs createallsubdirs
Source: "QuackSinkLauncher\*"; DestDir: "{app}\QuackSinkLauncher"; Flags: recursesubdirs createallsubdirs

[Run]
Filename: "{app}\QuackSinkLauncher\QuackSinkLauncher.exe"; Description: "Launch QuackSpace Launcher"; Flags: postinstall nowait skipifsilent