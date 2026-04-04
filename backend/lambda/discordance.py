# Owner: Mohith
# DiscordanceLambda — detect medical vs. pharmacy benefit discordances.
#
# Routes handled:
#   GET /api/discordance                  → list all discordance summaries
#   GET /api/discordance/{drug}/{payer}   → full discordance detail for a pair
#
# Discordance detection: when both medical and pharmacy benefit policies
# exist for the same drug + payer, auto-flag discrepancies in step therapy,
# prescriber requirements, and patient subgroup restrictions.
# Based on JMCP research: 14% of same-drug policies are discordant.

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "")
POLICY_DIFFS_TABLE = os.environ.get("POLICY_DIFFS_TABLE", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

DISCORDANCE_PROMPT = """\
You are comparing medical benefit vs. pharmacy benefit policies for the same \
drug and payer to identify discordances — cases where the same drug has \
different coverage requirements depending on which benefit it is administered \
under.

Drug: {drugName}
Payer: {payerName}

Medical benefit policy criteria:
{medicalJson}

Pharmacy benefit policy criteria:
{pharmacyJson}

Compare these dimensions and flag any discordances:
1. Step therapy requirements — number of prior drug failures, which drugs
2. Prescriber specialty requirement
3. Patient subgroup restrictions (age, diagnosis severity, etc.)
4. Dosing limits
5. Authorization duration
6. Reauthorization documentation

For each discordance found:
- dimension: which comparison dimension
- medicalValue: what the medical benefit policy requires
- pharmacyValue: what the pharmacy benefit policy requires
- moreRestrictive: "medical" | "pharmacy"
- clinicalImpact: one-sentence description of patient impact
- severity: "high" | "medium" | "low"

Return JSON only:
{{
  "discordances": [
    {{
      "dimension": string,
      "medicalValue": string,
      "pharmacyValue": string,
      "moreRestrictive": string,
      "clinicalImpact": string,
      "severity": string
    }}
  ],
  "overallDiscordanceScore": number (0-1, where 1 = completely discordant),
  "summary": string (2-3 sentence executive summary)
}}"""


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
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    text = text.strip()
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            return text[i:]
    return text


def _convert_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


def _find_discordant_pairs() -> list[dict]:
    """Scan DrugPolicyCriteria for drug+payer combos with both medical & pharmacy."""
    table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    result = table.scan(Limit=500)
    items = result.get("Items", [])

    # Group by (drugName, payerName)
    groups: dict[tuple, list[dict]] = {}
    for item in items:
        key = (item.get("drugName", ""), item.get("payerName", ""))
        groups.setdefault(key, []).append(item)

    pairs: list[dict] = []
    for (drug, payer), records in groups.items():
        benefit_types = {r.get("benefitType", "").lower() for r in records}
        if "medical" in benefit_types and "pharmacy" in benefit_types:
            medical = [r for r in records if r.get("benefitType", "").lower() == "medical"]
            pharmacy = [r for r in records if r.get("benefitType", "").lower() == "pharmacy"]
            pairs.append({
                "drugName": drug,
                "payerName": payer,
                "medicalRecords": medical,
                "pharmacyRecords": pharmacy,
            })

    return pairs


def list_discordances() -> dict:
    """GET /api/discordance — list all detected discordance summaries."""
    # Check existing diffs table for pre-computed discordances
    diffs_table = dynamodb.Table(POLICY_DIFFS_TABLE)

    try:
        result = diffs_table.scan(
            FilterExpression=Attr("diffType").eq("benefit_discordance"),
            Limit=50,
        )
        existing = result.get("Items", [])
    except Exception:
        existing = []

    # Also scan for new discordant pairs not yet analyzed
    pairs = _find_discordant_pairs()

    summaries: list[dict] = []

    # Include existing computed discordances
    for item in existing:
        summaries.append({
            "diffId": item.get("diffId"),
            "drugName": item.get("drugName"),
            "payerName": item.get("payerName"),
            "discordanceScore": float(item.get("discordanceScore", 0)),
            "summary": item.get("summary", ""),
            "changesCount": len(item.get("changes", [])),
            "generatedAt": item.get("generatedAt", ""),
        })

    # Include unanalyzed pairs
    existing_keys = {(s["drugName"], s["payerName"]) for s in summaries}
    for pair in pairs:
        key = (pair["drugName"], pair["payerName"])
        if key not in existing_keys:
            summaries.append({
                "drugName": pair["drugName"],
                "payerName": pair["payerName"],
                "discordanceScore": None,
                "summary": "Discordance not yet analyzed — both medical and pharmacy policies detected",
                "status": "pending_analysis",
            })

    return _response(200, {"items": summaries, "count": len(summaries)})


def get_discordance_detail(drug: str, payer: str) -> dict:
    """GET /api/discordance/{drug}/{payer} — full discordance analysis."""
    table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)

    # Fetch all criteria for this drug + payer
    result = table.query(
        IndexName="drugName-payerName-index",
        KeyConditionExpression=Key("drugName").eq(drug.lower()) & Key("payerName").eq(payer),
    )
    items = result.get("Items", [])

    medical = [i for i in items if i.get("benefitType", "").lower() == "medical"]
    pharmacy = [i for i in items if i.get("benefitType", "").lower() == "pharmacy"]

    if not medical or not pharmacy:
        return _response(200, {
            "drugName": drug,
            "payerName": payer,
            "discordances": [],
            "message": "Both medical and pharmacy benefit policies required for discordance analysis",
            "hasMedial": len(medical) > 0,
            "hasPharmacy": len(pharmacy) > 0,
        })

    # Run Bedrock discordance analysis
    prompt = DISCORDANCE_PROMPT.format(
        drugName=drug,
        payerName=payer,
        medicalJson=json.dumps(medical, default=str),
        pharmacyJson=json.dumps(pharmacy, default=str),
    )

    try:
        raw = _invoke_bedrock(prompt)
        cleaned = _clean_json(raw)
        analysis = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Bedrock discordance analysis failed: {e}")
        return _response(500, {"error": "Discordance analysis failed"})

    # Store result in PolicyDiffs table
    diffs_table = dynamodb.Table(POLICY_DIFFS_TABLE)
    diff_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    diff_record = {
        "diffId": diff_id,
        "diffType": "benefit_discordance",
        "drugName": drug.lower(),
        "payerName": payer,
        "changes": _convert_floats(analysis.get("discordances", [])),
        "discordanceScore": _convert_floats(analysis.get("overallDiscordanceScore", 0)),
        "summary": analysis.get("summary", ""),
        "generatedAt": now,
    }

    try:
        diffs_table.put_item(Item=diff_record)
    except Exception as e:
        logger.warning(f"Failed to store discordance result: {e}")

    return _response(200, {
        "diffId": diff_id,
        "drugName": drug,
        "payerName": payer,
        **analysis,
    })


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
        # /api/discordance/{drug}/{payer} → parts = ["api", "discordance", "<drug>", "<payer>"]
        if len(parts) == 4 and parts[1] == "discordance":
            path_params = {"drug": parts[2], "payer": parts[3]}

    try:
        if resource.startswith("/api/discordance/") and http_method == "GET":
            return get_discordance_detail(
                path_params.get("drug", ""),
                path_params.get("payer", ""),
            )
        elif resource == "/api/discordance":
            return list_discordances()
        else:
            return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        return _response(500, {"error": "Internal server error"})
