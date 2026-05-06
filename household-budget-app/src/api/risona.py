"""
りそな銀行 Open Banking API クライアント

りそな銀行の Open API (OAuth 2.0) に対応。
MOCK_MODE=true の場合はダミーデータを返す。

実際の API 利用には以下が必要:
  - りそな Open API ポータルでのアプリ登録
  - client_id / client_secret の取得
  - ユーザーによる OAuth 認可
参照: https://developer.resona-gr.co.jp/

== りそなネットバンキング CSV の使い方 ==
  1. りそなダイレクトにログイン
  2. 「入出金明細照会」→ CSV ダウンロード
  3. RisonaClient.from_csv("ダウンロードしたファイル.csv")
"""

import os
import random
from datetime import date, timedelta

import requests

from src.models.transaction import Account, Transaction, TransactionType


BASE_URL = "https://openapi.resona-gr.co.jp/v1"
TOKEN_URL = "https://openapi.resona-gr.co.jp/auth/token"


class RisonaAPIError(Exception):
    pass


class RisonaClient:
    def __init__(self, client_id: str, client_secret: str, mock: bool = False):
        self.client_id = client_id
        self.client_secret = client_secret
        self.mock = mock
        self._access_token: str | None = None

    # ------------------------------------------------------------------ #
    #  OAuth 2.0 認証                                                      #
    # ------------------------------------------------------------------ #

    def authenticate(self, authorization_code: str) -> None:
        """認可コードをアクセストークンと交換する。"""
        if self.mock:
            self._access_token = "mock_token"
            return

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RisonaAPIError(f"認証失敗: {resp.status_code} {resp.text}")
        self._access_token = resp.json()["access_token"]

    def authenticate_with_refresh_token(self, refresh_token: str) -> str:
        """リフレッシュトークンで新しいアクセストークンを取得する。"""
        if self.mock:
            self._access_token = "mock_token"
            return "mock_refresh"

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RisonaAPIError(f"トークン更新失敗: {resp.status_code} {resp.text}")
        data = resp.json()
        self._access_token = data["access_token"]
        return data.get("refresh_token", refresh_token)

    # ------------------------------------------------------------------ #
    #  API ヘルパー                                                         #
    # ------------------------------------------------------------------ #

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            raise RisonaAPIError("未認証。先に authenticate() を呼び出してください。")
        return {"Authorization": f"Bearer {self._access_token}"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        if resp.status_code != 200:
            raise RisonaAPIError(f"API エラー {path}: {resp.status_code} {resp.text}")
        return resp.json()

    # ------------------------------------------------------------------ #
    #  口座情報取得                                                          #
    # ------------------------------------------------------------------ #

    def get_accounts(self) -> list[Account]:
        if self.mock:
            return [
                Account(
                    account_id="0001234567",
                    account_name="普通預金",
                    bank_name="りそな銀行",
                    balance=350000,
                )
            ]

        data = self._get("/accounts")
        return [
            Account(
                account_id=a["accountId"],
                account_name=a["accountType"],
                bank_name="りそな銀行",
                balance=int(a["balance"]),
            )
            for a in data.get("accounts", [])
        ]

    # ------------------------------------------------------------------ #
    #  取引履歴取得                                                          #
    # ------------------------------------------------------------------ #

    def get_transactions(
        self,
        account_id: str,
        from_date: date,
        to_date: date,
    ) -> list[Transaction]:
        if self.mock:
            return self._mock_transactions(from_date, to_date)

        data = self._get(
            f"/accounts/{account_id}/transactions",
            params={
                "fromDate": from_date.isoformat(),
                "toDate": to_date.isoformat(),
            },
        )
        transactions = []
        for t in data.get("transactions", []):
            tx_type = (
                TransactionType.DEBIT
                if t["transactionType"] == "debit"
                else TransactionType.CREDIT
            )
            transactions.append(
                Transaction(
                    date=date.fromisoformat(t["transactionDate"]),
                    description=t["description"],
                    amount=int(t["amount"]),
                    transaction_type=tx_type,
                    source="risona",
                )
            )
        return transactions

    # ------------------------------------------------------------------ #
    #  モックデータ生成                                                      #
    # ------------------------------------------------------------------ #

    def _mock_transactions(self, from_date: date, to_date: date) -> list[Transaction]:
        random.seed(42)
        samples = [
            ("給与振込", 280000, TransactionType.CREDIT),
            ("イオン", 12500, TransactionType.DEBIT),
            ("東京電力", 8200, TransactionType.DEBIT),
            ("東京ガス", 4100, TransactionType.DEBIT),
            ("NTTドコモ", 7800, TransactionType.DEBIT),
            ("セブンイレブン", 980, TransactionType.DEBIT),
            ("ローソン", 650, TransactionType.DEBIT),
            ("ＪＲ東日本", 5400, TransactionType.DEBIT),
            ("薬局マツモトキヨシ", 2300, TransactionType.DEBIT),
            ("Netflix", 1490, TransactionType.DEBIT),
            ("Amazon Prime", 600, TransactionType.DEBIT),
            ("家賃振込", 80000, TransactionType.DEBIT),
            ("マクドナルド", 850, TransactionType.DEBIT),
            ("スターバックス", 1200, TransactionType.DEBIT),
        ]
        txns: list[Transaction] = []
        delta = (to_date - from_date).days
        for desc, amount, tx_type in samples:
            day_offset = random.randint(0, delta)
            txns.append(
                Transaction(
                    date=from_date + timedelta(days=day_offset),
                    description=desc,
                    amount=amount + random.randint(-500, 500) if tx_type == TransactionType.DEBIT else amount,
                    transaction_type=tx_type,
                    source="risona",
                )
            )
        return sorted(txns, key=lambda t: t.date)

    # ------------------------------------------------------------------ #
    #  CSV インポート（りそなネットバンキング 明細ダウンロード形式）            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def from_csv(
        filepath: str,
        target_year: int | None = None,
        target_month: int | None = None,
    ) -> list[Transaction]:
        """
        りそなネットバンキングからダウンロードした CSV を読み込む。

        CSV 列構成（20列）:
          0  レコード区分
          1  年（ダウンロード日）
          2  月（ダウンロード日）
          3  日（ダウンロード日）
          4  時
          5  分
          6  連絡先名
          7  金融機関名
          8  支店名
          9  口座番号区分
          10 口座種別
          11 口座番号
          12 再送表示
          13 取引名（支払 / 入金）
          14 取扱日付 年
          15 取扱日付 月
          16 取扱日付 日
          17 金額
          18 取引後残高
          19 摘要
          20 コメント（省略可）
        """
        import csv

        transactions: list[Transaction] = []

        # Shift-JIS / UTF-8 どちらも試みる
        for encoding in ("utf-8-sig", "shift_jis", "cp932"):
            try:
                with open(filepath, encoding=encoding, newline="") as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, FileNotFoundError):
                content = None

        if not content:
            raise ValueError(f"CSV ファイルを読み込めません: {filepath}")

        lines = content.splitlines()
        reader = csv.reader(lines)

        header_found = False
        for row in reader:
            if not row:
                continue
            # タイムスタンプ行・ヘッダー行をスキップ
            if row[0] == "レコード区分":
                header_found = True
                continue
            if not header_found:
                continue
            # 明細行のみ処理（合計行等はスキップ）
            if row[0] != "明細":
                continue
            if len(row) < 20:
                continue

            try:
                tx_year = int(row[14])
                tx_month = int(row[15])
                tx_day = int(row[16])
                # 対象年月フィルタ
                if target_year and tx_year != target_year:
                    continue
                if target_month and tx_month != target_month:
                    continue

                amount_str = row[17].replace(",", "").replace("，", "").strip()
                amount = int(amount_str) if amount_str else 0
                description = row[19].strip() if len(row) > 19 else ""
                tx_name = row[13].strip()

                tx_type = (
                    TransactionType.CREDIT if tx_name == "入金" else TransactionType.DEBIT
                )

                transactions.append(
                    Transaction(
                        date=date(tx_year, tx_month, tx_day),
                        description=description,
                        amount=amount,
                        transaction_type=tx_type,
                        source="risona:csv",
                    )
                )
            except (ValueError, IndexError):
                continue  # パース失敗行はスキップ

        return sorted(transactions, key=lambda t: t.date)
