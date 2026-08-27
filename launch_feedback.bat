@echo off
chcp 65001 > nul
title 📢 학원 수업 피드백 생성기
cd /d "%~dp0"

echo =======================================================
echo          📢 두잉창의코딩학원 피드백 생성기
echo =======================================================
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe src\scripts\gen_feedback.py %*
) else (
    python src\scripts\gen_feedback.py %*
)

echo.
pause
