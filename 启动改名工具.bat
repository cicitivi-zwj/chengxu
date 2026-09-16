@echo off
rem ---------------------------------------------------------------
rem  Double-click this file to launch the batch-rename GUI.
rem  It uses pythonw, so no black console window stays open.
rem  If Python is upgraded or moved, edit the PYW line below only.
rem
rem  NOTE: keep this file pure ASCII. Chinese characters in a .bat
rem  file break cmd.exe parsing and the script silently does nothing.
rem ---------------------------------------------------------------
set "PYW=%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe"
if not exist "%PYW%" goto nopython
start "" "%PYW%" "%~dp0rename_tool.py"
exit /b 0

:nopython
echo.
echo  [ERROR] Python interpreter not found:
echo      %PYW%
echo.
echo  Open this file in Notepad and point the PYW line at your
echo  own pythonw.exe, then save and try again.
echo.
pause
