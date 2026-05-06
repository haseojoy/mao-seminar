"""
.exe / .app ビルドスクリプト (PyInstaller)

実行方法:
  cd household-budget-app
  pip install pyinstaller pywebview
  python build_exe/build.py

成果物:
  dist/家計管理アプリ.exe  (Windows)
  dist/家計管理アプリ.app  (Mac)
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build() -> None:
    system = platform.system()
    print(f"ビルド対象: {system}")

    icon = str(ROOT / "build_exe" / ("icon.ico" if system == "Windows" else "icon.icns"))
    icon_opt = ["--icon", icon] if Path(icon).exists() else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile" if system == "Windows" else "--onedir",
        "--windowed",                          # ターミナルウィンドウを非表示
        "--name", "家計管理アプリ",
        *icon_opt,
        # アプリのソースファイルを同梱
        "--add-data", f"{ROOT / 'app'}:app",
        "--add-data", f"{ROOT / 'src'}:src",
        "--add-data", f"{ROOT / 'sample_data'}:sample_data",
        "--add-data", f"{ROOT / '.streamlit'}:.streamlit",
        # 非表示インポートを明示
        "--hidden-import", "streamlit",
        "--hidden-import", "plotly",
        "--hidden-import", "anthropic",
        "--hidden-import", "openpyxl",
        "--hidden-import", "pandas",
        "--hidden-import", "webview",
        str(ROOT / "launcher.py"),
    ]

    print("\n実行コマンド:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        dist = ROOT / "dist"
        print(f"\n✅ ビルド成功！")
        print(f"   成果物: {dist}")
        print(f"   配布するには dist/ フォルダごと渡してください。")
    else:
        print("\n❌ ビルド失敗。エラーを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    build()
