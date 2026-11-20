@echo off
title AIOps & Cloud Monitoring Demo - 1-Click Master Runner
chcp 65001 > nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_demo.ps1"
if %errorlevel% neq 0 (
    pause
)
