from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional
import math


class TransactionType(Enum):
    DEBIT = "debit"       # 支出
    CREDIT = "credit"     # 収入


class Category(Enum):
    # 収入
    INCOME = "収入"
    # 固定費
    HOUSING = "住居費"
    STUDENT_LOAN = "奨学金返済"
    DEBT_REPAYMENT = "借金返済"
    CREDIT_CARD_PAYMENT = "カード引落"
    INSURANCE = "保険料"
    COMMUNICATION = "通信費"
    # 変動費
    FOOD = "食費"
    TRANSPORT = "交通費"
    UTILITIES = "光熱費"
    MEDICAL = "医療費"
    ENTERTAINMENT = "娯楽費"
    CLOTHING = "衣服費"
    EDUCATION = "教育費"
    # 電子マネー・送金
    ELECTRONIC_PAYMENT = "電子マネー"
    TRANSFER = "送金・振替"
    BANK_FEE = "銀行手数料"
    SAVINGS = "貯蓄"
    OTHER = "その他"


# 特定度の高い順に並べること（先にマッチしたものが採用される）
CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.STUDENT_LOAN: ["ニホンガクセイシエンキ", "学生支援機構", "奨学金", "JASSO"],
    Category.DEBT_REPAYMENT: [
        "返済", "ヘンサイ", "サイケンカ", "債権回収", "カドトリプ", "ヨウヘンサイ",
        "消費者金融", "アコム", "プロミス", "アイフル",
    ],
    Category.CREDIT_CARD_PAYMENT: [
        "エポスカード", "SMCC", "三井住友", "ビューカード", "楽天カード",
        "JCB", "UFJカード", "セゾン",
    ],
    Category.HOUSING: [
        "家賃", "ヤチン", "管理費", "修繕", "住宅", "APJ",
    ],
    Category.ELECTRONIC_PAYMENT: [
        "PAYPAY", "PayPay", "ペイペイ", "Suica", "WAON", "nanaco",
        "バンクPOS",
    ],
    Category.BANK_FEE: ["手数料"],
    Category.FOOD: [
        "スーパー", "コンビニ", "レストラン", "食品", "フード", "飲食",
        "マクドナルド", "セブン", "ローソン", "ファミマ", "吉野家",
        "すき家", "サイゼ", "松屋",
    ],
    Category.TRANSPORT: [
        "交通", "電車", "バス", "タクシー", "駐車", "ガソリン",
        "スイカ", "パスモ", "ＪＲ", "JR", "地下鉄", "新幹線",
    ],
    Category.UTILITIES: ["電気", "ガス", "水道", "電力", "東京電力", "東京ガス"],
    Category.MEDICAL: ["病院", "薬局", "クリニック", "医院", "歯科", "調剤"],
    Category.ENTERTAINMENT: [
        "映画", "ゲーム", "動画", "Netflix", "Amazon", "Spotify",
        "音楽", "書籍", "本屋", "カラオケ",
    ],
    Category.CLOTHING: ["ユニクロ", "ZARA", "H&M", "洋服", "アパレル", "靴"],
    Category.EDUCATION: ["塾", "スクール", "学校", "大学", "予備校", "資格"],
    Category.COMMUNICATION: [
        "ドコモ", "au", "ソフトバンク", "楽天モバイル",
        "インターネット", "WiFi", "スマホ",
    ],
    Category.INSURANCE: ["保険", "生命保険", "損保"],
    Category.TRANSFER: ["振込", "送金", "振替"],
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
    source: str = ""
    memo: str = ""

    def __post_init__(self):
        if self.category == Category.OTHER:
            if not self.is_expense:
                self.category = Category.INCOME
            else:
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

    target_amount: int
    deadline: date
    stretch_amount: int = 0
    current_savings: int = 0

    @property
    def remaining_months(self) -> int:
        today = date.today()
        months = (self.deadline.year - today.year) * 12 + (self.deadline.month - today.month)
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
        return this_month_savings >= self.required_monthly_savings

    def forecast(self, monthly_savings: int) -> int:
        return self.current_savings + monthly_savings * self.remaining_months


@dataclass
class DebtRecord:
    """借金の1返済履歴。"""
    date: date
    creditor: str
    amount: int
    principal: int = 0
    interest: int = 0
    memo: str = ""


@dataclass
class DebtSummary:
    """借金全体の現状管理。"""
    creditor: str
    total_borrowed: int
    remaining_balance: int
    monthly_payment: int
    interest_rate: float
    repayment_history: list[DebtRecord] = field(default_factory=list)

    @property
    def monthly_interest(self) -> int:
        return math.ceil(self.remaining_balance * (self.interest_rate / 12))

    @property
    def monthly_principal(self) -> int:
        return max(self.monthly_payment - self.monthly_interest, 0)

    @property
    def months_to_payoff(self) -> int | None:
        if self.monthly_payment <= self.monthly_interest:
            return None
        r = self.interest_rate / 12
        if r == 0:
            return math.ceil(self.remaining_balance / self.monthly_payment)
        n = math.log(
            self.monthly_payment / (self.monthly_payment - self.remaining_balance * r)
        ) / math.log(1 + r)
        return math.ceil(n)

    @property
    def payoff_date(self) -> date | None:
        months = self.months_to_payoff
        if months is None:
            return None
        today = date.today()
        y, m = divmod(today.month - 1 + months, 12)
        return date(today.year + y, m + 1, 1)
