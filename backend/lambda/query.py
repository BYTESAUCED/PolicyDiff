# Owner: Mohith
# QueryLambda — natural language query against extracted policy criteria via Bedrock.
#
# Routes handled:
#   POST /api/query           → submit NL query, returns instant answer
#   GET  /api/query/{queryId} → fetch a past query result
#   GET  /api/queries         → list recent queries (last 20)
#
# Expected input (POST /api/query):
#   body: { "queryText": str }
#
# Expected output:
#   { "queryId": str, "queryType": str, "answer": str, "citations": [...], "responseTimeMs": int }

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
QUERY_LOG_TABLE = os.environ.get("QUERY_LOG_TABLE", "")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "")
POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "")
POLICY_DIFFS_TABLE = os.environ.get("POLICY_DIFFS_TABLE", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Prompt templates
QUERY_CLASSIFICATION_AND_SYNTHESIS = """\
You are answering questions about medical benefit drug coverage policies for \
pharmacy consultants at Anton RX.

Available payers in database: {payerList}
Available drugs: {drugList}

User question: {queryText}

Step 1 — Classify the query:
- coverage_check: "Which plans cover Drug X?"
- criteria_lookup: "What does Payer Z require for Drug X?"
- cross_payer_compare: "Compare X across payers" or "differences between..."
- change_tracking: "What changed..." or "how did policy evolve..."
- discordance_check: "Does medical differ from pharmacy for..."

Step 2 — Synthesize an answer from the retrieved data below.

RULES:
- Cite specific payer, document title, and effective date for every factual claim.
- If data is incomplete (e.g., only 2 of 5 payers have been ingested), state \
this explicitly.
- Never speculate about policies not present in the retrieved data.
- For comparison queries, structure the answer as a markdown table.
- Highlight the most clinically significant differences: step therapy count \
differences, biosimilar preference switches, prescriber requirement discrepancies.
- Keep answer under 400 words unless the query requires a full table.

Retrieved policy data:
{policyData}

Return JSON:
{{
  "queryType": string,
  "answer": string (markdown formatted),
  "citations": [{{ "payer": string, "documentTitle": string, \
"effectiveDate": string, "excerpt": string }}],
  "dataCompleteness": "complete|partial|insufficient"
}}"""


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json",
    }


def _response(status: int, body: Any) -> dict:
    return {
        "statusCode": status,
        "headers": _cors_headers(),
        "body": json.dumps(body, default=str),
    }


def _invoke_bedrock(prompt: str, max_tokens: int = 4096) -> str:
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": 0.2,
        },
    })
    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read().decode("utf-8"))
    return result["output"]["message"]["content"][0]["text"]


def _clean_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    text = text.strip()
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            return text[i:]
    return text


def _get_available_metadata() -> tuple[list[str], list[str]]:
    """Get lists of available payers and drugs from DynamoDB."""
    policy_table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
    criteria_table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    # Scan for available payers
    payers = set()
    drugs = set()

    try:
        result = policy_table.scan(
            ProjectionExpression="payerName",
            Limit=100,
        )
        for item in result.get("Items", []):
            if item.get("payerName"):
                payers.add(item["payerName"])
    except Exception:
        pass

    try:
        result = criteria_table.scan(
            ProjectionExpression="drugName",
            Limit=200,
        )
        for item in result.get("Items", []):
            if item.get("drugName"):
                drugs.add(item["drugName"])
    except Exception:
        pass

    return sorted(payers), sorted(drugs)


def _retrieve_policy_data(query_text: str) -> str:
    """Retrieve relevant policy data from DynamoDB based on query text.

    Heuristic: scan for drug names and payer names in the query,
    then fetch matching criteria records.
    """
    criteria_table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    # Known drug names to look for in queries
    common_drugs = [
        "infliximab", "adalimumab", "ustekinumab", "rituximab",
        "remicade", "inflectra", "avsola", "renflexis", "humira",
        "stelara", "rituxan",
    ]
    common_payers = [
        "unitedhealth", "uhc", "united", "aetna", "cigna", "anthem",
    ]

    query_lower = query_text.lower()

    # Find mentioned drugs
    mentioned_drugs = [d for d in common_drugs if d in query_lower]

    # Find mentioned payers
    mentioned_payers = [p for p in common_payers if p in query_lower]

    all_records: list[dict] = []

    # Fetch by drug name using GSI
    for drug in mentioned_drugs:
        # Normalize to generic name
        drug_map = {
            "remicade": "infliximab", "inflectra": "infliximab",
            "avsola": "infliximab", "renflexis": "infliximab",
            "humira": "adalimumab", "stelara": "ustekinumab",
            "rituxan": "rituximab",
        }
        generic = drug_map.get(drug, drug)

        try:
            result = criteria_table.query(
                IndexName="drugName-payerName-index",
                KeyConditionExpression=Key("drugName").eq(generic),
                Limit=50,
            )
            all_records.extend(result.get("Items", []))
        except Exception as e:
            logger.warning(json.dumps({"warning": "criteria_query_failed", "drug": generic, "detail": str(e)}))

    # If no drug-specific results, do a broad scan
    if not all_records:
        try:
            result = criteria_table.scan(Limit=50)
            all_records = result.get("Items", [])
        except Exception as e:
            logger.warning(json.dumps({"warning": "criteria_scan_failed", "detail": str(e)}))

    # Filter by mentioned payers if applicable
    if mentioned_payers:
        payer_map = {
            "unitedhealth": "UnitedHealthcare", "uhc": "UnitedHealthcare",
            "united": "UnitedHealthcare", "aetna": "Aetna",
            "cigna": "Cigna", "anthem": "Anthem",
        }
        target_payers = {payer_map.get(p, p) for p in mentioned_payers}
        all_records = [r for r in all_records if r.get("payerName") in target_payers] or all_records

    return json.dumps(all_records[:20], default=str)


