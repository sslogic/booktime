@echo off
setlocal
cd /d "%~dp0"
python booktime_server.py --open --setup
