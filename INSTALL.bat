@echo off
cd /d "%~dp0"
echo.
echo  Installation des dependances DMX + MIDI...
echo.
python -m pip install ftd2xx mido python-rtmidi --quiet
if errorlevel 1 (
    echo.
    echo  [ERREUR] Installation echouee.
    echo  Essai avec --break-system-packages...
    python -m pip install ftd2xx mido python-rtmidi --break-system-packages --quiet
)
echo.
echo  [OK] Installation terminee !
echo.
pause
