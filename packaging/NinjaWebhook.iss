; NinjaWebhook full installer (Inno Setup 6)
; Built by scripts\pack-release.ps1 — do not run against missing release files.

#define MyAppName "NinjaWebhook"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "NinjaWebhook"
#define MyAppExeName "WebhookReceiver.exe"
#define MyAddOnZip "WebhookTradeListener-AddOn.zip"

[Setup]
AppId={{8F3C2A91-4B7E-4D12-9C55-A1B2C3D4E5F6}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=NinjaWebhook-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
InfoAfterFile=postinstall.txt
SetupIconFile=..\webhook_receiver\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start receiver with Windows (system tray)"; GroupDescription: "Startup"; Flags: checkedonce

[Files]
; Receiver EXE (built by pack-release.ps1 into release\)
Source: "..\release\WebhookReceiver.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\release\{#MyAddOnZip}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\packaging\DISTRIBUTION.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\FLOW_TRADING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\OPTIONS_TRADING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-ngrok-tunnel.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "postinstall.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\webhook_receiver\config.defaults.json"; Flags: dontcopy

[Icons]
Name: "{group}\{#MyAppName} Receiver"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Install folder"; Filename: "{app}"
Name: "{group}\Distribution guide"; Filename: "{app}\DISTRIBUTION.md"
Name: "{group}\Flow signal setup"; Filename: "{app}\FLOW_TRADING.md"
Name: "{group}\Options forwarding setup"; Filename: "{app}\OPTIONS_TRADING.md"
Name: "{autodesktop}\{#MyAppName} Receiver"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autodesktop}\WebhookTradeListener-AddOn.zip"; Filename: "{app}\{#MyAddOnZip}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName} Receiver"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch receiver (system tray)"; Flags: nowait postinstall skipifsilent
Filename: "{app}"; Description: "Open install folder (import the Add-On zip in NinjaTrader)"; Flags: shellexec postinstall skipifsilent unchecked

[Code]
const
  DefaultListenPort = '5088';
  DefaultNtTcpPort = '7077';

var
  ListenPage: TInputQueryWizardPage;
  DiscordPage: TInputQueryWizardPage;
  OptionsPage: TInputQueryWizardPage;

function EscapeJsonString(const Value: String): String;
var
  I: Integer;
  Ch: Char;
  OutText: String;
begin
  OutText := '';
  for I := 1 to Length(Value) do
  begin
    Ch := Value[I];
    if Ch = '\' then
      OutText := OutText + '\\'
    else if Ch = '"' then
      OutText := OutText + '\"'
    else if Ord(Ch) = 8 then
      OutText := OutText + '\b'
    else if Ord(Ch) = 9 then
      OutText := OutText + '\t'
    else if Ord(Ch) = 10 then
      OutText := OutText + '\n'
    else if Ord(Ch) = 12 then
      OutText := OutText + '\f'
    else if Ord(Ch) = 13 then
      OutText := OutText + '\r'
    else
      OutText := OutText + Ch;
  end;
  Result := OutText;
end;

function UnescapeJsonString(const Value: String): String;
var
  I: Integer;
  OutText: String;
begin
  OutText := '';
  I := 1;
  while I <= Length(Value) do
  begin
    if (Value[I] = '\') and (I < Length(Value)) then
    begin
      Inc(I);
      case Value[I] of
        '\': OutText := OutText + '\';
        '"': OutText := OutText + '"';
        'b': OutText := OutText + Chr(8);
        't': OutText := OutText + Chr(9);
        'n': OutText := OutText + Chr(10);
        'f': OutText := OutText + Chr(12);
        'r': OutText := OutText + Chr(13);
      else
        OutText := OutText + Value[I];
      end;
    end
    else
      OutText := OutText + Value[I];
    Inc(I);
  end;
  Result := OutText;
end;

function StripBom(const Value: String): String;
begin
  Result := Value;
  while (Length(Result) > 0) and
        ((Ord(Result[1]) = 65279) or (Ord(Result[1]) = 239) or
         (Ord(Result[1]) = 187) or (Ord(Result[1]) = 191)) do
    Result := Copy(Result, 2, MaxInt);
end;

function ReadJsonStringField(const JsonText, FieldName: String): String;
var
  Marker: String;
  StartPos, ValueStart, ValueEnd: Integer;
  Raw: String;
begin
  Result := '';
  Marker := '"' + FieldName + '"';
  StartPos := Pos(Marker, JsonText);
  if StartPos = 0 then
    Exit;

  ValueStart := StartPos + Length(Marker);
  while (ValueStart <= Length(JsonText)) and (JsonText[ValueStart] <> '"') do
  begin
    { Skip null values like "field": null }
    if (JsonText[ValueStart] = 'n') and
       (Copy(JsonText, ValueStart, 4) = 'null') then
      Exit;
    ValueStart := ValueStart + 1;
  end;
  if ValueStart > Length(JsonText) then
    Exit;

  ValueEnd := ValueStart + 1;
  while ValueEnd <= Length(JsonText) do
  begin
    if (JsonText[ValueEnd] = '\') and (ValueEnd < Length(JsonText)) then
      ValueEnd := ValueEnd + 2
    else if JsonText[ValueEnd] = '"' then
      Break
    else
      ValueEnd := ValueEnd + 1;
  end;
  if ValueEnd > Length(JsonText) then
    Exit;

  Raw := Copy(JsonText, ValueStart + 1, ValueEnd - ValueStart - 1);
  Result := UnescapeJsonString(Raw);
end;

function ReadRootListenPort(const JsonText: String): String;
var
  Marker: String;
  StartPos, I: Integer;
  Digits: String;
begin
  Result := '';
  Marker := #10 + '  "port":';
  StartPos := Pos(Marker, JsonText);
  if StartPos = 0 then
    Exit;

  I := StartPos + Length(Marker);
  while (I <= Length(JsonText)) and (JsonText[I] = ' ') do
    I := I + 1;
  if (I <= Length(JsonText)) and (JsonText[I] = '"') then
    I := I + 1;

  Digits := '';
  while (I <= Length(JsonText)) and (JsonText[I] >= '0') and (JsonText[I] <= '9') do
  begin
    Digits := Digits + JsonText[I];
    I := I + 1;
  end;
  Result := Digits;
end;

function ReplaceRootListenPort(const JsonText, PortText: String): String;
var
  Marker: String;
  StartPos, ValueStart, ValueEnd: Integer;
begin
  Marker := #10 + '  "port":';
  StartPos := Pos(Marker, JsonText);
  if StartPos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  ValueStart := StartPos + Length(Marker);
  while (ValueStart <= Length(JsonText)) and
        ((JsonText[ValueStart] = ' ') or (JsonText[ValueStart] = '"')) do
    ValueStart := ValueStart + 1;

  ValueEnd := ValueStart;
  while (ValueEnd <= Length(JsonText)) and
        (JsonText[ValueEnd] >= '0') and (JsonText[ValueEnd] <= '9') do
    ValueEnd := ValueEnd + 1;

  Result :=
    Copy(JsonText, 1, ValueStart - 1) +
    PortText +
    Copy(JsonText, ValueEnd, MaxInt);
end;

function NormalizedPort(const Value, DefaultPort: String): String;
var
  PortNumber: Integer;
begin
  Result := Trim(Value);
  if Result = '' then
    Result := DefaultPort;
  PortNumber := StrToIntDef(Result, -1);
  if (PortNumber < 1) or (PortNumber > 65535) then
    Result := '';
end;

function ReadObjectPort(const JsonText, ObjectName: String): String;
var
  SectionPos, RelPos, I: Integer;
  Section: String;
  Digits: String;
begin
  Result := '';
  SectionPos := Pos('"' + ObjectName + '"', JsonText);
  if SectionPos = 0 then
    Exit;

  Section := Copy(JsonText, SectionPos, MaxInt);
  RelPos := Pos('"port":', Section);
  if RelPos = 0 then
    Exit;

  I := SectionPos + RelPos - 1 + Length('"port":');
  while (I <= Length(JsonText)) and (JsonText[I] = ' ') do
    I := I + 1;
  if (I <= Length(JsonText)) and (JsonText[I] = '"') then
    I := I + 1;

  Digits := '';
  while (I <= Length(JsonText)) and (JsonText[I] >= '0') and (JsonText[I] <= '9') do
  begin
    Digits := Digits + JsonText[I];
    I := I + 1;
  end;
  Result := Digits;
end;

function ReplaceObjectPort(const JsonText, ObjectName, PortText: String): String;
var
  SectionPos, RelPos, ValueStart, ValueEnd: Integer;
  Section: String;
begin
  SectionPos := Pos('"' + ObjectName + '"', JsonText);
  if SectionPos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  Section := Copy(JsonText, SectionPos, MaxInt);
  RelPos := Pos('"port":', Section);
  if RelPos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  ValueStart := SectionPos + RelPos - 1 + Length('"port":');
  while (ValueStart <= Length(JsonText)) and
        ((JsonText[ValueStart] = ' ') or (JsonText[ValueStart] = '"')) do
    ValueStart := ValueStart + 1;

  ValueEnd := ValueStart;
  while (ValueEnd <= Length(JsonText)) and
        (JsonText[ValueEnd] >= '0') and (JsonText[ValueEnd] <= '9') do
    ValueEnd := ValueEnd + 1;

  Result :=
    Copy(JsonText, 1, ValueStart - 1) +
    PortText +
    Copy(JsonText, ValueEnd, MaxInt);
end;

function ExistingConfigPath: String;
var
  Candidate: String;
begin
  // Never expand the app constant before install path is ready (InitializeWizard).
  Result := '';

  if WizardForm <> nil then
  begin
    Candidate := AddBackslash(WizardForm.DirEdit.Text) + 'config.json';
    if FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;

  Candidate := ExpandConstant('{localappdata}\Programs\{#MyAppName}\config.json');
  if FileExists(Candidate) then
    Result := Candidate;
end;

procedure PrefillWizardFromExistingConfig;
var
  ConfigPath: String;
  JsonText: AnsiString;
  Text: String;
  DiscordUrl, OptionsUrl, OptionsKey, ListenPort, NtTcpPort: String;
begin
  ConfigPath := ExistingConfigPath;
  if ConfigPath = '' then
    Exit;
  if not LoadStringFromFile(ConfigPath, JsonText) then
    Exit;

  Text := StripBom(String(JsonText));
  DiscordUrl := Trim(ReadJsonStringField(Text, 'discord_webhook_url'));
  OptionsUrl := Trim(ReadJsonStringField(Text, 'webhook_url'));
  OptionsKey := Trim(ReadJsonStringField(Text, 'api_key'));
  ListenPort := Trim(ReadRootListenPort(Text));
  NtTcpPort := Trim(ReadObjectPort(Text, 'tcp'));

  if (ListenPage <> nil) and
     ((Trim(ListenPage.Values[0]) = '') or
      (Trim(ListenPage.Values[0]) = DefaultListenPort)) and
     (ListenPort <> '') then
    ListenPage.Values[0] := ListenPort;

  if (ListenPage <> nil) and
     ((Trim(ListenPage.Values[1]) = '') or
      (Trim(ListenPage.Values[1]) = DefaultNtTcpPort)) and
     (NtTcpPort <> '') then
    ListenPage.Values[1] := NtTcpPort;

  if (DiscordPage <> nil) and (Trim(DiscordPage.Values[0]) = '') and (DiscordUrl <> '') then
    DiscordPage.Values[0] := DiscordUrl;

  if OptionsPage <> nil then
  begin
    if (Trim(OptionsPage.Values[0]) = '') and (OptionsUrl <> '') then
      OptionsPage.Values[0] := OptionsUrl;
    if (Trim(OptionsPage.Values[1]) = '') and (OptionsKey <> '') then
      OptionsPage.Values[1] := OptionsKey;
  end;
end;

function InsertFlowSection(const JsonText, WebhookUrl: String): String;
var
  BracePos: Integer;
begin
  BracePos := Pos('{', JsonText);
  if BracePos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  Result :=
    Copy(JsonText, 1, BracePos) +
    Chr(13) + Chr(10) +
    '  "flow": { "discord_webhook_url": "' + EscapeJsonString(WebhookUrl) + '" },' +
    Copy(JsonText, BracePos + 1, MaxInt);
end;

function ReplaceDiscordWebhook(const JsonText, WebhookUrl: String): String;
var
  Marker: String;
  StartPos, ValueStart, ValueEnd: Integer;
  Quote: Char;
begin
  Marker := '"discord_webhook_url"';
  StartPos := Pos(Marker, JsonText);
  if StartPos = 0 then
  begin
    Result := InsertFlowSection(JsonText, WebhookUrl);
    Exit;
  end;

  ValueStart := StartPos + Length(Marker);
  while (ValueStart <= Length(JsonText)) and (JsonText[ValueStart] <> '"') do
    ValueStart := ValueStart + 1;

  if ValueStart > Length(JsonText) then
  begin
    Result := JsonText;
    Exit;
  end;

  Quote := '"';
  ValueEnd := ValueStart + 1;
  while ValueEnd <= Length(JsonText) do
  begin
    if (JsonText[ValueEnd] = '\') and (ValueEnd < Length(JsonText)) then
      ValueEnd := ValueEnd + 2
    else if JsonText[ValueEnd] = Quote then
      Break
    else
      ValueEnd := ValueEnd + 1;
  end;

  if ValueEnd > Length(JsonText) then
  begin
    Result := JsonText;
    Exit;
  end;

  Result :=
    Copy(JsonText, 1, ValueStart) +
    EscapeJsonString(WebhookUrl) +
    Copy(JsonText, ValueEnd, MaxInt);
end;

function InsertOptionsSection(
  const JsonText, OptionsUrl, ApiKey: String
): String;
var
  BracePos: Integer;
begin
  BracePos := Pos('{', JsonText);
  if BracePos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  Result :=
    Copy(JsonText, 1, BracePos) +
    Chr(13) + Chr(10) +
    '  "options": {' +
    ' "enabled": true,' +
    ' "webhook_url": "' + EscapeJsonString(OptionsUrl) + '",' +
    ' "api_key": "' + EscapeJsonString(ApiKey) + '",' +
    ' "timeout_sec": 20 },' +
    Copy(JsonText, BracePos + 1, MaxInt);
end;

function ReplaceJsonStringField(
  const JsonText, FieldName, NewValue: String
): String;
var
  Marker: String;
  StartPos, ValueStart, ValueEnd: Integer;
begin
  Marker := '"' + FieldName + '"';
  StartPos := Pos(Marker, JsonText);
  if StartPos = 0 then
  begin
    Result := JsonText;
    Exit;
  end;

  ValueStart := StartPos + Length(Marker);
  while (ValueStart <= Length(JsonText)) and (JsonText[ValueStart] <> '"') do
    ValueStart := ValueStart + 1;
  if ValueStart > Length(JsonText) then
  begin
    Result := JsonText;
    Exit;
  end;

  ValueEnd := ValueStart + 1;
  while ValueEnd <= Length(JsonText) do
  begin
    if (JsonText[ValueEnd] = '\') and (ValueEnd < Length(JsonText)) then
      ValueEnd := ValueEnd + 2
    else if JsonText[ValueEnd] = '"' then
      Break
    else
      ValueEnd := ValueEnd + 1;
  end;
  if ValueEnd > Length(JsonText) then
  begin
    Result := JsonText;
    Exit;
  end;

  Result :=
    Copy(JsonText, 1, ValueStart) +
    EscapeJsonString(NewValue) +
    Copy(JsonText, ValueEnd, MaxInt);
end;

procedure WriteReceiverConfig(
  const ListenPort, NtTcpPort, DiscordWebhook, OptionsUrl, OptionsApiKey: String
);
var
  DefaultsPath, ConfigPath: String;
  JsonText: AnsiString;
  Updated, PortText: String;
begin
  ConfigPath := ExpandConstant('{app}\config.json');
  DefaultsPath := ExpandConstant('{tmp}\config.defaults.json');

  ExtractTemporaryFile('config.defaults.json');

  if FileExists(ConfigPath) then
  begin
    if not LoadStringFromFile(ConfigPath, JsonText) then
      Exit;
  end
  else if FileExists(DefaultsPath) then
  begin
    if not LoadStringFromFile(DefaultsPath, JsonText) then
      Exit;
  end
  else
    Exit;

  Updated := StripBom(String(JsonText));
  PortText := NormalizedPort(ListenPort, DefaultListenPort);
  if PortText <> '' then
    Updated := ReplaceRootListenPort(Updated, PortText);
  PortText := NormalizedPort(NtTcpPort, DefaultNtTcpPort);
  if PortText <> '' then
    Updated := ReplaceObjectPort(Updated, 'tcp', PortText);

  if Trim(DiscordWebhook) <> '' then
    Updated := ReplaceDiscordWebhook(Updated, Trim(DiscordWebhook))
  else if FileExists(ConfigPath) and (Updated = String(JsonText)) then
    Updated := Updated;

  if (Trim(OptionsUrl) <> '') and (Trim(OptionsApiKey) <> '') then
  begin
    if Pos('"options"', Updated) = 0 then
      Updated := InsertOptionsSection(
        Updated,
        Trim(OptionsUrl),
        Trim(OptionsApiKey)
      )
    else
    begin
      Updated := ReplaceJsonStringField(
        Updated,
        'webhook_url',
        Trim(OptionsUrl)
      );
      Updated := ReplaceJsonStringField(
        Updated,
        'api_key',
        Trim(OptionsApiKey)
      );
      if Pos('"enabled": false', Updated) > 0 then
        StringChangeEx(Updated, '"enabled": false', '"enabled": true', True);
    end;
  end;

  SaveStringToFile(ConfigPath, AnsiString(Updated), False);
end;

procedure InitializeWizard;
begin
  ListenPage := CreateInputQueryPage(
    wpSelectTasks,
    'Local ports',
    'HTTP webhook and NinjaTrader TCP',
    'Trade Desky uses HTTP 5090 and NT TCP 7077 by default. Change these if those are taken.' +
      Chr(13) + Chr(10) +
    'Set the same TCP port in the Webhook Trade Listener panel. Chrome extension: ' +
      'http://127.0.0.1:<http-port>/signal'
  );
  ListenPage.Add('HTTP listen port:', False);
  ListenPage.Add('NinjaTrader TCP port:', False);
  ListenPage.Values[0] := DefaultListenPort;
  ListenPage.Values[1] := DefaultNtTcpPort;

  DiscordPage := CreateInputQueryPage(
    ListenPage.ID,
    'Discord alerts (optional)',
    'Flow signal Discord webhook',
    'Paste your Discord webhook URL to receive trade / blocked-signal alerts.' +
      Chr(13) + Chr(10) +
    'Existing values are pre-filled when upgrading. Leave blank to skip Discord alerts.'
  );
  DiscordPage.Add('Discord webhook URL:', False);

  OptionsPage := CreateInputQueryPage(
    DiscordPage.ID,
    'Options trade receiver (optional)',
    'Forward allowed flow signals to trade-receiver',
    'Enter both values to enable options forwarding after a futures trade succeeds.' +
      Chr(13) + Chr(10) +
    'Existing values are pre-filled when upgrading. Leave both blank to keep futures only.'
  );
  OptionsPage.Add('Options base URL or /v1/ingest URL:', False);
  OptionsPage.Add('Device API key:', True);

  PrefillWizardFromExistingConfig;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = ListenPage.ID) or
     (CurPageID = DiscordPage.ID) or
     (CurPageID = OptionsPage.ID) then
    PrefillWizardFromExistingConfig;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Url, HttpPort, TcpPort: String;
begin
  Result := True;
  if CurPageID = ListenPage.ID then
  begin
    HttpPort := NormalizedPort(ListenPage.Values[0], DefaultListenPort);
    TcpPort := NormalizedPort(ListenPage.Values[1], DefaultNtTcpPort);
    if (HttpPort = '') or (TcpPort = '') then
    begin
      MsgBox(
        'Each port must be an integer between 1 and 65535.',
        mbError,
        MB_OK
      );
      Result := False;
    end
    else if HttpPort = TcpPort then
    begin
      MsgBox(
        'HTTP listen port and NinjaTrader TCP port must be different.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;

  if CurPageID = DiscordPage.ID then
  begin
    Url := Trim(DiscordPage.Values[0]);
    if (Url <> '') and
       (Pos('https://discord.com/api/webhooks/', Url) <> 1) and
       (Pos('https://discordapp.com/api/webhooks/', Url) <> 1) then
    begin
      MsgBox(
        'That does not look like a Discord webhook URL.' + Chr(13) + Chr(10) +
        'Use a URL starting with https://discord.com/api/webhooks/' + Chr(13) + Chr(10) +
        'or leave the field blank to skip.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;

  if CurPageID = OptionsPage.ID then
  begin
    if (Trim(OptionsPage.Values[0]) = '') <>
       (Trim(OptionsPage.Values[1]) = '') then
    begin
      MsgBox(
        'Enter both the options URL and API key, or leave both blank.',
        mbError,
        MB_OK
      );
      Result := False;
    end
    else if (Trim(OptionsPage.Values[0]) <> '') and
            (Pos('https://', Lowercase(Trim(OptionsPage.Values[0]))) <> 1) and
            (Pos('http://', Lowercase(Trim(OptionsPage.Values[0]))) <> 1) then
    begin
      MsgBox(
        'Options URL must start with https:// or http://.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteReceiverConfig(
      ListenPage.Values[0],
      ListenPage.Values[1],
      DiscordPage.Values[0],
      OptionsPage.Values[0],
      OptionsPage.Values[1]
    );
end;