# ── Route handlers ────────────────────────────────────────────────────────

def submit_query(body: dict, event: dict) -> dict:
    """POST /api/query — run NL query, return answer immediately."""
    query_text = body.get("queryText", "").strip()
    if not query_text:
        return _response(400, {"error": "queryText is required"})
    if len(query_text) > 2000:
        return _response(400, {"error": "queryText exceeds maximum length of 2000 characters"})

    start_time = time.time()
    query_id = str(uuid.uuid4())

    # 1. Get available metadata
    payers, drugs = _get_available_metadata()

    # 2. Retrieve relevant policy data
    policy_data = _retrieve_policy_data(query_text)

    # 3. Build prompt and call Bedrock
    prompt = QUERY_CLASSIFICATION_AND_SYNTHESIS.format(
        payerList=", ".join(payers) if payers else "None ingested yet",
        drugList=", ".join(drugs) if drugs else "None ingested yet",
        queryText=query_text,
        policyData=policy_data,
    )

    try:
        raw_response = _invoke_bedrock(prompt)
        cleaned = _clean_json(raw_response)
        result = json.loads(cleaned)
    except Exception as e:
        logger.error(json.dumps({"error": "query_ai_failed", "detail": str(e)}))
        result = {
            "queryType": "unknown",
            "answer": "I was unable to process your query. Please try rephrasing.",
            "citations": [],
            "dataCompleteness": "insufficient",
        }

    response_time_ms = int((time.time() - start_time) * 1000)

    # 4. Write to QueryLog
    query_log_table = dynamodb.Table(QUERY_LOG_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub", "")
    except Exception:
        user_id = ""

    log_entry = {
        "queryId": query_id,
        # ADR: queryText truncated to 200 chars | Prevents PHI persistence if user types patient data
        "queryText": query_text[:200],
        "queryType": result.get("queryType", "unknown"),
        "resultSummary": result.get("answer", "")[:500],
        "citations": result.get("citations", []),
        "responseTimeMs": response_time_ms,
        "createdAt": now,
    }
    if user_id:
        import hashlib
        log_entry["userId"] = hashlib.sha256(user_id.encode()).hexdigest()[:12]

    try:
        query_log_table.put_item(Item=_convert_floats(log_entry))
    except Exception as e:
        logger.warning(json.dumps({"warning": "query_log_write_failed", "detail": str(e)}))

    return _response(200, {
        "queryId": query_id,
        "queryType": result.get("queryType", "unknown"),
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "dataCompleteness": result.get("dataCompleteness", "unknown"),
        "responseTimeMs": response_time_ms,
    })


def get_query(query_id: str) -> dict:
    """GET /api/query/{queryId} — fetch past query result."""
    table = dynamodb.Table(QUERY_LOG_TABLE)
    result = table.get_item(Key={"queryId": query_id})
    item = result.get("Item")
    if not item:
        return _response(404, {"error": f"Query {query_id} not found"})
    return _response(200, item)


def list_queries(event: dict) -> dict:
    """GET /api/queries — list recent 20 queries for the calling user."""
    table = dynamodb.Table(QUERY_LOG_TABLE)

    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub", "")
    except Exception:
        user_id = ""

    if user_id:
        import hashlib
        user_id_hash = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    else:
        user_id_hash = ""

    result = table.scan(Limit=20)
    items = result.get("Items", [])

    if user_id_hash:
        items = [i for i in items if i.get("userId") == user_id_hash]

    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return _response(200, {"queries": items, "count": len(items)})


def _convert_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


# ── Router ────────────────────────────────────────────────────────────────

def _get_method_and_path(event: dict) -> tuple[str, str]:
    """Support both REST API v1 and HTTP API v2 event shapes."""
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        ctx = event["requestContext"]["http"]
        return ctx.get("method", ""), event.get("rawPath", "")
    return event.get("httpMethod", ""), event.get("resource", "")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({"event_keys": list(event.keys())}))

    http_method, resource = _get_method_and_path(event)
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": _cors_headers(), "body": ""}

    path_params = event.get("pathParameters") or {}
    if not path_params:
        parts = resource.strip("/").split("/")
        # /api/query/{queryId} → parts = ["api", "query", "<id>"]
        if len(parts) == 3 and parts[1] == "query":
            path_params = {"queryId": parts[2]}

    try:
        if http_method == "POST" and resource == "/api/query":
            body = json.loads(event.get("body") or "{}")
            return submit_query(body, event)

        elif http_method == "GET" and resource == "/api/queries":
            return list_queries(event)

        elif http_method == "GET" and resource.startswith("/api/query/"):
            return get_query(path_params.get("queryId", ""))

        else:
            return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return _response(500, {"error": "Internal server error"})
