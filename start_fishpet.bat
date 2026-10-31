@echo off
setlocal
rem Launch the overlay.  Usage: double-click, or `start_fishpet.bat [godot.exe]`.
set "GAME=%~dp0game"
set "GODOT=%~1"

if not defined GODOT if defined FISHPET_GODOT set "GODOT=%FISHPET_GODOT%"
if not defined GODOT if exist "D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe" set "GODOT=D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe"
if not defined GODOT if exist "I:\Godot\Godot_v4.7.2-stable_win64.exe" set "GODOT=I:\Godot\Godot_v4.7.2-stable_win64.exe"
if not defined GODOT if exist "I:\Godot\Godot_v4.7.2-stable_win64\Godot_v4.7.2-stable_win64.exe" set "GODOT=I:\Godot\Godot_v4.7.2-stable_win64\Godot_v4.7.2-stable_win64.exe"
if not defined GODOT for %%G in (godot.exe) do if not defined GODOT set "GODOT=%%~$PATH:G"

if not defined GODOT (
	echo Godot 4.7 not found.
	echo Pass the executable or set FISHPET_GODOT, e.g.:
	echo     start_fishpet.bat "C:\Godot\Godot_v4.7-stable_win64.exe"
	pause
	exit /b 1
)

if not exist "%GODOT%" (
	echo Godot not found: %GODOT%
	pause
	exit /b 1
)

rem A running game loads .godot/imported resources; source PNG/Spine edits
rem alone do not refresh that cache. Import headlessly before every launch.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\import_assets.ps1" -GodotExe "%GODOT%" -GamePath "%GAME%"
if errorlevel 1 (
	echo FishPet could not refresh its assets. See game\.godot\fishpet-import-errors.log.
	pause
	exit /b 1
)
start "" "%GODOT%" --path "%GAME%" --rendering-driver opengl3
endlocal
