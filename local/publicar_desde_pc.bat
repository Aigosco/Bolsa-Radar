@echo off
rem Publica en Bolsa-Radar lo que solo existe en el PC: estado del bot (MT5, sin datos de la cuenta), tesis de
rem analistas, radar de acciones y efecto F1. Pensado para el Programador de tareas (cada hora). Necesita MT5 abierto.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading\.venv\Scripts\python.exe" local\publicar_desde_pc.py >> "%TEMP%\bolsa_radar_publicar.log" 2>&1
