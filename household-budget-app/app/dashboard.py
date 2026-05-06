"""
家計管理ダッシュボード

起動コマンド:
  streamlit run app/dashboard.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import defaultdict
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.risona import RisonaClient
from src.models.transaction import MonthlySummary, SavingsGoal, Transaction
from src.main import build_monthly_summary

# ------------------------------------------------------------------ #
#  ページ設定                                                           #
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="家計管理ダッシュボード",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* 全体フォント */
html, body, [class*="css"] { font-family: "Helvetica Neue", "Hiragino Sans", sans-serif; }

/* KPI カード */
.kpi-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 22px 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border-top: 4px solid #2E75B6;
    margin-bottom: 4px;
}
.kpi-card.income  { border-top-color: #38A169; }
.kpi-card.expense { border-top-color: #E53E3E; }
.kpi-card.net-pos { border-top-color: #38A169; }
.kpi-card.net-neg { border-top-color: #E53E3E; }
.kpi-card.rate    { border-top-color: #805AD5; }

.kpi-label { font-size: 12px; color: #718096; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 700; color: #1A202C; }
.kpi-value.green  { color: #38A169; }
.kpi-value.red    { color: #E53E3E; }
.kpi-value.purple { color: #805AD5; }
.kpi-sub   { font-size: 11px; color: #A0AEC0; margin-top: 4px; }

/* セクションヘッダー */
.section-header {
    font-size: 15px; font-weight: 700; color: #2D3748;
    padding: 0 0 8px 0; margin: 24px 0 12px 0;
    border-bottom: 2px solid #E2E8F0;
}

/* 目標カード */
.goal-card {
    background: #EBF8FF;
    border-radius: 12px;
    padding: 18px 22px;
    border-left: 5px solid #2E75B6;
    margin-bottom: 16px;
}
.goal-on-track  { background: #F0FFF4; border-left-color: #38A169; }
.goal-off-track { background: #FFF5F5; border-left-color: #E53E3E; }

/* バッジ */
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600;
}
.badge-income   { background: #C6F6D5; color: #276749; }
.badge-expense  { background: #FED7D7; color: #9B2C2C; }

/* テーブル行ホバー */
.stDataFrame tbody tr:hover { background-color: #EBF4FF !important; }

/* アップロードエリア */
.upload-zone {
    border: 2.5px dashed #CBD5E0;
    border-radius: 16px;
    padding: 48px;
    text-align: center;
    background: #F7FAFC;
    margin: 32px 0;
}
.upload-zone h3 { color: #4A5568; font-size: 20px; margin-bottom: 8px; }
.upload-zone p  { color: #A0AEC0; font-size: 14px; }

/* サイドバー */
section[data-testid="stSidebar"] { background: #1A202C !important; }
section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stNumberInput label { color: #A0AEC0 !important; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
#  カラーパレット（Plotly用）                                            #
# ------------------------------------------------------------------ #

CATEGORY_COLORS = {
    "カード引落":   "#E53E3E",
    "電子マネー":   "#DD6B20",
    "借金返済":    "#E53E3E",
    "奨学金返済":   "#C05621",
    "住居費":      "#2B6CB0",
    "食費":        "#38A169",
    "交通費":      "#319795",
    "光熱費":      "#D69E2E",
    "通信費":      "#553C9A",
    "医療費":      "#B7791F",
    "娯楽費":      "#D53F8C",
    "衣服費":      "#6B46C1",
    "教育費":      "#2C7A7B",
    "保険料":      "#276749",
    "銀行手数料":   "#718096",
    "送金・振替":   "#4A5568",
    "その他":      "#A0AEC0",
}


# ------------------------------------------------------------------ #
#  データ読み込み                                                       #
# ------------------------------------------------------------------ #

def load_transactions(uploaded_file, year: int, month: int) -> list[Transaction]:
    """アップロードされたCSVファイルから取引データを読み込む。"""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    try:
        txns = RisonaClient.from_csv(tmp_path, target_year=year, target_month=month)
    finally:
        os.unlink(tmp_path)
    return txns


# ------------------------------------------------------------------ #
#  UI コンポーネント                                                    #
# ------------------------------------------------------------------ #

def render_upload_screen() -> None:
    st.markdown("""
    <div class="upload-zone">
        <h3>💰 家計管理ダッシュボード</h3>
        <p>りそな銀行の明細CSVをサイドバーからアップロードすると<br>支出分析とレポートが自動生成されます</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">📋 使い方</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**① CSVをダウンロード**\nりそなダイレクト →「入出金明細照会」→ CSVダウンロード")
    with col2:
        st.info("**② アップロード**\nサイドバーの「CSVをアップロード」からファイルを選択")
    with col3:
        st.info("**③ 分析結果を確認**\n収支サマリー・グラフ・AIアドバイスが自動表示されます")

    with st.expander("サンプルデータで試す"):
        sample_path = os.path.join(
            os.path.dirname(__file__), "..", "sample_data", "risona_202604.csv"
        )
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                st.download_button(
                    label="サンプルCSVをダウンロード",
                    data=f,
                    file_name="risona_202604.csv",
                    mime="text/csv",
                )
            st.caption("このサンプルデータを使って動作確認できます（年:2026 / 月:4 を選択してください）")


