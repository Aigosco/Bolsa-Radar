@echo off
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading\.venv\Scripts\python.exe" local\respaldo_nube.py >> "%TEMP%\bolsa_radar_respaldo.log" 2>&1
