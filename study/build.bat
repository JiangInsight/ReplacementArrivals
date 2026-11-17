@echo off
setlocal
if "%~2"=="" exit /b 2
if defined VSCMD_VER goto compile
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" exit /b 1
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCROOT=%%I"
if not defined VCROOT exit /b 1
call "%VCROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
:compile
set "study_source=%~dp0study.cpp"
if not "%~3"=="" set "study_source=%~3"
cl /nologo /EHsc /O2 /std:c++17 /DNOMINMAX /I"%~1\tglib_cpp\src" /I"%~dp0." "%study_source%" /Fo:"%~dpn2.obj" /Fe:"%~2"
exit /b %errorlevel%

