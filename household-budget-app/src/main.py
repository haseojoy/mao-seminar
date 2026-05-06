"""
家計管理アプリ メインエントリポイント

使い方:
  python -m src.main                    # 当月分を実行
  python -m src.main --year 2025 --month 4   # 指定月を実行
  python -m src.main --mock             # モックデータで動作確認
  python -m src.main --schedule         # 月次自動実行モード
"""

from __future__ import annotations

import argparse
import calendar
import os
import sys
from collections import defaultdict
from datetime import date

import schedule
import time

from dotenv import load_dotenv

from src.api.credit_card import CreditCardClient
from src.api.risona import RisonaClient
from src.analysis.analyzer import ExpenseAnalyzer
from src.excel.writer import ExcelReportWriter
from src.models.transaction import Category, MonthlySummary, Transaction, TransactionType


load_dotenv()


def collect_transactions(
    year: int,
    month: int,
    mock: bool = False,
) -> list[Transaction]:
    """りそな銀行とクレジットカードから取引データを収集する。"""
    from_date = date(year, month, 1)
    to_date = date(year, month, calendar.monthrange(year, month)[1])

    # ----------------------------------------
    # りそな銀行
    # ----------------------------------------
    risona = RisonaClient(
        client_id=os.getenv("RISONA_CLIENT_ID", ""),
        client_secret=os.getenv("RISONA_CLIENT_SECRET", ""),
        mock=mock,
    )

    if mock:
        risona.authenticate("")
    else:
        refresh_token = os.getenv("RISONA_REFRESH_TOKEN", "")
        if not refresh_token:
            print("[ERROR] RISONA_REFRESH_TOKEN が設定されていません。")
            sys.exit(1)
        risona.authenticate_with_refresh_token(refresh_token)

    accounts = risona.get_accounts()
    bank_txns: list[Transaction] = []
    for account in accounts:
        bank_txns.extend(
            risona.get_transactions(account.account_id, from_date, to_date)
        )

    # ----------------------------------------
    # クレジットカード
    # ----------------------------------------
    cc_provider = os.getenv("CC_PROVIDER", "smbc")
    cc_client = CreditCardClient(
        provider=cc_provider,
        client_id=os.getenv("CC_CLIENT_ID", ""),
        client_secret=os.getenv("CC_CLIENT_SECRET", ""),
        mock=mock,
    )

    if mock:
        cc_client.authenticate("")
    else:
        refresh_token = os.getenv("CC_REFRESH_TOKEN", "")
        if not refresh_token:
            print("[ERROR] CC_REFRESH_TOKEN が設定されていません。")
            sys.exit(1)
        cc_client.authenticate_with_refresh_token(refresh_token)

    cc_txns = cc_client.get_transactions(from_date, to_date)

    return bank_txns + cc_txns


def build_monthly_summary(
    year: int,
    month: int,
    transactions: list[Transaction],
) -> MonthlySummary:
    """取引リストから月次サマリーを生成する。"""
    total_income = sum(t.amount for t in transactions if not t.is_expense)
    total_expense = sum(t.amount for t in transactions if t.is_expense)

    by_category: dict[str, int] = defaultdict(int)
    for t in transactions:
        if t.is_expense:
            by_category[t.category.value] += t.amount
        else:
            by_category["収入"] += t.amount

    return MonthlySummary(
        year=year,
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        by_category=dict(by_category),
        transactions=sorted(transactions, key=lambda t: t.date),
    )


def run_monthly_report(year: int, month: int, mock: bool = False) -> None:
    print(f"\n{'='*50}")
    print(f"  家計管理レポート生成: {year}年{month:02d}月")
    print(f"{'='*50}")

    # 1. データ収集
    print("\n[1/4] 取引データを取得中...")
    transactions = collect_transactions(year, month, mock=mock)
    print(f"      → {len(transactions)} 件取得")

    # 2. サマリー生成
    print("[2/4] 月次サマリーを集計中...")
    summary = build_monthly_summary(year, month, transactions)
    print(f"      → 収入: {summary.total_income:,}円 / 支出: {summary.total_expense:,}円 / 差額: {summary.net:,}円")

    # 3. AI 分析
    print("[3/4] AI 支出分析を実行中...")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    analysis_text = ""
    if not api_key:
        print("      [WARN] ANTHROPIC_API_KEY 未設定。AI 分析をスキップします。")
    else:
        analyzer = ExpenseAnalyzer(api_key=api_key)
        analysis_text = analyzer.analyze(summary)
        print("      → 分析完了")

    # 4. Excel 出力
    print("[4/4] Excel レポートを生成中...")
    output_dir = os.getenv("OUTPUT_DIR", "output")
    writer = ExcelReportWriter(output_dir=output_dir)
    filepath = writer.write(summary, analysis_text=analysis_text)
    print(f"      → 保存先: {filepath}")

    print("\n完了しました。")

    # コンソール出力
    if analysis_text:
        print(f"\n{'='*50}")
        print("AI 分析結果:")
        print('='*50)
        print(analysis_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="家計管理アプリ")
    parser.add_argument("--year", type=int, default=None, help="対象年 (デフォルト: 当年)")
    parser.add_argument("--month", type=int, default=None, help="対象月 (デフォルト: 当月)")
    parser.add_argument("--mock", action="store_true", help="モックデータで実行")
    parser.add_argument("--schedule", action="store_true", help="月次自動実行モード")
    args = parser.parse_args()

    today = date.today()
    year = args.year or today.year
    month = args.month or today.month

    if args.schedule:
        print("月次自動実行モードを開始します。毎月1日 09:00 に実行されます。")

        def scheduled_job():
            t = date.today()
            # 前月分を生成（月初に前月レポートを作成）
            if t.month == 1:
                run_monthly_report(t.year - 1, 12, mock=args.mock)
            else:
                run_monthly_report(t.year, t.month - 1, mock=args.mock)

        schedule.every().month.at("09:00").do(scheduled_job)
        print("スケジューラー起動中。Ctrl+C で終了。")
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_monthly_report(year, month, mock=args.mock)


if __name__ == "__main__":
    main()
