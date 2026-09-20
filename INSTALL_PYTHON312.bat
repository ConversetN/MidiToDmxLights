@echo off
echo.
echo  Ce script installe Python 3.12 et toutes les dependances
echo  Python 3.14 reste installe, les deux coexistent.
echo.
echo  1. Telechargement Python 3.12...
curl -L -o "%TEMP%\python312.exe" https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe
echo.
echo  2. Installation Python 3.12 (sans ecraser 3.14)...
"%TEMP%\python312.exe" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1
echo.
echo  3. Installation des dependances via py -3.12...
py -3.12 -m pip install ftd2xx mido python-rtmidi pygame --quiet
echo.
echo  [OK] Termine ! Lance maintenant le script avec :
echo       py -3.12 dmx_controller.py
echo.
pause
