from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional
import math


class TransactionType(Enum):
    DEBIT = "debit"       # 支出
    CREDIT = "credit"     # 収入


class Category(Enum):
    FOOD = "食費"
    TRANSPORT = "交通費"
    UTILITIES = "光熱費"
    HOUSING = "住居費"
    MEDICAL = "医療費"
    ENTERTAINMENT = "娯楽費"
    CLOTHING = "衣服費"
    EDUCATION = "教育費"
    COMMUNICATION = "通信費"
    INSURANCE = "保険料"
    SAVINGS = "貯蓄"
    INCOME = "収入"
    OTHER = "その他"


# カテゴリ自動判定キーワードマップ
CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.FOOD: ["スーパー", "コンビニ", "レストラン", "食品", "フード", "飲食", "マクドナルド",
                    "セブン", "ローソン", "ファミマ", "吉野家", "すき家", "サイゼ", "松屋"],
    Category.TRANSPORT: ["交通", "電車", "バス", "タクシー", "駐車", "ガソリン", "スイカ",
                         "パスモ", "ＪＲ", "JR", "地下鉄", "新幹線"],
    Category.UTILITIES: ["電気", "ガス", "水道", "電力", "東京電力", "東京ガス"],
    Category.HOUSING: ["家賃", "管理費", "修繕", "住宅"],
    Category.MEDICAL: ["病院", "薬局", "クリニック", "医院", "歯科", "調剤"],
    Category.ENTERTAINMENT: ["映画", "ゲーム", "動画", "Netflix", "Amazon", "Spotify",
                             "音楽", "書籍", "本屋", "カラオケ"],
    Category.CLOTHING: ["ユニクロ", "ZARA", "H&M", "洋服", "アパレル", "靴"],
    Category.EDUCATION: ["塾", "スクール", "学校", "大学", "予備校", "資格"],
    Category.COMMUNICATION: ["ドコモ", "au", "ソフトバンク", "楽天モバイル", "インターネット",
                              "WiFi", "スマホ"],
    Category.INSURANCE: ["保険", "生命保険", "損保"],
}


def auto_categorize(description: str) -> Category:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in description for kw in keywords):
            return category
    return Category.OTHER


@dataclass
class Transaction:
    date: date
    description: str
    amount: int                         # 金額（円）
    transaction_type: TransactionType
    category: Category = field(default=Category.OTHER)
    source: str = ""                    # "risona" or "credit_card"
    memo: str = ""

    def __post_init__(self):
        if self.category == Category.OTHER:
            self.category = auto_categorize(self.description)

    @property
    def is_expense(self) -> bool:
        return self.transaction_type == TransactionType.DEBIT


@dataclass
class Account:
    account_id: str
    account_name: str
    bank_name: str
    balance: int
    currency: str = "JPY"


@dataclass
class MonthlySummary:
    year: int
    month: int
    total_income: int
    total_expense: int
    by_category: dict[str, int]
    transactions: list[Transaction]

    @property
    def net(self) -> int:
        return self.total_income - self.total_expense

    @property
    def label(self) -> str:
        return f"{self.year}年{self.month:02d}月"


@dataclass
class SavingsGoal:
    """年間貯蓄目標の管理クラス。"""

    target_amount: int          # 目標金額（円）
    deadline: date              # 達成期限
    stretch_amount: int = 0     # ストレッチ目標（円）
    current_savings: int = 0    # これまでの累計貯蓄額（円）

    @property
    def remaining_months(self) -> int:
        today = date.today()
        months = (self.deadline.year - today.year) * 12 + (self.deadline.month - today.month)
        # 月末締めなので当月を含める
        return max(months + 1, 1)

    @property
    def remaining_amount(self) -> int:
        return max(self.target_amount - self.current_savings, 0)

    @property
    def required_monthly_savings(self) -> int:
        return math.ceil(self.remaining_amount / self.remaining_months)

    @property
    def stretch_remaining_amount(self) -> int:
        if not self.stretch_amount:
            return 0
        return max(self.stretch_amount - self.current_savings, 0)

    @property
    def stretch_required_monthly(self) -> int:
        if not self.stretch_amount:
            return 0
        return math.ceil(self.stretch_remaining_amount / self.remaining_months)

    @property
    def progress_rate(self) -> float:
        if not self.target_amount:
            return 0.0
        return min(self.current_savings / self.target_amount, 1.0)

    def on_track(self, this_month_savings: int) -> bool:
        """今月の貯蓄額が目標達成ペースを満たしているか。"""
        return this_month_savings >= self.required_monthly_savings

    def forecast(self, monthly_savings: int) -> int:
        """現在の月次貯蓄ペースで年末に到達できる金額を推計。"""
        return self.current_savings + monthly_savings * self.remaining_months


@dataclass
class DebtRecord:
    """借金の1返済履歴。"""
    date: date
    creditor: str       # 貸主（消費者金融名、カード会社等）
    amount: int         # 返済額（円）
    principal: int = 0  # うち元本返済分（わかれば）
    interest: int = 0   # うち利息分（わかれば）
    memo: str = ""


@dataclass
class DebtSummary:
    """借金全体の現状管理。"""
    creditor: str           # 貸主
    total_borrowed: int     # 借入総額（円）
    remaining_balance: int  # 残債（円）
    monthly_payment: int    # 月々の返済額（円）
    interest_rate: float    # 年利（例: 0.18 = 18%）
    repayment_history: list[DebtRecord] = field(default_factory=list)

    @property
    def monthly_interest(self) -> int:
        """今月の利息概算（残債 × 月利）。"""
        return math.ceil(self.remaining_balance * (self.interest_rate / 12))

    @property
    def monthly_principal(self) -> int:
        """今月の元本返済概算。"""
        return max(self.monthly_payment - self.monthly_interest, 0)

    @property
    def months_to_payoff(self) -> int | None:
        """完済までの残り月数（定額返済の場合の概算）。"""
        if self.monthly_payment <= self.monthly_interest:
            return None  # 利息以下の返済では完済不可
        r = self.interest_rate / 12
        if r == 0:
            return math.ceil(self.remaining_balance / self.monthly_payment)
        import math as _m
        n = _m.log(self.monthly_payment / (self.monthly_payment - self.remaining_balance * r)) / _m.log(1 + r)
        return math.ceil(n)

    @property
    def payoff_date(self) -> date | None:
        months = self.months_to_payoff
        if months is None:
            return None
        today = date.today()
        y, m = divmod(today.month - 1 + months, 12)
        return date(today.year + y, m + 1, 1)
