@echo off
cd /d C:\Users\mokha\catalogiq
call .venv\Scripts\activate.bat
python -m app.connector_profile_dialog
pause
