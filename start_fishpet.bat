@echo off
setlocal
set "GODOT=D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe"
set "GAME=%~dp0game"

if not exist "%GODOT%" (
	echo Godot not found: %GODOT%
	pause
	exit /b 1
)

start "" "%GODOT%" --path "%GAME%" --rendering-driver opengl3
endlocal
