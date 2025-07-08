[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=空间规划政策爬虫与合规性分析系统
AppVersion=2.1.0
AppVerName=空间规划政策爬虫与合规性分析系统 2.1.0
AppPublisher=空间规划政策分析团队
AppPublisherURL=https://gitee.com/ViVi141/space-planning-spider
AppSupportURL=https://gitee.com/ViVi141/space-planning-spider
AppUpdatesURL=https://gitee.com/ViVi141/space-planning-spider
DefaultDirName={autopf}\空间规划政策爬虫系统
DefaultGroupName=空间规划政策爬虫系统
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=空间规划政策爬虫系统_v2.1.0_安装程序
SetupIconFile=docs\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\空间规划政策爬虫系统.exe
UninstallDisplayName=空间规划政策爬虫与合规性分析系统
VersionInfoVersion=2.1.0.0
VersionInfoCompany=空间规划政策分析团队
VersionInfoDescription=空间规划政策爬虫与合规性分析系统
VersionInfoCopyright=Copyright (C) 2025 空间规划政策分析团队
VersionInfoProductName=空间规划政策爬虫与合规性分析系统
VersionInfoProductVersion=2.1.0.0

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "startmenuicon"; Description: "{cm:CreateStartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked

[Files]
Source: "dist\空间规划政策爬虫系统.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "版本管理说明.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\空间规划政策爬虫系统"; Filename: "{app}\空间规划政策爬虫系统.exe"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,空间规划政策爬虫系统}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\空间规划政策爬虫系统"; Filename: "{app}\空间规划政策爬虫系统.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\空间规划政策爬虫系统"; Filename: "{app}\空间规划政策爬虫系统.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\空间规划政策爬虫系统.exe"; Description: "{cm:LaunchProgram,空间规划政策爬虫系统}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\空间规划政策爬虫系统"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\空间规划政策爬虫系统"; ValueType: string; ValueName: "Version"; ValueData: "2.1.0"; Flags: uninsdeletekey

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 安装完成后的操作
  end;
end;
