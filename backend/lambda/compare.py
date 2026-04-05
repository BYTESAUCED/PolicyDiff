# Owner: Mohith
# CompareLambda — cross-payer comparison matrix for a given drug + indication.
#
# Routes handled:
#   GET /api/compare        → returns color-coded comparison matrix
#   GET /api/compare/export → returns CSV download (plain text)
#
# Query params: drug (required), indication (optional), payers (optional, comma-separated)

import csv
import io
import json
import logging
import os
import re
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "DrugPolicyCriteria")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")

for _var in ["DRUG_POLICY_CRITERIA_TABLE", "BEDROCK_MODEL_ID"]:
    if not os.environ.get(_var):
        logger.warning(json.dumps({"warning": "missing_env_var", "var": _var}))

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

CROSS_PAYER_COMPARISON_PROMPT = """\
You are comparing medical benefit drug policy criteria across multiple payers \
for the same drug and indication. Your output feeds a color-coded comparison \
matrix for pharmacy consultants.

Drug: {drugName}
Indication: {indicationName}
Payers being compared: {payerList}

Policy data from each payer:
{policiesJson}

For each of the following dimensions, determine which payer is most restrictive \
and least restrictive:

1. preferred_products — list each payer's preference hierarchy
2. step_therapy_count — how many prior drug failures required
3. step_therapy_drugs — which specific drugs must fail
4. trial_duration — minimum weeks of prior therapy
5. prescriber_requirement — specialist type required
6. max_dosing — maximum dose and frequency
7. auth_duration — months per authorization period
8. reauth_documentation — what clinical evidence required for renewal
9. combination_restrictions — co-prescribing prohibitions
10. self_admin — whether self-administration is permitted

For each dimension, assign severity per payer:
- "most_restrictive" → red cell
- "moderate" → yellow cell
- "least_restrictive" → green cell
- "equivalent" → gray cell (all payers the same)
- "not_specified" → gray cell (not addressed in this payer's policy)

Return structured JSON only:
{{
  "drug": string,
  "indication": string,
  "dimensions": [
    {{
      "key": string,
      "label": string,
      "values": [
        {{ "payerName": string, "value": string, "severity": string }}
      ]
    }}
  ]
}}"""


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Content-Type": "application/json",
    }


def _response(status: int, body: Any, content_type: str = "application/json") -> dict:
    headers = _cors_headers()
    headers["Content-Type"] = content_type
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, default=str) if content_type == "application/json" else body,
    }


def _invoke_bedrock(prompt: str, max_tokens: int = 4096) -> str:
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": 0.1,
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


def _fetch_criteria_for_drug(drug_name: str, payers: list[str] | None = None) -> list[dict]:
    """Fetch DrugPolicyCriteria records for a drug across payers via GSI."""
    table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    result = table.query(
        IndexName="drugName-payerName-index",
        KeyConditionExpression=Key("drugName").eq(drug_name.lower()),
        Limit=100,
    )
    items = result.get("Items", [])

    if payers:
        items = [i for i in items if i.get("payerName") in payers]

    return items


def compare_matrix(params: dict) -> dict:
    """GET /api/compare — generate comparison matrix."""
    drug = params.get("drug", "").strip().lower()
    indication = params.get("indication", "").strip()
    payers_str = params.get("payers", "")
    payers = [p.strip() for p in payers_str.split(",") if p.strip()] if payers_str else None

    if not drug:
        return _response(400, {"error": "drug query parameter is required"})

    if len(drug) > 200:
        return _response(400, {"error": "drug parameter too long"})
    if indication and len(indication) > 500:
        return _response(400, {"error": "indication parameter too long"})

    # 1. Fetch criteria from DynamoDB
    criteria = _fetch_criteria_for_drug(drug, payers)

    if not criteria:
        return _response(200, {
            "drug": drug,
            "indication": indication,
            "payers": [],
            "dimensions": [],
            "message": "No policy data found for this drug",
        })

    # Filter by indication if provided
    if indication:
        indication_lower = indication.lower()
        filtered = [c for c in criteria if indication_lower in c.get("indicationName", "").lower()]
        if filtered:
            criteria = filtered

    # Get unique payers
    payer_list = sorted({c.get("payerName", "") for c in criteria if c.get("payerName")})

    if not indication:
        # Auto-detect most common indication
        indication_counts: dict[str, int] = {}
        for c in criteria:
            ind = c.get("indicationName", "")
            if ind:
                indication_counts[ind] = indication_counts.get(ind, 0) + 1
        if indication_counts:
            indication = max(indication_counts, key=indication_counts.get)

    # 2. Call Bedrock for comparison analysis
    prompt = CROSS_PAYER_COMPARISON_PROMPT.format(
        drugName=drug,
        indicationName=indication,
        payerList=", ".join(payer_list),
        policiesJson=json.dumps(criteria, default=str),
    )

    try:
        raw = _invoke_bedrock(prompt)
        cleaned = _clean_json(raw)
        matrix = json.loads(cleaned)
    except Exception as e:
        logger.error(json.dumps({"error": "bedrock_comparison_failed", "detail": str(e)}))
        # Fallback: return raw data without AI analysis
        matrix = {
            "drug": drug,
            "indication": indication,
            "dimensions": [],
            "error": "AI comparison analysis unavailable",
        }

    matrix["payers"] = payer_list
    return _response(200, matrix)


def compare_export(params: dict) -> dict:
    """GET /api/compare/export — export comparison matrix as CSV."""
    # Re-use matrix generation
    matrix_response = compare_matrix(params)
    matrix_body = json.loads(matrix_response["body"]) if isinstance(matrix_response["body"], str) else matrix_response["body"]

    dimensions = matrix_body.get("dimensions", [])
    payers = matrix_body.get("payers", [])

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(["Dimension"] + payers)

    # Data rows
    for dim in dimensions:
        row = [dim.get("label", dim.get("key", ""))]
        values_by_payer = {v["payerName"]: v for v in dim.get("values", [])}
        for payer in payers:
            val = values_by_payer.get(payer, {})
            cell = f"{val.get('value', 'N/A')} [{val.get('severity', 'unknown')}]"
            row.append(cell)
        writer.writerow(row)

    csv_content = output.getvalue()

    return {
        "statusCode": 200,
        "headers": {
            **_cors_headers(),
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename={matrix_body.get('drug', 'comparison')}_matrix.csv",
        },
        "body": csv_content,
    }


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

    query_params = event.get("queryStringParameters") or {}

    try:
        if resource == "/api/compare/export":
            return compare_export(query_params)
        elif resource == "/api/compare":
            return compare_matrix(query_params)
        else:
            return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return _response(500, {"error": "Internal server error"})
