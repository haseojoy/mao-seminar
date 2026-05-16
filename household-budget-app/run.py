"""
家計管理アプリ

使い方:
  python run.py

フォルダをどこに置いても動きます（ドキュメント・デスクトップ等）。
初回のみ必要なパッケージを自動インストールします。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# このファイルの場所を基準にする（フォルダをどこに移動しても動く）
ROOT = Path(__file__).parent
PORT = 8501
SETUP_FLAG = ROOT / ".setup_done"


def first_run_setup() -> None:
    """初回のみ requirements.txt をインストールする。"""
    if SETUP_FLAG.exists():
        return

    print("=" * 50)
    print("  初回セットアップ中（次回からは不要です）")
    print("=" * 50)

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r",
         str(ROOT / "requirements.txt"), "-q"],
    )
    if result.returncode != 0:
        print("\n[エラー] インストールに失敗しました。")
        print("以下を手動で実行してください:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    SETUP_FLAG.write_text("ok")
    print("完了！\n")


def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except OSError:
        return False


def start_streamlit() -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "app" / "dashboard.py"),
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--server.runOnSave", "false",
            "--browser.gatherUsageStats", "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_startup(timeout: int = 30) -> bool:
    print("起動中", end="", flush=True)
    for _ in range(timeout):
        if is_port_open(PORT):
            print(" 完了！\n")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print("\n[エラー] 起動タイムアウト")
    return False


def main() -> None:
    os.chdir(ROOT)
    first_run_setup()

    already_running = is_port_open(PORT)
    proc = None if already_running else start_streamlit()

    if not already_running and not wait_for_startup():
        if proc:
            proc.terminate()
        sys.exit(1)

    # pywebview があればネイティブウィンドウ、なければブラウザで開く
    try:
        import webview
        import types
        p = proc if proc else types.SimpleNamespace(terminate=lambda: None)
        window = webview.create_window(
            "家計管理ダッシュボード",
            f"http://localhost:{PORT}",
            width=1280, height=850,
            min_size=(900, 600),
            confirm_close=True,
        )
        webview.start(debug=False)
        p.terminate()

    except ImportError:
        # pywebview 未インストール → ブラウザで開く
        url = f"http://localhost:{PORT}"
        webbrowser.open(url)
        print(f"ブラウザでダッシュボードを開きました: {url}")
        print("終了するには Ctrl+C を押してください。")
        try:
            if proc:
                proc.wait()
        except KeyboardInterrupt:
            if proc:
                proc.terminate()


if __name__ == "__main__":
    main()
