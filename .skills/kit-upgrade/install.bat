@echo off
REM Install the kit-upgrade skill into an existing Kit project so an AI assistant
REM can load it there. Copies SKILL.md, README.md, procedures\, and references\
REM (not this installer) into <target>\<dest-kind>\kit-upgrade\.
REM
REM Usage:
REM   install.bat C:\path\to\your-kit-project [dest-kind]
REM     dest-kind defaults to ".skills". Use ".claude\skills" for the Claude Code layout.
setlocal
set "SRC=%~dp0"
set "TARGET=%~1"
set "DEST_KIND=%~2"
if "%DEST_KIND%"=="" set "DEST_KIND=.skills"

if "%TARGET%"=="" (
  echo Usage: %~nx0 C:\path\to\your-kit-project [.skills^|.claude\skills] 1>&2
  exit /b 1
)
if not exist "%TARGET%\" (
  echo Error: target project directory not found: %TARGET% 1>&2
  exit /b 1
)

set "DEST=%TARGET%\%DEST_KIND%\kit-upgrade"
if not exist "%DEST%\" mkdir "%DEST%"
copy /Y "%SRC%SKILL.md" "%DEST%\" >nul
copy /Y "%SRC%README.md" "%DEST%\" >nul
REM Replace each bundled dir in place so a re-install mirrors the source (matches
REM install.sh's rm -rf); xcopy alone would leave behind files deleted upstream.
for %%D in (references procedures) do (
  if exist "%DEST%\%%D\" rmdir /S /Q "%DEST%\%%D"
  xcopy /E /I /Y "%SRC%%%D" "%DEST%\%%D\" >nul
)

echo Installed kit-upgrade skill to: %DEST%
echo Next: point your AI assistant at %DEST%\SKILL.md and ask it to upgrade the project.
endlocal
