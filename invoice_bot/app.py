"""
Slack Invoice Bot - Webhook Server
Slackでメッセージを受信し、請求書PDFを自動生成して返送するBot
"""
import os
import json
import tempfile
import logging

from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from dotenv import load_dotenv
import anthropic

from invoice_generator import generate_invoice
from slack_client import upload_invoice

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------
# Slack Bolt App 初期化
# -------------------------------------------------------
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)

flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

# -------------------------------------------------------
# Anthropic クライアント
# -------------------------------------------------------
anthropic_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# -------------------------------------------------------
# Claude へ送るプロンプト
# -------------------------------------------------------
PARSE_PROMPT = """\
以下のメッセージから請求書情報をJSONで抽出してください。
JSONのみを返してください（前後の説明文・コードブロック記号も不要）。

{{
  "bill_to": "宛名",
  "tax_included": true または false,
  "items": [{{"name": "品目名", "quantity": 数量（整数）, "unit_price": 単価（整数）}}],
  "due_date": "YYYY-MM-DD または null",
  "invoice_number": "請求書番号 または null",
  "notes": "備考 または null"
}}

ルール：
- tax_included：「税込」と明記されていれば true、それ以外は false
- tax_included=true の場合は unit_price を税込金額のまま入れる（変換しない）

メッセージ：
{message}
"""


# -------------------------------------------------------
# メッセージイベントハンドラ
# -------------------------------------------------------
@slack_app.event("message")
def handle_message(event, client, logger):
    # Bot自身のメッセージは無視（無限ループ防止）
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return

    text = event.get("text", "")
    channel_id = event.get("channel")
    # スレッド返信の場合は同スレッドへ、そうでなければ新スレッド開始
    thread_ts = event.get("thread_ts") or event.get("ts")

    # 「請求書」を含まないメッセージは無視
    if "請求書" not in text:
        return

    logger.info(f"請求書メッセージを受信: channel={channel_id}")

    # 処理中メッセージ
    thinking_res = client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text="⏳ 請求書を生成中です。しばらくお待ちください...",
    )
    thinking_ts = thinking_res["ts"]

    try:
        # 1) Claude で請求書情報を解析
        ai_response = anthropic_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": PARSE_PROMPT.format(message=text),
                }
            ],
        )
        raw_json = ai_response.content[0].text.strip()
        logger.info(f"Claude応答: {raw_json}")

        invoice_data = json.loads(raw_json)

        # 2) PDF 生成
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path, filename = generate_invoice(invoice_data, tmpdir)

            # 3) Slack にアップロード
            upload_invoice(
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts,
                pdf_path=pdf_path,
                filename=filename,
            )

        # 処理中メッセージを削除
        client.chat_delete(channel=channel_id, ts=thinking_ts)

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        client.chat_update(
            channel=channel_id,
            ts=thinking_ts,
            text="❌ 請求書情報の解析に失敗しました。宛名・品目・金額が含まれているか確認してください。",
        )
    except Exception as e:
        logger.error(f"エラー: {e}", exc_info=True)
        client.chat_update(
            channel=channel_id,
            ts=thinking_ts,
            text=f"❌ 請求書の生成中にエラーが発生しました。\n```{e}```",
        )


# -------------------------------------------------------
# Flask ルーティング
# -------------------------------------------------------
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


# -------------------------------------------------------
# エントリーポイント
# -------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
