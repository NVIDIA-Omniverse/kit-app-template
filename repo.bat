@echo off

:: Set OMNI_REPO_ROOT early so `repo` bootstrapping can target the repository
:: root when writing out Python dependencies.
set OMNI_REPO_ROOT="%~dp0"

call "%~dp0tools\packman\python.bat" "%~dp0tools\repoman\repoman.py" %*
if %errorlevel% neq 0 ( goto Error )

:Success
exit /b 0

:Error
exit /b %errorlevel%
