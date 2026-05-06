"""
クレジットカード API クライアント

複数の国内カード会社に対応した汎用クライアント。
PROVIDER に応じて適切なエンドポイントを使用する。

対応予定プロバイダー:
  - smbc   : 三井住友カード (Vpass API)
  - rakuten: 楽天カード
  - jcb    : JCB (MyJCB API)
  - generic: 汎用 (CSV インポートも可)

実際の API 利用には各社のデベロッパー登録が必要。
MOCK_MODE=true の場合はダミーデータを返す。
"""

import random
from datetime import date, timedelta

import requests

from src.models.transaction import Transaction, TransactionType


PROVIDER_CONFIG: dict[str, dict] = {
    "smbc": {
        "token_url": "https://api.smbc-card.com/oauth2/token",
        "base_url": "https://api.smbc-card.com/v1",
        "transactions_path": "/cardusages",
    },
    "rakuten": {
        "token_url": "https://api.rakuten-card.co.jp/oauth2/token",
        "base_url": "https://api.rakuten-card.co.jp/v2",
        "transactions_path": "/transactions",
    },
    "jcb": {
        "token_url": "https://api.myjcb.jp/oauth2/token",
        "base_url": "https://api.myjcb.jp/v1",
        "transactions_path": "/usage",
    },
}


class CreditCardAPIError(Exception):
    pass


class CreditCardClient:
    def __init__(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        mock: bool = False,
    ):
        if provider not in PROVIDER_CONFIG and not mock:
            raise ValueError(f"未対応のプロバイダー: {provider}。対応: {list(PROVIDER_CONFIG)}")
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.mock = mock
        self._access_token: str | None = None
        self._config = PROVIDER_CONFIG.get(provider, {})

    # ------------------------------------------------------------------ #
    #  OAuth 2.0 認証                                                      #
    # ------------------------------------------------------------------ #

    def authenticate(self, authorization_code: str) -> None:
        if self.mock:
            self._access_token = "mock_cc_token"
            return

        resp = requests.post(
            self._config["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise CreditCardAPIError(f"CC認証失敗: {resp.status_code} {resp.text}")
        self._access_token = resp.json()["access_token"]

    def authenticate_with_refresh_token(self, refresh_token: str) -> str:
        if self.mock:
            self._access_token = "mock_cc_token"
            return "mock_cc_refresh"

        resp = requests.post(
            self._config["token_url"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise CreditCardAPIError(f"CCトークン更新失敗: {resp.status_code} {resp.text}")
        data = resp.json()
        self._access_token = data["access_token"]
        return data.get("refresh_token", refresh_token)

    # ------------------------------------------------------------------ #
    #  利用明細取得                                                          #
    # ------------------------------------------------------------------ #

    def get_transactions(self, from_date: date, to_date: date) -> list[Transaction]:
        if self.mock:
            return self._mock_transactions(from_date, to_date)

        if not self._access_token:
            raise CreditCardAPIError("未認証。先に authenticate() を呼び出してください。")

        resp = requests.get(
            f"{self._config['base_url']}{self._config['transactions_path']}",
            headers={"Authorization": f"Bearer {self._access_token}"},
            params={"from": from_date.isoformat(), "to": to_date.isoformat()},
            timeout=30,
        )
        if resp.status_code != 200:
            raise CreditCardAPIError(f"明細取得失敗: {resp.status_code} {resp.text}")

        return self._parse_response(resp.json())

    def _parse_response(self, data: dict) -> list[Transaction]:
        """各プロバイダーのレスポンス形式を統一フォーマットに変換する。"""
        txns = []
        items = data.get("transactions") or data.get("cardUsages") or data.get("usages", [])
        for item in items:
            txns.append(
                Transaction(
                    date=date.fromisoformat(item.get("date") or item.get("usageDate")),
                    description=item.get("description") or item.get("shopName") or "",
                    amount=abs(int(item.get("amount") or item.get("usageAmount", 0))),
                    transaction_type=TransactionType.DEBIT,
                    source=f"credit_card:{self.provider}",
                )
            )
        return txns

    # ------------------------------------------------------------------ #
    #  CSV インポート (スクレイピング不要の代替手段)                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def from_csv(filepath: str, provider: str = "csv") -> list[Transaction]:
        """
        カード会社サイトからダウンロードした CSV を読み込む。
        列順: 利用日, 店名/内容, 金額(円)
        """
        import csv

        txns = []
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                txns.append(
                    Transaction(
                        date=date.fromisoformat(list(row.values())[0]),
                        description=list(row.values())[1],
                        amount=int(list(row.values())[2].replace(",", "").replace("円", "")),
                        transaction_type=TransactionType.DEBIT,
                        source=f"credit_card:{provider}",
                    )
                )
        return txns

    # ------------------------------------------------------------------ #
    #  モックデータ生成                                                      #
    # ------------------------------------------------------------------ #

    def _mock_transactions(self, from_date: date, to_date: date) -> list[Transaction]:
        random.seed(99)
        samples = [
            ("ユニクロ", 4900),
            ("Amazon.co.jp", 3200),
            ("サイゼリヤ", 1200),
            ("スターバックス", 680),
            ("Spotify", 980),
            ("吉野家", 550),
            ("ビックカメラ", 18000),
            ("ファミリーマート", 450),
            ("駿台予備校", 35000),
            ("ドラッグストア", 1850),
        ]
        txns = []
        delta = (to_date - from_date).days
        for desc, amount in samples:
            day_offset = random.randint(0, delta)
            txns.append(
                Transaction(
                    date=from_date + timedelta(days=day_offset),
                    description=desc,
                    amount=amount + random.randint(-200, 200),
                    transaction_type=TransactionType.DEBIT,
                    source=f"credit_card:{self.provider}",
                )
            )
        return sorted(txns, key=lambda t: t.date)
