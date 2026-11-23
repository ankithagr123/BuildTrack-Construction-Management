@echo off
setlocal EnableExtensions
set "PROJECT_DIR=%~dp0"
set "LAUNCHER=%PROJECT_DIR%Start BuildTrack.bat"
set "BUILDTRACK_LAUNCHER=%LAUNCHER%"
if not exist "%LAUNCHER%" (
  echo Cannot enable automatic startup: the existing launcher was not found.
  echo Expected: "%LAUNCHER%"
  pause
  exit /b 1
)
echo Enabling BuildTrack automatic startup for the current Windows user...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $launcher=$env:BUILDTRACK_LAUNCHER; $startup=[Environment]::GetFolderPath('Startup'); $shortcutPath=Join-Path $startup 'BuildTrack Auto Start.lnk'; try { $shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut($shortcutPath); $shortcut.TargetPath=$launcher; $shortcut.WorkingDirectory=(Split-Path -Parent $launcher); $shortcut.Description='Start the existing BuildTrack launcher when this user signs in'; $shortcut.WindowStyle=1; $shortcut.Save(); if (-not (Test-Path -LiteralPath $shortcutPath)) { throw 'Startup shortcut was not created' }; Write-Output ('Startup shortcut created: ' + $shortcutPath) } catch { $runKey='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; New-Item -Path $runKey -Force | Out-Null; $runCommand='"' + $env:ComSpec + '" /c ""' + $launcher + '""'; New-ItemProperty -Path $runKey -Name 'BuildTrack' -Value $runCommand -PropertyType String -Force | Out-Null; if ((Get-ItemProperty -Path $runKey -Name 'BuildTrack').BuildTrack -ne $runCommand) { throw 'Could not verify the per-user startup entry' }; Write-Output 'Startup-folder shortcut was not writable; enabled the equivalent per-user Windows Run entry instead.' }"
if errorlevel 1 (
  echo Could not create the Startup shortcut. No BuildTrack data was changed.
  echo Run this installer directly from your signed-in Windows desktop if this environment blocks per-user startup changes.
  pause
  exit /b 1
)
echo Automatic startup is enabled for this Windows user.
echo The existing launcher checks for BuildTrack before starting it and opens Chrome after its health check succeeds.
echo Use "Uninstall BuildTrack Auto Start.bat" to disable automatic startup.
pause
exit /b 0
