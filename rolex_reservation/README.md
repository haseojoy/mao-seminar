# Rolex Boutique LEXIA — 予約自動申し込みシステム

Playwright (Python) を使って、ロレックスブティック レキシア各店舗の来店予約フォームを自動入力・送信するツールです。

## セットアップ

### 1. Python 依存パッケージのインストール

```bash
cd rolex_reservation
pip install playwright
playwright install chromium
```

### 2. `config.json` の編集

`config.json` に個人情報と申し込み対象店舗を設定してください。

```json
{
  "personal_info": {
    "last_name":       "山田",
    "first_name":      "太郎",
    "last_name_kana":  "ヤマダ",
    "first_name_kana": "タロウ",
    "email":           "taro.yamada@example.com",
    "phone":           "09012345678",
    "gender":          "male"
  },
  "stores": {
    "shinjuku":     { "enabled": true,  ... },
    "ginza":        { "enabled": true,  ... },
    "omotesando":   { "enabled": true,  ... },
    "osaka_hilton": { "enabled": false, ... },
    "nagoya":       { "enabled": false, ... }
  }
}
```

- `enabled: false` にすると、その店舗はデフォルト実行でスキップされます。
- `gender` には `"male"` または `"female"` を指定します。

## 使い方

### 有効な全店舗に申し込む

```bash
python main.py
```

### 指定店舗のみに申し込む

```bash
python main.py --loc ginza
python main.py --loc shinjuku
python main.py --loc omotesando
python main.py --loc osaka_hilton
python main.py --loc nagoya
```

### ドライランモード（送信しない）

フォーム入力・確認画面への遷移まで行い、最終送信はスキップします。動作確認・デバッグに使用します。

```bash
python main.py --dry-run
python main.py --loc ginza --dry-run
```

## スケジュール

- 毎回「**次の土曜日 11:00**」で予約を試みます。
- 実行時点が土曜日の場合は、翌週の土曜日を対象とします。

## スクリーンショット

各ステップ後に `screenshots/` フォルダへ PNG が保存されます。

```
screenshots/
  ginza_2025-06-07_01_loaded.png
  ginza_2025-06-07_02_date_selected.png
  ...
  ginza_2025-06-07_07_submitted.png
```

エラーが発生した場合も `_err_*.png` として保存されます。

## 対応店舗

| キー          | 店舗名            |
|--------------|-----------------|
| shinjuku     | 新宿             |
| ginza        | 銀座             |
| omotesando   | 表参道           |
| osaka_hilton | 大阪ヒルトン      |
| nagoya       | レキシア名古屋    |

## 注意事項

- 本ツールは個人的な予約申し込みの補助を目的としています。
- サイトの HTML 構造が変更された場合、セレクターの調整が必要になる場合があります。
- 申し込み後は必ず確認メールや予約完了画面のスクリーンショットを確認してください。
- 連続送信によるサーバー負荷増大を避けるため、店舗ごとに適切な間隔を置いています。
