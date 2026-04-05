# Owner: Mohith
# ApprovalPathLambda — score coverage likelihood and generate PA memos.
#
# Routes handled:
#   POST /api/approval-path             → score patient against all payer criteria
#   POST /api/approval-path/{id}/memo   → generate PA memo for specific payer
#
# Expected input (POST /api/approval-path):
#   body: {
#     "drugName": str, "indicationName": str, "icd10Code": str,
#     "patientProfile": {
#       "patientAge": int,
#       "priorDrugsTried": [{ "drugName": str, "durationWeeks": int, "outcome": str }],
#       "labValues": { key: value },
#       "prescriberSpecialty": str,
#       "diagnosisDocumented": bool,
#       "diseaseActivityScore": str
#     }
#   }

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "")
POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "")
APPROVAL_PATHS_TABLE = os.environ.get("APPROVAL_PATHS_TABLE", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

SCORING_AND_MEMO_PROMPT = """\
You are a prior authorization specialist helping a pharmacy consultant assess \
whether a patient meets coverage criteria for a specific drug under a specific \
payer's policy.

Drug: {drugName}
Indication: {indicationName}
Payer: {payerName}
Policy title: {policyTitle}
Policy effective date: {policyEffectiveDate}

Payer's extracted criteria:
{payerCriteriaJson}

Patient clinical profile:
{patientProfileJson}

Step 1 — Score coverage likelihood (0-100):
- Start at 100
- For each required criterion the patient does NOT meet: deduct points based \
on barrier severity
  - Missing step therapy drug trial: -25 points each
  - Wrong prescriber specialty: -20 points
  - Missing diagnosis documentation: -30 points
  - Missing lab values: -10 points
  - Missing reauth documentation: -15 points
- For each criterion met with documentation: no deduction
- If a criterion cannot be determined from the profile: -5 points and flag \
as "unknown"

Step 2 — Identify gaps:
List each criterion the patient does not clearly meet, with a plain English \
explanation of what is missing.

Step 3 — Generate PA memo (only if score >= 50):
Write a formal prior authorization justification memo. Requirements:
- Reference the payer's policy by exact title and effective date
- For each criterion the patient meets, state it explicitly using the payer's \
own language
- Map patient data directly to policy language (e.g., "per Section 3.2 of \
the policy, patient must have failed one biosimilar infliximab product — \
patient completed a 14-week trial of Inflectra with documented inadequate \
response")
- Professional clinical tone
- 300-500 words
- Do NOT mention criteria the patient does not meet

Return JSON:
{{
  "score": number,
  "status": "likely_approved|gap_detected|likely_denied",
  "gaps": [string],
  "memo": string or null
}}"""


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
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


def _convert_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


def score_approval_path(body: dict) -> dict:
    """POST /api/approval-path — score patient against all ingested payer criteria."""
    drug_name = body.get("drugName", "").strip().lower()
    indication_name = body.get("indicationName", "").strip()
    icd10_code = body.get("icd10Code", "")
    patient_profile = body.get("patientProfile", {})

    if not drug_name or not indication_name:
        return _response(400, {"error": "drugName and indicationName are required"})

    if icd10_code and len(icd10_code) > 20:
        return _response(400, {"error": "icd10Code too long"})

    profile_str = json.dumps(patient_profile)
    if len(profile_str) > 50000:
        return _response(400, {"error": "patientProfile too large"})

    # 1. Fetch criteria for this drug across all payers
    criteria_table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)
    result = criteria_table.query(
        IndexName="drugName-payerName-index",
        KeyConditionExpression=Key("drugName").eq(drug_name),
        Limit=100,
    )
    all_criteria = result.get("Items", [])

    # Filter by indication
    indication_lower = indication_name.lower()
    relevant = [
        c for c in all_criteria
        if indication_lower in c.get("indicationName", "").lower()
    ]

    if not relevant:
        # Fall back to all criteria for this drug
        relevant = all_criteria

    # Group by payer
    by_payer: dict[str, list[dict]] = {}
    for c in relevant:
        payer = c.get("payerName", "Unknown")
        by_payer.setdefault(payer, []).append(c)

    if not by_payer:
        return _response(200, {
            "payerScores": [],
            "message": "No policy data found for this drug. Upload payer policies first.",
        })

    # 2. Score each payer
    payer_scores: list[dict] = []
    generated_memos: dict[str, str] = {}
    approval_path_id = str(uuid.uuid4())

    # Get policy titles from PolicyDocuments
    policy_table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)

    for payer_name, payer_criteria in by_payer.items():
        # Look up policy document for title + effective date
        policy_doc_id = payer_criteria[0].get("policyDocId", "")
        policy_title = "Unknown Policy"
        effective_date = payer_criteria[0].get("effectiveDate", "")

        if policy_doc_id:
            try:
                doc = policy_table.get_item(Key={"policyDocId": policy_doc_id}).get("Item", {})
                policy_title = doc.get("documentTitle", policy_title)
                effective_date = doc.get("effectiveDate", effective_date)
            except Exception:
                pass

        # Build patient profile with drug + indication context
        full_profile = {
            **patient_profile,
            "drugName": drug_name,
            "indicationName": indication_name,
            "icd10Code": icd10_code,
        }

        prompt = SCORING_AND_MEMO_PROMPT.format(
            drugName=drug_name,
            indicationName=indication_name,
            payerName=payer_name,
            policyTitle=policy_title,
            policyEffectiveDate=effective_date,
            payerCriteriaJson=json.dumps(payer_criteria, default=str),
            patientProfileJson=json.dumps(full_profile, default=str),
        )

        try:
            raw = _invoke_bedrock(prompt)
            cleaned = _clean_json(raw)
            scoring = json.loads(cleaned)
        except Exception as e:
            logger.error(json.dumps({"error": "bedrock_scoring_failed", "payerName": payer_name, "detail": str(e)}))
            scoring = {
                "score": 0,
                "status": "likely_denied",
                "gaps": [f"Scoring unavailable: {str(e)}"],
                "memo": None,
            }

        score = scoring.get("score", 0)
        status = scoring.get("status", "likely_denied")
        gaps = scoring.get("gaps", [])
        memo = scoring.get("memo")

        payer_scores.append({
            "payerName": payer_name,
            "score": score,
            "status": status,
            "gaps": gaps,
            "meetsCriteria": status == "likely_approved",
            "policyTitle": policy_title,
            "effectiveDate": effective_date,
        })

        if memo:
            generated_memos[payer_name] = memo

    # Sort by score descending
    payer_scores.sort(key=lambda x: x["score"], reverse=True)
    recommended_payer = payer_scores[0]["payerName"] if payer_scores else None

    # 3. Store in ApprovalPaths table
    approval_table = dynamodb.Table(APPROVAL_PATHS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    approval_record = {
        "approvalPathId": approval_path_id,
        "drugName": drug_name,
        "indicationName": indication_name,
        "patientProfile": _convert_floats(patient_profile),
        "payerScores": _convert_floats(payer_scores),
        "generatedMemos": generated_memos,
        "createdAt": now,
    }

    try:
        approval_table.put_item(Item=approval_record)
    except Exception as e:
        logger.warning(json.dumps({"warning": "approval_path_store_failed", "detail": str(e)}))

    return _response(200, {
        "approvalPathId": approval_path_id,
        "payerScores": payer_scores,
        "recommendedPayer": recommended_payer,
    })


def generate_memo(approval_path_id: str, body: dict) -> dict:
    """POST /api/approval-path/{id}/memo — generate or retrieve PA memo for a payer."""
    payer_name = body.get("payerName", "").strip()
    if not payer_name:
        return _response(400, {"error": "payerName is required"})

    # Fetch existing approval path
    approval_table = dynamodb.Table(APPROVAL_PATHS_TABLE)
    result = approval_table.get_item(Key={"approvalPathId": approval_path_id})
    item = result.get("Item")

    if not item:
        return _response(404, {"error": f"Approval path {approval_path_id} not found"})

    # Check if memo already generated
    existing_memos = item.get("generatedMemos", {})
    if payer_name in existing_memos:
        # Find matching payer score for metadata
        payer_score = next(
            (s for s in item.get("payerScores", []) if s.get("payerName") == payer_name),
            {},
        )
        return _response(200, {
            "memoText": existing_memos[payer_name],
            "citations": [],
            "policyTitle": payer_score.get("policyTitle", ""),
            "effectiveDate": payer_score.get("effectiveDate", ""),
        })

    # If not cached, regenerate memo on-demand for this payer
    drug_name = item.get("drugName", "")
    indication_name = item.get("indicationName", "")
    patient_profile = item.get("patientProfile", {})

    payer_score = next(
        (s for s in item.get("payerScores", []) if s.get("payerName") == payer_name),
        {},
    )
    if not payer_score:
        return _response(404, {"error": f"Payer {payer_name} not found in this approval path"})

    if payer_score.get("score", 0) < 50:
        return _response(400, {"error": f"Score {payer_score['score']}/100 is below 50 — memo generation not available for likely-denied cases"})

    # Re-run Bedrock scoring for this payer to generate memo
    criteria_table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)
    result = criteria_table.query(
        IndexName="drugName-payerName-index",
        KeyConditionExpression=Key("drugName").eq(drug_name) & Key("payerName").eq(payer_name),
        Limit=20,
    )
    payer_criteria = result.get("Items", [])

    policy_title = payer_score.get("policyTitle", "Unknown Policy")
    effective_date = payer_score.get("effectiveDate", "")

    full_profile = {**patient_profile, "drugName": drug_name, "indicationName": indication_name}
    prompt = SCORING_AND_MEMO_PROMPT.format(
        drugName=drug_name,
        indicationName=indication_name,
        payerName=payer_name,
        policyTitle=policy_title,
        policyEffectiveDate=effective_date,
        payerCriteriaJson=json.dumps(payer_criteria, default=str),
        patientProfileJson=json.dumps(full_profile, default=str),
    )

    try:
        raw = _invoke_bedrock(prompt)
        cleaned = _clean_json(raw)
        scoring = json.loads(cleaned)
        memo = scoring.get("memo")
    except Exception as e:
        logger.error(json.dumps({"error": "memo_regeneration_failed", "detail": str(e)}))
        return _response(500, {"error": "Memo generation failed"})

    if not memo:
        return _response(404, {"error": "Memo could not be generated — patient may not meet criteria"})

    # Cache the memo for future requests
    approval_table.update_item(
        Key={"approvalPathId": approval_path_id},
        UpdateExpression="SET generatedMemos.#payer = :memo",
        ExpressionAttributeNames={"#payer": payer_name},
        ExpressionAttributeValues={":memo": memo},
    )

    return _response(200, {
        "memoText": memo,
        "citations": [],
        "policyTitle": policy_title,
        "effectiveDate": effective_date,
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
        # /api/approval-path/{id}/memo → parts = ["api", "approval-path", "<id>", "memo"]
        if len(parts) == 4 and parts[1] == "approval-path":
            path_params = {"id": parts[2]}

    try:
        if http_method == "POST" and resource == "/api/approval-path":
            body = json.loads(event.get("body") or "{}")
            return score_approval_path(body)

        elif http_method == "POST" and resource.endswith("/memo"):
            body = json.loads(event.get("body") or "{}")
            return generate_memo(path_params.get("id", ""), body)

        else:
            return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return _response(500, {"error": "Internal server error"})
