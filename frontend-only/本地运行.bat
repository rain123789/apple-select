@echo off
REM 苹果检测（纯前端）本地运行脚本
REM 双击本文件即可启动本地服务并自动打开浏览器
cd /d "%~dp0"
"C:\Users\liubojun\.workbuddy\binaries\python\versions\3.13.12\python.exe" serve.py
pause
