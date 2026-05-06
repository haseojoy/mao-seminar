"""
家計管理アプリ メインエントリポイント

使い方:
  python -m src.main --csv sample_data/risona_202604.csv  # CSVから実行（実データ）
  python -m src.main --mock                               # モックデータで動作確認
  python -m src.main --year 2026 --month 4                # 指定月を実行
  python -m src.main --schedule                           # 月次自動実行モード
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
from src.models.transaction import Category, MonthlySummary, SavingsGoal, Transaction, TransactionType


load_dotenv()


def collect_transactions(
    year: int,
    month: int,
    mock: bool = False,
    csv_path: str | None = None,
) -> list[Transaction]:
    """りそな銀行とクレジットカードから取引データを収集する。"""
    from_date = date(year, month, 1)
    to_date = date(year, month, calendar.monthrange(year, month)[1])

    # ----------------------------------------
    # りそな銀行（CSV モード優先）
    # ----------------------------------------
    if csv_path:
        print(f"      CSV から読み込み: {csv_path}")
        bank_txns = RisonaClient.from_csv(csv_path, target_year=year, target_month=month)
    elif mock:
        risona = RisonaClient(client_id="", client_secret="", mock=True)
        risona.authenticate("")
        accounts = risona.get_accounts()
        bank_txns = []
        for account in accounts:
            bank_txns.extend(risona.get_transactions(account.account_id, from_date, to_date))
    else:
        risona = RisonaClient(
            client_id=os.getenv("RISONA_CLIENT_ID", ""),
            client_secret=os.getenv("RISONA_CLIENT_SECRET", ""),
        )
        refresh_token = os.getenv("RISONA_REFRESH_TOKEN", "")
        if not refresh_token:
            print("[ERROR] RISONA_REFRESH_TOKEN が設定されていません。")
            sys.exit(1)
        risona.authenticate_with_refresh_token(refresh_token)
        accounts = risona.get_accounts()
        bank_txns = []
        for account in accounts:
            bank_txns.extend(risona.get_transactions(account.account_id, from_date, to_date))

    # ----------------------------------------
    # クレジットカード（CSV モード / mock 時はスキップ）
    # ----------------------------------------
    cc_txns: list[Transaction] = []
    cc_csv = os.getenv("CC_CSV_PATH", "")
    if cc_csv and os.path.exists(cc_csv):
        print(f"      クレカ CSV から読み込み: {cc_csv}")
        cc_txns = CreditCardClient.from_csv(cc_csv)
    elif mock:
        cc_client = CreditCardClient(provider="smbc", client_id="", client_secret="", mock=True)
        cc_client.authenticate("")
        cc_txns = cc_client.get_transactions(from_date, to_date)
    elif os.getenv("CC_CLIENT_ID"):
        cc_provider = os.getenv("CC_PROVIDER", "smbc")
        cc_client = CreditCardClient(
            provider=cc_provider,
            client_id=os.getenv("CC_CLIENT_ID", ""),
            client_secret=os.getenv("CC_CLIENT_SECRET", ""),
        )
        refresh_token = os.getenv("CC_REFRESH_TOKEN", "")
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


def build_goal(cumulative_savings: int = 0) -> SavingsGoal:
    """環境変数または引数から貯蓄目標を構築する。"""
    target = int(os.getenv("GOAL_TARGET", "1000000"))
    stretch = int(os.getenv("GOAL_STRETCH", "1500000"))
    deadline_str = os.getenv("GOAL_DEADLINE", "2026-12-31")
    deadline = date.fromisoformat(deadline_str)
    return SavingsGoal(
        target_amount=target,
        deadline=deadline,
        stretch_amount=stretch,
        current_savings=cumulative_savings,
    )


def run_monthly_report(
    year: int,
    month: int,
    mock: bool = False,
    csv_path: str | None = None,
) -> None:
    print(f"\n{'='*50}")
    print(f"  家計管理レポート生成: {year}年{month:02d}月")
    print(f"{'='*50}")

    # 1. データ収集
    print("\n[1/4] 取引データを取得中...")
    transactions = collect_transactions(year, month, mock=mock, csv_path=csv_path)
    print(f"      → {len(transactions)} 件取得")

    # 2. サマリー生成
    print("[2/4] 月次サマリーを集計中...")
    summary = build_monthly_summary(year, month, transactions)
    print(f"      → 収入: {summary.total_income:,}円 / 支出: {summary.total_expense:,}円 / 差額: {summary.net:,}円")

    # 貯蓄目標 (累計貯蓄は CURRENT_SAVINGS 環境変数で管理)
    cumulative = int(os.getenv("CURRENT_SAVINGS", "0"))
    goal = build_goal(cumulative_savings=cumulative)
    on_track = goal.on_track(summary.net)
    print(f"      → 目標進捗: 月次貯蓄 {summary.net:,}円 / 必要 {goal.required_monthly_savings:,}円 "
          f"({'✅ ペース達成' if on_track else '⚠️ ペース不足'})")

    # 3. AI 分析
    print("[3/4] AI 支出分析を実行中...")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    analysis_text = ""
    if not api_key:
        print("      [WARN] ANTHROPIC_API_KEY 未設定。AI 分析をスキップします。")
    else:
        analyzer = ExpenseAnalyzer(api_key=api_key)
        analysis_text = analyzer.analyze(summary, goal=goal)
        print("      → 分析完了")

    # 4. Excel 出力
    print("[4/4] Excel レポートを生成中...")
    output_dir = os.getenv("OUTPUT_DIR", "output")
    writer = ExcelReportWriter(output_dir=output_dir)
    filepath = writer.write(summary, analysis_text=analysis_text, goal=goal)
    print(f"      → 保存先: {filepath}")

    print("\n完了しました。")

    # コンソール出力
    if analysis_text:
        print(f"\n{'='*50}")
        print("AI 分析結果:")
        print('='*50)
        print(analysis_text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="家計管理アプリ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使い方の例:
  python -m src.main --csv sample_data/risona_202604.csv --year 2026 --month 4
  python -m src.main --mock
  python -m src.main --schedule
        """,
    )
    parser.add_argument("--year", type=int, default=None, help="対象年")
    parser.add_argument("--month", type=int, default=None, help="対象月")
    parser.add_argument("--mock", action="store_true", help="モックデータで実行")
    parser.add_argument("--csv", type=str, default=None, metavar="FILE",
                        help="りそな銀行 CSV ファイルのパス")
    parser.add_argument("--schedule", action="store_true", help="月次自動実行モード")
    args = parser.parse_args()

    today = date.today()
    year = args.year or today.year
    month = args.month or today.month

    if args.schedule:
        print("月次自動実行モードを開始します。毎月1日 09:00 に実行されます。")

        def scheduled_job():
            t = date.today()
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
        run_monthly_report(year, month, mock=args.mock, csv_path=args.csv)


if __name__ == "__main__":
    main()
