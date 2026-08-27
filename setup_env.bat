@echo off
REM Reproducible environment setup for scdocdecoding (Windows, conda).
REM Creates/updates a pythonocc-core modeling env and installs the GUI deps.
setlocal
set SCDM_ENV_NAME=scdm
echo [1/3] conda env with pythonocc-core (conda-forge) + numpy + vtk...
conda create -y -n %SCDM_ENV_NAME% -c conda-forge python=3.12 pythonocc-core numpy vtk || goto :err
echo [2/3] pip deps: PyQt5, scipy, trimesh, pytest...
conda run -n %SCDM_ENV_NAME% python -m pip install PyQt5 scipy trimesh pytest || goto :err
echo [3/3] verify OCC...
conda run -n %SCDM_ENV_NAME% python -c "from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox; print('OCC OK', BRepPrimAPI_MakeBox(1,1,1).Shape())" || goto :err
echo.
echo Done. Activate with:  conda activate %SCDM_ENV_NAME%
exit /b 0
:err
echo FAILED - see messages above.
exit /b 1
