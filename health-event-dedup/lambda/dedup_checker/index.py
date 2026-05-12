import json
import os
import time
import hashlib
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
TTL_DAYS = 60  # 2 months


def _make_event_key(body: dict) -> str:
    """AWS Health event の eventArn を優先し、なければ内容全体のハッシュ値を使う."""
    arn = body.get("detail", {}).get("eventArn") or body.get("event_key")
    if arn:
        return arn
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
                "message": "duplicate — already tracked",
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

    return _resp(
        200,
        {
            "is_new": True,
            "event_key": event_key,
            "message": "new event — create ticket",
            "ticket_data": {
                "title": _extract_title(body),
                "severity": body.get("detail", {}).get("eventTypeCategory", "unknown"),
                "region": body.get("region", "unknown"),
                "service": body.get("detail", {}).get("service", "ECS"),
                "event_arn": body.get("detail", {}).get("eventArn", event_key),
                "start_time": body.get("detail", {}).get("startTime", now.isoformat()),
                "description": _extract_description(body),
                "raw": body,
            },
        },
    )


def _extract_title(body: dict) -> str:
    detail = body.get("detail", {})
    event_desc = detail.get("eventDescription", [{}])
    if isinstance(event_desc, list) and event_desc:
        return event_desc[0].get("latestDescription", "AWS Health ECS Event")
    return detail.get("eventTypeCode", "AWS Health ECS Event")


def _extract_description(body: dict) -> str:
    event_desc = body.get("detail", {}).get("eventDescription", [{}])
    if isinstance(event_desc, list) and event_desc:
        return event_desc[0].get("latestDescription", "")
    return ""


def _resp(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
