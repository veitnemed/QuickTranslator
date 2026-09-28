@echo off
if exist "%~dp0QuickTranslator.exe" (
  start "" "%~dp0QuickTranslator.exe"
) else (
  start "" "%LocalAppData%\Programs\Python\Launcher\pyw.exe" "%~dp0translator.pyw"
)
