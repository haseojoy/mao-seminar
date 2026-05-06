#!/bin/bash
# Mac 用ダブルクリック起動スクリプト
# 初回: ターミナルで chmod +x start_app.command を実行してください

cd "$(dirname "$0")"

# Python3 の確認
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python3 が見つかりません。\nhttps://www.python.org/downloads/ からインストールしてください。" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

python3 launcher.py
