@echo off
cd /d "%~dp0"
echo.
echo  ◈  Build EXE Python 3.12 + inclusion DLLs
echo  ════════════════════════════════════════════
echo.

echo  [1/4] Installation des dependances...
py -3.12 -m pip install ftd2xx mido python-rtmidi pyinstaller --quiet

echo  [2/4] Recherche des DLLs necessaires...
py -3.12 -c "import ftd2xx, os; print(os.path.dirname(ftd2xx.__file__))" > ftd2xx_path.txt
set /p FTD2XX_DIR=<ftd2xx_path.txt
del ftd2xx_path.txt
echo  ftd2xx trouve dans : %FTD2XX_DIR%

py -3.12 -c "import mido, os; print(os.path.dirname(mido.__file__))" > mido_path.txt
set /p MIDO_DIR=<mido_path.txt
del mido_path.txt
echo  mido trouve dans : %MIDO_DIR%

echo  [3/4] Compilation...
py -3.12 -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "DMX_Stairville_Controller" ^
    --collect-all ftd2xx ^
    --collect-all mido ^
    --collect-all rtmidi ^
    --hidden-import ftd2xx ^
    --hidden-import mido ^
    --hidden-import mido.backends.rtmidi ^
    --hidden-import rtmidi ^
    dmx_controller.py

if errorlevel 1 (
    echo.
    echo [ERREUR] Compilation echouee.
    pause & exit /b 1
)

echo  [4/4] Copie des DLLs dans dist\...
copy "%FTD2XX_DIR%\*.dll" "dist\" >nul 2>&1
copy "%FTD2XX_DIR%\*.pyd" "dist\" >nul 2>&1

echo.
echo  Succes ! Votre exe est dans : dist\DMX_Stairville_Controller.exe
echo.
pause
