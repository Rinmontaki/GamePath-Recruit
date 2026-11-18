@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [GamePath] Creando entorno virtual...
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
if not exist ".venv\.gamepath_deps_ok" (
  echo [GamePath] Instalando dependencias de Streamlit...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto error
  type nul > ".venv\.gamepath_deps_ok"
)
echo [GamePath] Iniciando interfaz en http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run frontend/app.py
if errorlevel 1 goto error
exit /b 0
:error
echo [GamePath] No fue posible iniciar. Revisa los mensajes de arriba.
pause
exit /b 1
