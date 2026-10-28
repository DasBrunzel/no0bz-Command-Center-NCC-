#ifndef Version
  #define Version "0.6.0-beta.8-dev.1"
#endif
#ifndef Stage
  #error Stage must name the prepared installer input directory.
#endif
#ifndef Output
  #error Output must name the installer output directory.
#endif

[Setup]
AppId={{F038C97B-C4C6-44D7-83E4-49198FE47CB8}
AppName=no0bz Command Center Agent
AppVersion={#Version}
AppPublisher=no0bz
DefaultDirName={autopf}\no0bz\NCC Agent
DefaultGroupName=no0bz Command Center
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir={#Output}
OutputBaseFilename=ncc-agent-setup-{#Version}-windows-x86_64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NccTray.exe
CloseApplications=force
RestartApplications=yes
SetupLogging=yes

[Files]
Source: "{#Stage}\NccTray.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\NccServiceHost.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\ncc-core.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\initial-payload.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\initial-payload.manifest.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\trusted-keys.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\installer-version.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\installer-feed-url.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\install-agent.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\uninstall-agent.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Stage}\preinstall-agent.ps1"; Flags: dontcopy

[Registry]
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NccTray"; ValueData: """{app}\NccTray.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\NccTray.exe"; Description: "NCC Agent im Infobereich starten"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall-agent.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: NccAgentCleanup

[Code]
var
  ServerPage: TInputQueryWizardPage;

function ServerUrl(): String;
begin
  if WizardSilent then
    Result := ExpandConstant('{param:SERVERURL|}')
  else
    Result := Trim(ServerPage.Values[0]);
end;

procedure InitializeWizard();
begin
  ServerPage := CreateInputQueryPage(wpSelectDir, 'NCC-Server',
    'Verbindung zum NCC-Server',
    'Gib die HTTPS-Adresse oder die Tailscale-Adresse deines NCC-Servers ein. Vorhandene Agent-Konfigurationen bleiben erhalten.');
  ServerPage.Add('Server-URL:', False);
  ServerPage.Values[0] := ExpandConstant('{param:SERVERURL|}');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Url: String;
begin
  Result := True;
  if CurPageID = ServerPage.ID then
  begin
    Url := ServerUrl();
    if (Url = '') and
       (not FileExists(ExpandConstant('{commonappdata}\no0bz\NCC Agent\config\core.env'))) and
       (not FileExists(ExpandConstant('{commonappdata}\no0bz\NCC\config\core.env'))) and
       (not FileExists(ExpandConstant('{commonappdata}\no0bz\NCC\config\agent.env'))) then
    begin
      MsgBox('Für eine neue Installation ist die NCC-Server-Adresse erforderlich.', mbError, MB_OK);
      Result := False;
    end;
    if (Url <> '') and (Pos('https://', Lowercase(Url)) <> 1) and
       (Pos('http://', Lowercase(Url)) <> 1) then
    begin
      MsgBox('Die NCC-Server-Adresse muss mit https:// oder einer vertrauten Tailscale-http://-Adresse beginnen.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure RunRequiredScript(Filename, Parameters: String);
var
  ExitCode: Integer;
begin
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -File "' + Filename + '" ' + Parameters,
    '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    RaiseException('NCC-Installationsskript konnte nicht gestartet werden.');
  if ExitCode <> 0 then
    RaiseException('NCC-Installationsskript meldete Fehlercode ' + IntToStr(ExitCode) + '. Siehe Setup-Log.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PreinstallScript: String;
  ServerUrlFile: String;
begin
  if CurStep = ssInstall then
  begin
    ExtractTemporaryFile('preinstall-agent.ps1');
    PreinstallScript := ExpandConstant('{tmp}\preinstall-agent.ps1');
    RunRequiredScript(PreinstallScript, '-AppDir "' + ExpandConstant('{app}') + '"');
  end;
  if CurStep = ssPostInstall then
  begin
    ServerUrlFile := ExpandConstant('{tmp}\ncc-server-url.txt');
    if not SaveStringToFile(ServerUrlFile, ServerUrl(), False) then
      RaiseException('NCC-Server-Adresse konnte nicht vorbereitet werden.');
    RunRequiredScript(ExpandConstant('{app}\install-agent.ps1'),
      '-AppDir "' + ExpandConstant('{app}') + '" -ServerUrlFile "' + ServerUrlFile + '"');
  end;
end;
