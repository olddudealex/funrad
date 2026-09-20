@echo off
REM FunRad - EMerge environment (Windows cmd)
cd /d "%~dp0"
py -3.12 -m venv .venv || python -m venv .venv || goto :fail
.venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
echo.
echo done. activate with:  .venv\Scripts\activate.bat
echo then:                 python coupler_catalogue.py
echo                       python redesign.py redesign_configs/final51_copper9.json
exit /b 0
:fail
echo SETUP FAILED - is Python 3.10-3.13 on PATH?
exit /b 1
