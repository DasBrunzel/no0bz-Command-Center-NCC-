#ifndef Version
  #define Version "0.6.0"
#endif
#ifndef Stage
  #error Stage must name the prepared installer input directory.
#endif
#ifndef Output
  #error Output must name the installer output directory.
#endif
; A setup built for one server, e.g. for friends, carries its address and
; skips the address page on a new installation.
#ifndef DefaultServerUrl
  #define DefaultServerUrl ""
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

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\uninstall-agent.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: NccAgentCleanup

[UninstallDelete]
Type: files; Name: "{app}\tray-settings.json"
Type: files; Name: "{app}\pairing-url.txt"
Type: files; Name: "{app}\agent-status.json"
Type: files; Name: "{app}\agent-status.json.tmp"
Type: files; Name: "{app}\tray-upgrade.marker"

[Code]
var
  ServerPage: TInputQueryWizardPage;
  SensorPage: TInputOptionWizardPage;
  PawnIoResult: String;
  InstallScriptFailed: Boolean;
  PairingUrl: String;
  PairingCheck: TNewCheckBox;
  PairingEdit: TNewEdit;

function CanLaunchTray(): Boolean;
begin
  { A service-driven update runs Setup as SYSTEM. The existing tray's
    same-session helper restarts it after the upgrade marker disappears. }
  Result := CompareText(GetUserNameString(), 'SYSTEM') <> 0;
end;

function HasExistingConfig(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonappdata}\no0bz\NCC Agent\config\core.env')) or
    FileExists(ExpandConstant('{commonappdata}\no0bz\NCC\config\core.env')) or
    FileExists(ExpandConstant('{commonappdata}\no0bz\NCC\config\agent.env'));
end;

function BuiltInServerUrl(): String;
begin
  { Only a new installation uses the built-in address; an update keeps the
    address the device already uses, because install-agent.ps1 leaves the
    configuration alone when it receives an empty address. }
  if HasExistingConfig() then
    Result := ''
  else
    Result := '{#DefaultServerUrl}';
end;

function ServerUrl(): String;
begin
  if WizardSilent then
    Result := ExpandConstant('{param:SERVERURL|}')
  else
    Result := Trim(ServerPage.Values[0]);
  if Result = '' then
    Result := BuiltInServerUrl();
end;

function PawnIoInstalled(): Boolean;
begin
  { LHM only uses PawnIO when its own setup registered it. }
  Result := RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (PageID = ServerPage.ID) and ('{#DefaultServerUrl}' <> '') then
    Result := True;
  if (PageID = SensorPage.ID) and PawnIoInstalled() then
    Result := True;
end;

procedure InitializeWizard();
begin
  ServerPage := CreateInputQueryPage(wpSelectDir, 'NCC-Server',
    'Verbindung zum NCC-Server',
    'Gib die HTTPS-Adresse oder die Tailscale-Adresse deines NCC-Servers ein. Vorhandene Agent-Konfigurationen bleiben erhalten.');
  ServerPage.Add('Server-URL:', False);
  ServerPage.Values[0] := ExpandConstant('{param:SERVERURL|}');

  SensorPage := CreateInputOptionPage(ServerPage.ID, 'Hardware-Sensoren',
    'CPU-Temperatur, CPU-Leistung und Mainboard-Lüfter',
    'Diese Werte liest NCC über den signierten Treiber PawnIO (Freeware von namazso, pawnio.eu). ' +
    'Setup installiert ihn über winget aus der offiziellen Quelle und akzeptiert dabei dessen Lizenz. ' +
    'Ohne PawnIO fehlen nur diese Werte; alles andere funktioniert.',
    False, False);
  SensorPage.Add('PawnIO installieren (empfohlen)');
  SensorPage.Values[0] := True;

  PairingCheck := TNewCheckBox.Create(WizardForm);
  PairingCheck.Parent := WizardForm.FinishedPage;
  PairingCheck.Caption := 'Gerät jetzt im Browser mit dem NCC-Dashboard koppeln';
  PairingCheck.Checked := True;
  PairingCheck.Visible := False;
  PairingEdit := TNewEdit.Create(WizardForm);
  PairingEdit.Parent := WizardForm.FinishedPage;
  PairingEdit.ReadOnly := True;
  PairingEdit.Visible := False;
end;

function HasMigratedToken(): Boolean;
var
  Lines: TArrayOfString;
  I: Integer;
begin
  { Agents paired before this installer keep their token in core.env. }
  Result := False;
  if LoadStringsFromFile(ExpandConstant('{commonappdata}\no0bz\NCC Agent\config\core.env'), Lines) then
    for I := 0 to GetArrayLength(Lines) - 1 do
      if (Pos('NCC_AGENT_TOKEN=', Trim(Lines[I])) = 1) and (Length(Trim(Lines[I])) > Length('NCC_AGENT_TOKEN=')) then
        Result := True;
end;

procedure ReadPairingUrl();
var
  Url: AnsiString;
