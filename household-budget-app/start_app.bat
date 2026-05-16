@echo off
chcp 65001 > nul
title 家計管理ダッシュボード
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python が見つかりません。https://www.python.org/ からインストールしてください。
    pause
    exit /b 1
)

python run.py
if %errorlevel% neq 0 ( pause )
