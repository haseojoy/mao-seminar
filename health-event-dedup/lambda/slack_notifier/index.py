import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

secrets_client = boto3.client("secretsmanager")
_webhook_cache: str | None = None


def _get_webhook_url() -> str:
    global _webhook_cache
    if _webhook_cache:
        return _webhook_cache
    secret = secrets_client.get_secret_value(SecretId=os.environ["SLACK_SECRET_ARN"])
    _webhook_cache = json.loads(secret["SecretString"])["webhook_url"]
    return _webhook_cache


def lambda_handler(event, context):
    webhook_url = _get_webhook_url()

    for record in event.get("Records", []):
        raw = record.get("Sns", {}).get("Message", "{}")
        try:
            health_event = json.loads(raw)
        except json.JSONDecodeError:
            health_event = {"raw": raw}

        _post_to_slack(webhook_url, health_event)

    return {"statusCode": 200}


def _post_to_slack(webhook_url: str, health_event: dict) -> None:
    detail = health_event.get("detail", {})
    event_descs = detail.get("eventDescription", [{}])
    description = (
        event_descs[0].get("latestDescription", "（詳細なし）")
        if isinstance(event_descs, list) and event_descs
        else "（詳細なし）"
    )
    region = health_event.get("region", "N/A")
    event_type = detail.get("eventTypeCode", "N/A")
    category = detail.get("eventTypeCategory", "N/A")
    start_time = detail.get("startTime", "N/A")
    event_arn = detail.get("eventArn", "N/A")

    payload = {
        "text": ":rotating_light: *AWS Health ECS イベント検出*",
        "attachments": [
            {
                "color": _color(category),
                "fields": [
                    {"title": "イベント種別", "value": event_type, "short": True},
                    {"title": "カテゴリ", "value": category, "short": True},
                    {"title": "リージョン", "value": region, "short": True},
                    {"title": "開始時刻", "value": start_time, "short": True},
                    {"title": "説明", "value": description, "short": False},
                    {"title": "Event ARN", "value": f"`{event_arn}`", "short": False},
                ],
                "footer": f"AWS Health | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            }
        ],
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Slack通知失敗: {e}") from e


def _color(category: str) -> str:
    return {"issue": "danger", "scheduledChange": "warning", "accountNotification": "#439FE0"}.get(
        category, "#cccccc"
    )
