@echo off
setlocal EnableExtensions
echo Removing only the BuildTrack Startup shortcut for the current Windows user...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $startup=[Environment]::GetFolderPath('Startup'); $shortcutPath=Join-Path $startup 'BuildTrack Auto Start.lnk'; if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force; Write-Output 'Removed the Startup-folder shortcut.' }; $runKey='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'; if (Test-Path $runKey) { Remove-ItemProperty -Path $runKey -Name 'BuildTrack' -ErrorAction SilentlyContinue }; Write-Output 'BuildTrack automatic startup disabled.'"
if errorlevel 1 (
  echo Could not remove the Startup shortcut.
  pause
  exit /b 1
)
echo The running BuildTrack server, project files and SQLite database were not changed.
pause
exit /b 0