begin
  { A device that already holds an agent credential keeps its pairing. }
  PairingUrl := '';
  if FileExists(ExpandConstant('{commonappdata}\no0bz\NCC Agent\data\agent-credential.json')) or HasMigratedToken() then
    Exit;
  if LoadStringFromFile(ExpandConstant('{app}\pairing-url.txt'), Url) then
    PairingUrl := Trim(String(Url));
  { Shell-open only a web address. }
  if (Pos('https://', Lowercase(PairingUrl)) <> 1) and (Pos('http://', Lowercase(PairingUrl)) <> 1) then
    PairingUrl := '';
end;

procedure OpenPairingUrl();
var
  ErrorCode: Integer;
begin
  if (PairingUrl <> '') and CanLaunchTray() then
    ShellExecAsOriginalUser('open', PairingUrl, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure InstallPawnIo();
var
  ResultCode: Integer;
begin
  { winget installs the official, signed PawnIO setup. A failure only costs
    the CPU and mainboard sensors, so it never fails the agent setup. }
  if PawnIoInstalled() then
    Exit;
  Log('Installing PawnIO through winget.');
  if Exec(ExpandConstant('{cmd}'),
    '/C winget install --id namazso.PawnIO --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and PawnIoInstalled() then
    PawnIoResult := 'ok'
  else
  begin
    Log('PawnIO installation failed with exit code ' + IntToStr(ResultCode) + '.');
    PawnIoResult := 'failed';
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and (PawnIoResult = 'failed') and not InstallScriptFailed then
  begin
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
      'PawnIO konnte nicht installiert werden. CPU- und Lüfterwerte fehlen, bis du in einer ' +
      'PowerShell als Administrator "winget install --id namazso.PawnIO -e" ausführst.';
    WizardForm.FinishedLabel.AdjustHeight();
  end;
  if (CurPageID = wpFinished) and (PairingUrl <> '') and not InstallScriptFailed then
  begin
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
      'Das Gerät ist noch nicht mit dem NCC-Server gekoppelt. Öffne diesen Link und melde ' +
      'dich mit deinem NCC-Konto an. Hast du noch keins, registriere dich dort mit deinem ' +
      'Einladungscode. Der Link ist auch später über das Tray-Menü erreichbar.';
    WizardForm.FinishedLabel.AdjustHeight();
    PairingEdit.Text := PairingUrl;
    PairingEdit.Left := WizardForm.FinishedLabel.Left;
    PairingEdit.Width := WizardForm.FinishedLabel.Width;
    PairingEdit.Top := WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height + ScaleY(12);
    PairingEdit.Visible := True;
    PairingCheck.Left := WizardForm.FinishedLabel.Left;
    PairingCheck.Width := WizardForm.FinishedLabel.Width;
    PairingCheck.Height := ScaleY(17);
    PairingCheck.Top := PairingEdit.Top + PairingEdit.Height + ScaleY(12);
    PairingCheck.Visible := True;
  end;
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
  if (CurPageID = wpFinished) and PairingCheck.Visible and PairingCheck.Checked then
    OpenPairingUrl();
end;

function HasSwitch(Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
      Result := True;
end;

procedure RunRequiredScript(Filename, Parameters: String);
var
  ExitCode: Integer;
begin
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -File "' + Filename + '" ' + Parameters,
    '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    InstallScriptFailed := True;
    RaiseException('NCC-Installationsskript konnte nicht gestartet werden.');
  end;
  if ExitCode <> 0 then
  begin
    InstallScriptFailed := True;
    RaiseException('NCC-Installationsskript meldete Fehlercode ' + IntToStr(ExitCode) + '. Siehe Setup-Log.');
  end;
end;

function GetCustomSetupExitCode(): Integer;
begin
  { An exception after ssInstall is only shown (and suppressed in silent
    mode); Setup would otherwise exit 0 after install-agent.ps1 rolled back.
    10 stays clear of Inno Setup's reserved exit codes 1-8. }
  if InstallScriptFailed then
    Result := 10
  else
    Result := 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PreinstallScript: String;
  ServerUrlFile: String;
  TrayResult: Integer;
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
    { The wizard asks; a silent install only with /PAWNIO. A service-driven
      update (SYSTEM) never installs a driver on its own. }
    if CanLaunchTray() and ((not WizardSilent and SensorPage.Values[0]) or (WizardSilent and HasSwitch('/PAWNIO'))) then
      InstallPawnIo();
    { Not a [Run] entry: those run before ssPostInstall, and a new tray would
      restart the stopped service on the old payload before install-agent.ps1
      activates the new one. }
    if CanLaunchTray() then
      ExecAsOriginalUser(ExpandConstant('{app}\NccTray.exe'), '', '', SW_SHOWNORMAL, ewNoWait, TrayResult);
    ReadPairingUrl();
    { Silent installs open no browser unless asked; the wizard offers it on
      its finished page instead. }
    if WizardSilent and HasSwitch('/OPENPAIRING') then
      OpenPairingUrl();
  end;
end;

procedure DeinitializeSetup();
begin
  DeleteFile(ExpandConstant('{app}\tray-upgrade.marker'));
end;
