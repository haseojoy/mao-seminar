"""
家計管理アプリ ランチャー

使い方:
  Windows : start_app.bat をダブルクリック
  Mac     : start_app.command をダブルクリック
  直接実行 : python launcher.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
PORT = 8501
SETUP_FLAG = ROOT / ".setup_done"
APP_TITLE = "💰 家計管理ダッシュボード"


# ------------------------------------------------------------------ #
#  初回セットアップ                                                      #
# ------------------------------------------------------------------ #

def first_run_setup() -> None:
    """初回のみ requirements.txt をインストールする。"""
    if SETUP_FLAG.exists():
        return

    print("=" * 50)
    print("  初回セットアップを実行中...")
    print("  （次回からは不要です）")
    print("=" * 50)

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "-q"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("\n[エラー] パッケージのインストールに失敗しました。")
        print("管理者権限で再実行するか、手動で以下を実行してください:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    SETUP_FLAG.write_text("ok")
    print("セットアップ完了。\n")


# ------------------------------------------------------------------ #
#  Streamlit 起動                                                       #
# ------------------------------------------------------------------ #

def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except OSError:
        return False


def start_streamlit() -> subprocess.Popen:
    app_path = str(ROOT / "app" / "dashboard.py")
    return subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--server.runOnSave", "false",
            "--browser.gatherUsageStats", "false",
            "--theme.base", "light",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_startup(timeout: int = 30) -> bool:
    """Streamlit が起動するまで最大 timeout 秒待つ。"""
    print("アプリを起動中", end="", flush=True)
    for _ in range(timeout):
        if is_port_open(PORT):
            print(" 完了！\n")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print("\n[エラー] 起動タイムアウト")
    return False


# ------------------------------------------------------------------ #
#  ウィンドウ表示                                                        #
# ------------------------------------------------------------------ #

def open_native_window(proc: subprocess.Popen) -> None:
    """pywebview でネイティブウィンドウを開く。"""
    import webview

    window = webview.create_window(
        APP_TITLE,
        f"http://localhost:{PORT}",
        width=1280,
        height=850,
        min_size=(900, 600),
        confirm_close=True,
    )
    webview.start(debug=False)
    # ウィンドウが閉じたら Streamlit も終了
    proc.terminate()


def open_in_browser(proc: subprocess.Popen) -> None:
    """フォールバック: ブラウザで開く。"""
    url = f"http://localhost:{PORT}"
    print(f"ブラウザで開きます: {url}")
    webbrowser.open(url)
    print("アプリを終了するには このウィンドウを閉じてください。(Ctrl+C)")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


# ------------------------------------------------------------------ #
#  メイン                                                               #
# ------------------------------------------------------------------ #

def main() -> None:
    os.chdir(ROOT)

    first_run_setup()

    # ポートが既に使用中なら再起動しない
    if is_port_open(PORT):
        print("既に起動中のアプリを開きます。")
        proc = None
    else:
        proc = start_streamlit()
        if not wait_for_startup():
            if proc:
                proc.terminate()
            sys.exit(1)

    try:
        import webview  # noqa: F401
        if proc is None:
            # 既存プロセスに接続するだけのダミー Popen
            import types
            proc = types.SimpleNamespace(terminate=lambda: None)
        open_native_window(proc)
    except ImportError:
        # pywebview が未インストールの場合はブラウザで開く
        if proc is None:
            webbrowser.open(f"http://localhost:{PORT}")
        else:
            open_in_browser(proc)


if __name__ == "__main__":
    main()
