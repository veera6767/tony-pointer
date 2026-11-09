; Pointer V - Inno Setup Script
; Generates installers/Output/PointerV-Setup-2.0.0.exe

#define MyAppName "Pointer V"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Veera Akash A"
#define MyAppURL "https://github.com/veeraakash/pointer-v"
#define MyAppExeName "PointerV.exe"

[Setup]
AppId={{D37F8E32-5F2A-4B91-8604-A7E36C2F81D5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Pointer V
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=PointerV-Setup-{#MyAppVersion}
SetupIconFile=..\pointer_v\assets\icons\pointer_v.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Global\PointerV_SingleInstance_Mutex
CloseApplications=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "runatstartup"; Description: "Launch Pointer V when Windows starts"; GroupDescription: "Windows Integration:"; Flags: unchecked

[Files]
Source: "..\pointer_v\dist\PointerV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: runatstartup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  Installed: Cardinal;
  ErrorCode: Integer;
begin
  Result := True;
  // Check 64-bit VC++ 2015-2022 Redistributable
  if not RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) or (Installed <> 1) then
  begin
    if MsgBox('Pointer V requires the Visual C++ 2015-2022 x64 Redistributable.' + #13#10#13#10 +
              'It appears to be missing on this system. Would you like to open the official Microsoft download page now?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://aka.ms/vs/17/release/vc_redist.x64.exe', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataPath := ExpandConstant('{userappdata}\PointerV');
    if DirExists(AppDataPath) then
    begin
      if MsgBox('Do you want to delete your custom Pointer V settings and logs?' + #13#10#13#10 +
                AppDataPath, mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
end;

