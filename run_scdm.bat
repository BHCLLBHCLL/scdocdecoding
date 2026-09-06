@echo off
REM Launch the SCDM shell with the kernel-capable conda env.
REM Direct-editing tools (Pull/Move/Fill/Combine/...) need pythonocc-core;
REM the plain `python` on PATH (anaconda base) has PyQt5+VTK only, which
REM renders in lightweight mode but leaves every kernel tool dead.
REM Usage:  run_scdm.bat [file.scdoc]
setlocal
set ENV_NAME=scdm
set PY=%USERPROFILE%\.conda\envs\%ENV_NAME%\python.exe
if not exist "%PY%" if defined CONDA_PREFIX set PY=%CONDA_PREFIX%\envs\%ENV_NAME%\python.exe
if not exist "%PY%" if exist "%CONDA_EXE%" (
    for /f "delims=" %%i in ('"%CONDA_EXE%" run -n %ENV_NAME% python -c "import sys;print(sys.executable)" 2^>nul') do set PY=%%i
)
if not exist "%PY%" (
    echo conda env "%ENV_NAME%" not found. Run setup_env.bat first.
    pause
    exit /b 1
)
start "SCDM" "%PY%" "%~dp0scdm_gui.py" %*
exit /b 0
