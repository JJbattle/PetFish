@echo off
setlocal
set "SRC=%~dp0start_fishpet.bat"
set "DIR=%~dp0"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\FishPet.lnk"

if not exist "%SRC%" (
	echo start_fishpet.bat not found next to this script.
	exit /b 1
)

powershell -NoProfile -Command ^
	"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
	"$s.TargetPath = '%SRC%';" ^
	"$s.WorkingDirectory = '%DIR%';" ^
	"$s.Save()"

if exist "%LNK%" (
	echo Startup shortcut created: %LNK%
) else (
	echo Failed to create shortcut.
	exit /b 1
)
endlocal
