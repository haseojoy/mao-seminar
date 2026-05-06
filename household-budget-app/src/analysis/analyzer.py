"""
Claude AI による支出分析・フィードバックモジュール

Anthropic の Claude API を使い、月次支出データを分析して
日本語でのパーソナライズされたアドバイスを生成する。
"""

from __future__ import annotations

import anthropic

from src.models.transaction import MonthlySummary


class ExpenseAnalyzer:
    def __init__(self, api_key: str, model: str = "claude-opus-4-7"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, summary: MonthlySummary) -> str:
        """月次サマリーを分析し、日本語のフィードバックテキストを返す。"""
        prompt = self._build_prompt(summary)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=(
                "あなたは日本の家計管理の専門家です。"
                "ユーザーの月次支出データを分析し、具体的で実践的なアドバイスを日本語で提供してください。"
                "アドバイスは温かみがあり、批判的にならないよう心がけてください。"
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text

    def analyze_trend(
        self, summaries: list[MonthlySummary], months: int = 3
    ) -> str:
        """複数月のサマリーを比較してトレンド分析を行う。"""
        if not summaries:
            return "分析に必要なデータがありません。"

        recent = summaries[-months:] if len(summaries) >= months else summaries
        prompt = self._build_trend_prompt(recent)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=(
                "あなたは日本の家計管理の専門家です。"
                "複数月の支出トレンドを分析し、改善点と良い点を具体的に指摘してください。"
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text

    # ------------------------------------------------------------------ #
    #  プロンプト構築                                                       #
    # ------------------------------------------------------------------ #

    def _build_prompt(self, summary: MonthlySummary) -> str:
        expense_lines = "\n".join(
            f"  - {cat}: {amount:,}円"
            for cat, amount in sorted(summary.by_category.items(), key=lambda x: -x[1])
            if amount > 0 and cat != "収入"
        )

        top_txns = sorted(
            [t for t in summary.transactions if t.is_expense],
            key=lambda t: -t.amount,
        )[:5]
        top_lines = "\n".join(
            f"  - {t.description}: {t.amount:,}円 ({t.date})"
            for t in top_txns
        )

        saving_rate = (
            (summary.net / summary.total_income * 100) if summary.total_income > 0 else 0
        )

        return f"""
{summary.label}の家計データを分析してください。

## 収支概要
- 収入合計: {summary.total_income:,}円
- 支出合計: {summary.total_expense:,}円
- 収支差額: {summary.net:,}円（貯蓄率: {saving_rate:.1f}%）

## カテゴリ別支出
{expense_lines}

## 高額支出 TOP5
{top_lines}

## お願いする分析内容
1. 今月の支出の総合評価（100点満点でスコアをつけてください）
2. 支出バランスについての評価
3. 節約できる可能性がある項目の具体的な提案
4. 来月に向けての具体的な行動アドバイス（3つ）
5. 総合的なコメント

わかりやすく、箇条書きを使って回答してください。
""".strip()

    def _build_trend_prompt(self, summaries: list[MonthlySummary]) -> str:
        month_sections = []
        for s in summaries:
            cats = "\n".join(
                f"    {cat}: {amount:,}円"
                for cat, amount in sorted(s.by_category.items(), key=lambda x: -x[1])
                if amount > 0 and cat != "収入"
            )
            month_sections.append(
                f"### {s.label}\n"
                f"  収入: {s.total_income:,}円 / 支出: {s.total_expense:,}円 / 差額: {s.net:,}円\n"
                f"{cats}"
            )

        return f"""
以下は過去{len(summaries)}ヶ月の家計データです。

{"".join(month_sections)}

## 分析してください
1. 支出トレンドの評価（増加・減少傾向のカテゴリ）
2. 改善が見られた点
3. 注意が必要な点
4. 3ヶ月を通じた節約目標の提案
""".strip()
