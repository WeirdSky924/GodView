@echo off
chcp 65001 >nul
title GodView 安装向导
python "%~dp0install.py" %*
pause
