@echo off
setlocal
cd /d "%~dp0"
python booktime_bridge.py --watch
