@echo off
rem Arranque completo de Bolsa-Radar (MT5, bot, nube, Cava, lectura IA, publicar). Equivale a decir "ejecutar bolsa".
title Arranque Bolsa-Radar
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading\.venv\Scripts\python.exe" local\arrancar.py
pause
