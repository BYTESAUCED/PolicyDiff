# Owner: Mohith
# DiffLambda — temporal + cross-payer + discordance diffs via Bedrock.
#
# Routes handled (API Gateway):
#   GET /api/diffs           → list diffs (filter by drug, payer, severity, page)
#   GET /api/diffs/{diffId}  → get full diff detail
#   GET /api/diffs/feed      → chronological change feed (most recent first)
#
# Also invoked asynchronously by Step Functions State 7 to compute temporal diffs.
#
# When invoked async (no httpMethod), expects:
#   { diffType, policyDocIdOld, policyDocIdNew, drugName, payerName, oldDate, newDate }

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
POLICY_DIFFS_TABLE = os.environ.get("POLICY_DIFFS_TABLE", "PolicyDiffs")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "DrugPolicyCriteria")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250514")

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Content-Type": "application/json",
    }


def _response(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps(body, default=str),
    }


def _convert_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


def _invoke_bedrock(prompt: str, max_tokens: int = 4096) -> str:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read().decode("utf-8"))
    return result["content"][0]["text"]


def _clean_json(text: str) -> str:
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    text = text.strip()
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            return text[i:]
    return text


# ── Async invocation: compute temporal diff ───────────────────────────────

def compute_temporal_diff(event: dict) -> dict:
    """Generate a temporal diff between two policy versions using Bedrock."""
    policy_doc_id_old = event["policyDocIdOld"]
    policy_doc_id_new = event["policyDocIdNew"]
    drug_name = event.get("drugName", "")
    payer_name = event.get("payerName", "")
    old_date = event.get("oldDate", "")
    new_date = event.get("newDate", "")

    criteria_table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    # Fetch old and new criteria
    old_result = criteria_table.query(
        KeyConditionExpression=Key("policyDocId").eq(policy_doc_id_old)
    )
    new_result = criteria_table.query(
        KeyConditionExpression=Key("policyDocId").eq(policy_doc_id_new)
    )

    old_criteria = old_result.get("Items", [])
    new_criteria = new_result.get("Items", [])

    if not old_criteria and not new_criteria:
        logger.warning("No criteria found for either policy version — skipping diff")
        return {"diffId": None, "changes": []}

    # Call Bedrock with the temporal diff prompt
    from extraction.prompts import TEMPORAL_DIFF_PROMPT

    prompt = TEMPORAL_DIFF_PROMPT.format(
        payerName=payer_name,
        drugName=drug_name,
        oldDate=old_date,
        newDate=new_date,
        oldPolicyJson=json.dumps(old_criteria, default=str),
        newPolicyJson=json.dumps(new_criteria, default=str),
    )

    try:
        response_text = _invoke_bedrock(prompt)
        cleaned = _clean_json(response_text)
        diff_result = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Bedrock diff invocation failed: {e}")
        diff_result = {"changes": []}

    changes = diff_result.get("changes", [])

    # Write to PolicyDiffs table
    diff_id = str(uuid.uuid4())
    diffs_table = dynamodb.Table(POLICY_DIFFS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    diff_record = {
        "diffId": diff_id,
        "diffType": "temporal",
        "drugName": drug_name,
        "payerName": payer_name,
        "policyDocIdOld": policy_doc_id_old,
        "policyDocIdNew": policy_doc_id_new,
        "changes": _convert_floats(changes),
        "generatedAt": now,
    }

    # Add indication from first change if available
    if changes:
        diff_record["indicationName"] = changes[0].get("indication", "")

    diffs_table.put_item(Item=diff_record)
    logger.info(f"Wrote temporal diff {diff_id} with {len(changes)} changes")

    return {"diffId": diff_id, "changesCount": len(changes)}


# ── API Gateway routes ────────────────────────────────────────────────────

def list_diffs(params: dict) -> dict:
    """GET /api/diffs — list diffs with optional filters."""
    table = dynamodb.Table(POLICY_DIFFS_TABLE)

    drug = params.get("drug")
    severity = params.get("severity")
    payer = params.get("payer")
    limit = int(params.get("limit", "50"))

    if drug:
        result = table.query(
            IndexName="drugName-diffType-index",
            KeyConditionExpression=Key("drugName").eq(drug),
            Limit=limit,
            ScanIndexForward=False,
        )
    else:
        result = table.scan(Limit=limit)

    items = result.get("Items", [])

    # Client-side filters for severity and payer
    if severity:
        items = [
            item for item in items
            if any(c.get("severity") == severity for c in item.get("changes", []))
        ]
    if payer:
        items = [item for item in items if item.get("payerName") == payer]

    return _response(200, {"items": items, "count": len(items)})


def get_diff(diff_id: str) -> dict:
    """GET /api/diffs/{diffId} — get full diff detail."""
    table = dynamodb.Table(POLICY_DIFFS_TABLE)
    result = table.get_item(Key={"diffId": diff_id})
    item = result.get("Item")
    if not item:
        return _response(404, {"error": f"Diff {diff_id} not found"})
    return _response(200, item)


def get_feed(params: dict) -> dict:
    """GET /api/diffs/feed — chronological change feed, most recent first."""
    table = dynamodb.Table(POLICY_DIFFS_TABLE)
    limit = int(params.get("limit", "20"))

    result = table.scan(Limit=limit)
    items = result.get("Items", [])

    # Sort by generatedAt descending (client-side since Scan)
    items.sort(key=lambda x: x.get("generatedAt", ""), reverse=True)

    # Flatten into feed entries
    feed: list[dict] = []
    for item in items:
        for change in item.get("changes", []):
            feed.append({
                "diffId": item["diffId"],
                "diffType": item.get("diffType"),
                "drugName": item.get("drugName"),
                "payerName": item.get("payerName"),
                "indication": change.get("indication", ""),
                "field": change.get("field", ""),
                "severity": change.get("severity", ""),
                "humanSummary": change.get("humanSummary", ""),
                "oldValue": change.get("oldValue", ""),
                "newValue": change.get("newValue", ""),
                "generatedAt": item.get("generatedAt"),
            })

    # Sort feed by severity priority: breaking > restrictive > relaxed > neutral
    severity_order = {"breaking": 0, "restrictive": 1, "relaxed": 2, "neutral": 3}
    feed.sort(key=lambda x: (x.get("generatedAt", ""), severity_order.get(x.get("severity", ""), 4)), reverse=True)

    return _response(200, {"feed": feed[:limit], "totalChanges": len(feed)})


# ── Router ────────────────────────────────────────────────────────────────

def _get_method_and_path(event: dict) -> tuple[str, str]:
    """Support both REST API v1 and HTTP API v2 event shapes."""
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        ctx = event["requestContext"]["http"]
        return ctx.get("method", ""), event.get("rawPath", "")
    return event.get("httpMethod", ""), event.get("resource", "")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({"event_keys": list(event.keys())}))

    # Check if this is an async invocation from Step Functions (no httpMethod)
    if "httpMethod" not in event and "diffType" in event:
        result = compute_temporal_diff(event)
        return result

    http_method, resource = _get_method_and_path(event)
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": _cors_headers(), "body": ""}

    path_params = event.get("pathParameters") or {}
    if not path_params:
        parts = resource.strip("/").split("/")
        # /api/diffs/{diffId} → parts = ["api", "diffs", "<id>"]
        if len(parts) == 3 and parts[1] == "diffs" and parts[2] != "feed":
            path_params = {"diffId": parts[2]}

    query_params = event.get("queryStringParameters") or {}

    try:
        if http_method == "GET" and resource == "/api/diffs/feed":
            return get_feed(query_params)

        elif http_method == "GET" and resource.startswith("/api/diffs/") and resource != "/api/diffs/feed":
            return get_diff(path_params.get("diffId", ""))

        elif http_method == "GET" and resource == "/api/diffs":
            return list_diffs(query_params)

        else:
            return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return _response(500, {"error": "Internal server error", "detail": str(e)})
