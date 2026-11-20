@echo off
title AIOps Cloud Monitoring - Build and Open Dashboards
chcp 65001 > nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if %errorlevel% neq 0 (
    pause
)
