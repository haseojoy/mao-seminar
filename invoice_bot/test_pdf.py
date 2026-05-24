#!/usr/bin/env python3
"""
PDF生成テストスクリプト
実行すると カレントディレクトリにテスト用PDFを出力します。

使い方:
    cd invoice_bot
    python test_pdf.py
"""
import os
import shutil
import tempfile

from invoice_generator import generate_invoice

# テスト用請求書データ（税抜）
TEST_DATA_TAX_EXCL = {
    "bill_to": "テスト株式会社",
    "tax_included": False,
    "items": [
        {"name": "Webシステム開発", "quantity": 1, "unit_price": 500000},
        {"name": "保守サポート（月額）", "quantity": 3, "unit_price": 50000},
        {"name": "サーバー費用", "quantity": 1, "unit_price": 12000},
    ],
    "due_date": "2026-06-30",
    "invoice_number": "INV-2026-001",
    "notes": "お振込手数料はご負担ください。",
}

# テスト用請求書データ（税込）
TEST_DATA_TAX_INCL = {
    "bill_to": "サンプル合同会社",
    "tax_included": True,
    "items": [
        {"name": "デザイン制作", "quantity": 1, "unit_price": 110000},
        {"name": "修正対応", "quantity": 5, "unit_price": 11000},
    ],
    "due_date": None,
    "invoice_number": None,
    "notes": None,
}


def run_test(data: dict, label: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path, filename = generate_invoice(data, tmpdir)
        output_path = os.path.join(os.getcwd(), filename)
        shutil.copy(pdf_path, output_path)
        print(f"[{label}] PDF生成完了: {output_path}")


if __name__ == "__main__":
    print("PDFテスト生成を開始します...\n")
    run_test(TEST_DATA_TAX_EXCL, "税抜テスト")
    run_test(TEST_DATA_TAX_INCL, "税込テスト")
    print("\n完了。生成されたPDFを確認してください。")
