@echo off
rem Videos nuevos de Cava: transcripción + tesis con Claude Code (plan Pro) + publicación en GitHub.
rem Programado de lunes a viernes a las 7:30 Bogotá (antes de la lectura con IA de las 8:10).
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading\.venv\Scripts\python.exe" local\cava_diario.py >> "%TEMP%\bolsa_radar_cava.log" 2>&1
