import json
import os
import hashlib
from datetime import datetime, timedelta, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
TTL_DAYS = 60  # 2 months


def _make_event_key(body: dict) -> str:
    arn = body.get("detail", {}).get("eventArn") or body.get("event_key")
    if arn:
        return arn
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _extract_description(body: dict) -> str:
    event_desc = body.get("detail", {}).get("eventDescription", [{}])
    if isinstance(event_desc, list) and event_desc:
        return event_desc[0].get("latestDescription", "")
    return ""


def _servicenow_fields(body: dict, event_key: str, description: str) -> dict:
    detail = body.get("detail", {})
    category = detail.get("eventTypeCategory", "unknown")
    event_type = detail.get("eventTypeCode", "N/A")
    region = body.get("region", "N/A")
    start_time = detail.get("startTime", "N/A")
    event_arn = detail.get("eventArn", event_key)

    # 1行目をタイトルに使う（長すぎる場合は切る）
    first_line = description.split("\n")[0][:100] if description else event_type
    short_description = f"[AWS Health ECS] {first_line} ({region})"

    sn_description = "\n".join([
        f"■ イベント種別 : {event_type}",
        f"■ カテゴリ     : {category}",
        f"■ リージョン   : {region}",
        f"■ 開始時刻     : {start_time}",
        f"■ Event ARN    : {event_arn}",
        "",
        "■ 詳細:",
        description or "（詳細なし）",
    ])

    # カテゴリで影響度・緊急度をマッピング
    impact_map = {"issue": "1", "scheduledChange": "2", "accountNotification": "3"}
    urgency_map = {"issue": "2", "scheduledChange": "3", "accountNotification": "3"}

    return {
        "short_description": short_description,
        "description": sn_description,
        "category": "Infrastructure",
        "impact": impact_map.get(category, "2"),
        "urgency": urgency_map.get(category, "3"),
        "assignment_group": "AWS Operations",
    }


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "Invalid JSON body"})

    if not body:
        return _resp(400, {"error": "Empty body"})

    event_key = _make_event_key(body)
    table = dynamodb.Table(TABLE_NAME)

    existing = table.get_item(Key={"event_key": event_key}).get("Item")
    if existing:
        return _resp(
            200,
            {
                "is_new": False,
                "event_key": event_key,
                "message": "既知のイベントです。報告は不要です。",
                "first_seen": existing["first_seen"],
            },
        )

    now = datetime.now(timezone.utc)
    ttl = int((now + timedelta(days=TTL_DAYS)).timestamp())
    table.put_item(
        Item={
            "event_key": event_key,
            "first_seen": now.isoformat(),
            "event_data": json.dumps(body, ensure_ascii=False),
            "ttl": ttl,
        }
    )

    detail = body.get("detail", {})
    description = _extract_description(body)

    return _resp(
        200,
        {
            "is_new": True,
            "event_key": event_key,
            "message": "新規イベントです。起票をお願いします。",
            "ticket_data": {
                "title": description.split("\n")[0][:100] if description else detail.get("eventTypeCode", "AWS Health ECS Event"),
                "severity": detail.get("eventTypeCategory", "unknown"),
                "region": body.get("region", "unknown"),
                "service": detail.get("service", "ECS"),
                "event_arn": detail.get("eventArn", event_key),
                "start_time": detail.get("startTime", now.isoformat()),
                "description": description,
                "raw": body,
            },
            "servicenow": _servicenow_fields(body, event_key, description),
        },
    )


def _resp(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
