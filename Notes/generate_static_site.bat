@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: Generate static site from FunRad (Obsidian vault) via Quartz
::
:: Usage:
::   generate_static_site.bat          -- build only
::   generate_static_site.bat --serve  -- build and start local server
::                                        (open http://localhost:8080 to preview)
::
:: NOTE: Do NOT open docs\index.html directly in a browser.
::   Quartz uses clean URLs (no .html extension) which require
::   a web server to resolve. Use --serve for local preview.
::
:: Prerequisites -- run once after cloning:
::   See QUARTZ_SETUP.md for full instructions.
::   Short version:
::     1. Install Node.js (https://nodejs.org)
::     2. cd Notes\quartz
::     3. npm install
:: ============================================================

set ROOT=%~dp0
set FUNRAD=%ROOT%FunRad
set QUARTZ=%ROOT%quartz
set CONTENT=%QUARTZ%\content
set PUBLIC=%ROOT%..\docs

:: 1. Clear quartz content
echo [1/4] Clearing quartz\content...
if exist "%CONTENT%" (
    rmdir /s /q "%CONTENT%"
    if errorlevel 1 ( echo ERROR: failed to remove %CONTENT% & exit /b 1 )
)
mkdir "%CONTENT%"

:: 2. Copy FunRad vault into quartz content
echo [2/4] Copying FunRad to quartz\content...
xcopy /E /I /Y /Q "%FUNRAD%\*" "%CONTENT%\"
if errorlevel 1 ( echo ERROR: xcopy failed & exit /b 1 )

:: 3. Build static site
cd /d "%QUARTZ%"

if /i "%~1"=="--serve" (
    rem serve mode: Quartz handles build + local server in one command
    echo [3/3] Building and serving with Quartz at http://localhost:8080 ...
    call npx quartz build --serve
    exit /b !errorlevel!
)

echo [3/4] Building with Quartz...
call npx quartz build
if errorlevel 1 ( echo ERROR: Quartz build failed & exit /b 1 )

:: 4. Copy output to repo docs\ folder (for GitHub Pages)
echo [4/4] Copying quartz\public to %PUBLIC%...
if exist "%PUBLIC%" (
    rmdir /s /q "%PUBLIC%"
)
xcopy /E /I /Y /Q "%QUARTZ%\public\*" "%PUBLIC%\"
if errorlevel 1 ( echo ERROR: failed to copy public output & exit /b 1 )

echo.
echo Done! Static site is at: %PUBLIC%
echo TIP: To preview locally run:  generate_static_site.bat --serve
