@echo off
chcp 65001 > nul
title 家計管理ダッシュボード

cd /d "%~dp0"

echo.
echo  ========================================
echo   家計管理ダッシュボード を起動しています
echo  ========================================
echo.

REM pywebview が入っていればネイティブウィンドウで開く（未インストールならブラウザ）
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [エラー] Python が見つかりません。
    echo Python をインストールしてから再実行してください。
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

python launcher.py

if %errorlevel% neq 0 (
    echo.
    echo [エラー] 起動に失敗しました。
    pause
)
