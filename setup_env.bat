@echo off
REM Reproducible pythonocc-core environment setup for scdocdecoding (Windows + conda).
REM Usage:  setup_env.bat            (creates/updates the 'scdm' env)
REM         setup_env.bat occ        (instead: complete the existing 'occ' env)
setlocal
set ENV_NAME=%1
if "%ENV_NAME%"=="" set ENV_NAME=scdm
echo [1/3] conda env with pythonocc-core (conda-forge) + numpy + vtk...
if exist "%CONDA_PREFIX%\envs\%ENV_NAME%" goto :deps
conda create -y -n %ENV_NAME% -c conda-forge python=3.12 pythonocc-core numpy vtk || goto :err
:deps
echo [2/3] pip deps: PyQt5, pytest...
conda run -n %ENV_NAME% python -m pip install --quiet PyQt5 pytest || goto :err
echo [3/3] verify OCC...
conda run -n %ENV_NAME% python -c "from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox; print('OCC OK', BRepPrimAPI_MakeBox(1,1,1).Shape())" || goto :err
echo.
echo Done. Activate with:  conda activate %ENV_NAME%
echo Then from the project root:  python scdm_gui.py box.scdoc
exit /b 0
:err
echo FAILED - see messages above.
exit /b 1
