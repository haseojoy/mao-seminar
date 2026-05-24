"""
Slack クライアントユーティリティ
請求書PDFをSlackチャンネルにアップロードする
"""
import logging

logger = logging.getLogger(__name__)


def upload_invoice(
    client,
    channel_id: str,
    thread_ts: str,
    pdf_path: str,
    filename: str,
) -> dict:
    """
    PDFファイルをSlackにアップロードして、指定チャンネル（スレッド）に投稿する

    Args:
        client: slack_bolt が提供する WebClient インスタンス
        channel_id: 送信先チャンネルID
        thread_ts: スレッドのタイムスタンプ（スレッド返信にする場合）
        pdf_path: アップロードするPDFの絶対パス
        filename: Slackに表示するファイル名
    Returns:
        Slack APIレスポンス
    """
    logger.info(f"PDFアップロード開始: {filename} → {channel_id}")

    with open(pdf_path, "rb") as f:
        response = client.files_upload_v2(
            channel=channel_id,
            file=f,
            filename=filename,
            initial_comment="✅ 請求書PDFを生成しました！",
            thread_ts=thread_ts,
        )

    logger.info(f"PDFアップロード完了: {filename}")
    return response
