@echo off
cd /d C:\Users\mokha\catalogiq
call .venv\Scripts\activate.bat
python -m app.catalogiq_command_center
pause
