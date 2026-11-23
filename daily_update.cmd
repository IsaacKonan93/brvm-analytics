@echo off
rem Daily update of the BRVM database (used by Windows Task Scheduler, see UPDATE.md).
cd /d "%~dp0"
".env\Scripts\python.exe" daily_update.py %*
exit /b %ERRORLEVEL%