def render_kpi_cards(summary: MonthlySummary) -> None:
    st.markdown('<div class="section-header">📊 収支サマリー</div>', unsafe_allow_html=True)

    saving_rate = (summary.net / summary.total_income * 100) if summary.total_income > 0 else 0
    net_class = "net-pos" if summary.net >= 0 else "net-neg"
    net_color = "green" if summary.net >= 0 else "red"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card income">
            <div class="kpi-label">収入合計</div>
            <div class="kpi-value green">¥{summary.total_income:,}</div>
            <div class="kpi-sub">{summary.label}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card expense">
            <div class="kpi-label">支出合計</div>
            <div class="kpi-value red">¥{summary.total_expense:,}</div>
            <div class="kpi-sub">{len([t for t in summary.transactions if t.is_expense])} 件</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card {net_class}">
            <div class="kpi-label">収支差額（今月の貯蓄）</div>
            <div class="kpi-value {net_color}">¥{summary.net:,}</div>
            <div class="kpi-sub">{"黒字" if summary.net >= 0 else "赤字"}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="kpi-card rate">
            <div class="kpi-label">貯蓄率</div>
            <div class="kpi-value purple">{saving_rate:.1f}%</div>
            <div class="kpi-sub">目標: 23%以上</div>
        </div>""", unsafe_allow_html=True)


def render_goal_section(goal: SavingsGoal, summary: MonthlySummary) -> None:
    st.markdown('<div class="section-header">🎯 貯蓄目標</div>', unsafe_allow_html=True)

    on_track = goal.on_track(summary.net)
    forecast = goal.forecast(summary.net)
    card_class = "goal-card goal-on-track" if on_track else "goal-card goal-off-track"
    status_icon = "✅" if on_track else "⚠️"
    status_text = "目標ペース達成中" if on_track else "ペース不足 — 節約が必要です"

    col_main, col_stretch = st.columns([2, 1])
    with col_main:
        st.markdown(f"""
        <div class="{card_class}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:13px; color:#4A5568; font-weight:600;">
                        {status_icon} {status_text}
                    </span><br>
                    <span style="font-size:22px; font-weight:700; color:#1A202C;">
                        目標 ¥{goal.target_amount:,}
                    </span>
                    <span style="font-size:13px; color:#718096;"> / {goal.deadline.strftime('%Y年%m月末')}</span>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px; color:#718096;">年末予測</div>
                    <div style="font-size:20px; font-weight:700; color:{'#38A169' if forecast >= goal.target_amount else '#E53E3E'};">
                        ¥{forecast:,}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        progress = min(goal.progress_rate, 1.0)
        st.progress(progress, text=f"達成率 {progress:.1%}  （累計 ¥{goal.current_savings:,}）")

    with col_stretch:
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("今月の貯蓄", f"¥{summary.net:,}", delta=f"{summary.net - goal.required_monthly_savings:+,}")
        with col_b:
            st.metric("必要月次貯蓄", f"¥{goal.required_monthly_savings:,}")

        if goal.stretch_amount:
            st.caption(f"💎 ストレッチ目標 ¥{goal.stretch_amount:,}（月 ¥{goal.stretch_required_monthly:,} 必要）")


