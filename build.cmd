@echo off
setlocal
cd /d "%~dp0"
python "%~dp0fetch_dependencies.py"
if errorlevel 1 exit /b 1
if defined VSCMD_VER goto compile
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" exit /b 1
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCROOT=%%I"
if not defined VCROOT exit /b 1
call "%VCROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
:compile
if not exist build mkdir build
pushd build
cl /nologo /O2 /std:c++20 /EHsc ..\src\expanded_point_control.cpp /Fe:arrivals.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++20 /EHsc ..\src\source_cache.cpp /Fe:source_cache.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++20 /EHsc ..\src\cache_sizes.cpp /Fe:cache_sizes.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DNOMINMAX /I..\vendor\tglib\tglib_cpp\src /I..\study ..\study\study.cpp /Fe:study.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DNOMINMAX /I..\study ..\study\census.cpp /Fe:census.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DNOMINMAX /I..\study ..\study\batch.cpp /Fe:batch.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DNOMINMAX /I..\study ..\study\timetable.cpp /Fe:timetable.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DNOMINMAX /I..\study ..\supplement\bridge_isolation.cpp /Fe:bridge_isolation.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /std:c++17 /EHsc ..\supplement\latency_clock.cpp /Fe:latency_clock.exe
if errorlevel 1 exit /b 1
popd