def render_charts(summary: MonthlySummary) -> None:
    st.markdown('<div class="section-header">📈 支出分析</div>', unsafe_allow_html=True)

    expense_cats = {
        k: v for k, v in summary.by_category.items() if v > 0 and k != "収入"
    }

    col_left, col_right = st.columns([1, 1])

    # ---- カテゴリ別ドーナツグラフ ----
    with col_left:
        labels = list(expense_cats.keys())
        values = list(expense_cats.values())
        colors = [CATEGORY_COLORS.get(l, "#A0AEC0") for l in labels]

        fig_donut = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.52,
            marker_colors=colors,
            textinfo="label+percent",
            textfont_size=12,
            hovertemplate="<b>%{label}</b><br>¥%{value:,}<br>%{percent}<extra></extra>",
        ))
        fig_donut.update_layout(
            title=dict(text="カテゴリ別支出", font_size=15, x=0),
            showlegend=False,
            margin=dict(t=40, b=0, l=0, r=0),
            height=340,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_donut.add_annotation(
            text=f"¥{summary.total_expense:,}",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#1A202C", family="Helvetica Neue"),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ---- 日別支出バーチャート ----
    with col_right:
        expense_txns = [t for t in summary.transactions if t.is_expense]
        if expense_txns:
            daily: dict[str, int] = defaultdict(int)
            for t in expense_txns:
                daily[t.date.strftime("%m/%d")] += t.amount
            days = sorted(daily.keys())
            amounts = [daily[d] for d in days]

            fig_bar = go.Figure(go.Bar(
                x=days, y=amounts,
                marker_color="#2E75B6",
                hovertemplate="<b>%{x}</b><br>¥%{y:,}<extra></extra>",
            ))
            fig_bar.update_layout(
                title=dict(text="日別支出", font_size=15, x=0),
                xaxis_title="日付",
                yaxis_title="金額（円）",
                margin=dict(t=40, b=40, l=0, r=0),
                height=340,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#E2E8F0"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # ---- カテゴリ別横棒グラフ ----
    sorted_cats = sorted(expense_cats.items(), key=lambda x: x[1])
    fig_hbar = go.Figure(go.Bar(
        x=[v for _, v in sorted_cats],
        y=[k for k, _ in sorted_cats],
        orientation="h",
        marker_color=[CATEGORY_COLORS.get(k, "#A0AEC0") for k, _ in sorted_cats],
        text=[f"¥{v:,}" for _, v in sorted_cats],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>¥%{x:,}<extra></extra>",
    ))
    fig_hbar.update_layout(
        title=dict(text="カテゴリ別支出ランキング", font_size=15, x=0),
        margin=dict(t=40, b=20, l=0, r=60),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#E2E8F0"),
    )
    st.plotly_chart(fig_hbar, use_container_width=True)


def render_transaction_table(summary: MonthlySummary) -> None:
    st.markdown('<div class="section-header">📋 取引明細</div>', unsafe_allow_html=True)

    col_filter1, col_filter2, _ = st.columns([1, 1, 2])
    with col_filter1:
        filter_type = st.selectbox("収支", ["すべて", "支出のみ", "収入のみ"])
    with col_filter2:
        categories = sorted({t.category.value for t in summary.transactions})
        filter_cat = st.selectbox("カテゴリ", ["すべて"] + categories)

    txns = summary.transactions
    if filter_type == "支出のみ":
        txns = [t for t in txns if t.is_expense]
    elif filter_type == "収入のみ":
        txns = [t for t in txns if not t.is_expense]
    if filter_cat != "すべて":
        txns = [t for t in txns if t.category.value == filter_cat]

    rows = []
    for t in txns:
        rows.append({
            "日付":     t.date.strftime("%m/%d"),
            "摘要":     t.description,
            "カテゴリ": t.category.value,
            "収支":     "収入" if not t.is_expense else "支出",
            "金額":     t.amount,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "金額": st.column_config.NumberColumn(format="¥%d"),
                "収支": st.column_config.TextColumn(width="small"),
            },
        )
        st.caption(f"{len(df)} 件表示中")


def render_ai_analysis(summary: MonthlySummary, goal: SavingsGoal) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    st.markdown('<div class="section-header">🤖 AI 支出分析・アドバイス</div>', unsafe_allow_html=True)

    if not api_key:
        st.info(
            "AI分析を有効にするには `.env` に `ANTHROPIC_API_KEY` を設定してください。\n\n"
            "設定後はここに Claude によるパーソナライズされたアドバイスが表示されます。",
            icon="💡",
        )
        return

    if st.button("AIに分析してもらう", type="primary"):
        with st.spinner("Claude が分析中..."):
            try:
                from src.analysis.analyzer import ExpenseAnalyzer
                analyzer = ExpenseAnalyzer(api_key=api_key)
                result = analyzer.analyze(summary, goal=goal)
                st.session_state["ai_result"] = result
            except Exception as e:
                st.error(f"分析中にエラーが発生しました: {e}")

    if "ai_result" in st.session_state:
        st.markdown(
            f'<div style="background:#EBF8FF; border-radius:12px; padding:20px; '
            f'border-left:4px solid #2E75B6; white-space:pre-wrap; font-size:14px; line-height:1.7;">'
            f'{st.session_state["ai_result"]}</div>',
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------ #
#  サイドバー                                                           #
# ------------------------------------------------------------------ #

def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## 💰 家計管理")
        st.markdown("---")

        uploaded_file = st.file_uploader(
            "りそな銀行 CSV",
            type=["csv"],
            help="りそなネットバンキング →「入出金明細照会」からダウンロードしたCSVファイル",
        )

        st.markdown("**対象期間**")
        col1, col2 = st.columns(2)
        today = date.today()
        with col1:
            year = st.selectbox("年", list(range(2024, 2028)), index=list(range(2024, 2028)).index(today.year))
        with col2:
            month = st.selectbox("月", list(range(1, 13)), index=today.month - 2)

        st.markdown("---")
        st.markdown("**🎯 貯蓄目標**")
        goal_target = st.number_input("目標金額（円）", value=1_000_000, step=100_000, min_value=0)
        goal_stretch = st.number_input("ストレッチ目標（円）", value=1_500_000, step=100_000, min_value=0)
        goal_deadline = st.date_input("達成期限", value=date(2026, 12, 31))
        current_savings = st.number_input("累計貯蓄額（円）", value=0, step=10_000, min_value=0,
                                          help="これまでの累計貯蓄額を入力してください")

        st.markdown("---")
        st.caption("Made with Claude AI")

    goal = SavingsGoal(
        target_amount=goal_target,
        deadline=goal_deadline,
        stretch_amount=goal_stretch,
        current_savings=current_savings,
    )
    return uploaded_file, year, month, goal


# ------------------------------------------------------------------ #
#  メイン                                                               #
# ------------------------------------------------------------------ #

def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    uploaded_file, year, month, goal = render_sidebar()

    if uploaded_file is None:
        st.title("💰 家計管理ダッシュボード")
        render_upload_screen()
        return

    with st.spinner("CSVを読み込み中..."):
        transactions = load_transactions(uploaded_file, year, month)

    if not transactions:
        st.warning(f"{year}年{month:02d}月のデータが見つかりませんでした。年・月の選択を確認してください。")
        return

    summary = build_monthly_summary(year, month, transactions)

    # ヘッダー
    st.markdown(
        f'<h1 style="margin-bottom:4px;">💰 {summary.label} 家計管理レポート</h1>'
        f'<p style="color:#718096; margin-bottom:24px;">{uploaded_file.name} · {len(transactions)} 件</p>',
        unsafe_allow_html=True,
    )

    render_kpi_cards(summary)
    st.markdown("<br>", unsafe_allow_html=True)
    render_goal_section(goal, summary)
    render_charts(summary)
    render_transaction_table(summary)
    render_ai_analysis(summary, goal)


if __name__ == "__main__":
    main()
