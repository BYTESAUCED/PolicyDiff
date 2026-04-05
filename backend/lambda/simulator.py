# Owner: Mohith
# SimulatorLambda — simulate policy outcome for a given patient + drug + payer combination.
#
# Routes handled:
#   POST /api/simulate
#
# Expected input:
#   body: {
#     "drug": str,
#     "payerId": str,
#     "patientProfile": {
#       "diagnosis": str,
#       "icd10Code": str (optional),
#       "priorTreatments": [{ "drug": str, "weeks": int, "outcome": str }],
#       "prescriberSpecialty": str (optional),
#       "diagnosisDocumented": bool (optional),
#       "highDiseaseActivityDocumented": bool (optional),
#     }
#   }
#
# Expected output:
#   {
#     "simulationId": str,
#     "outcome": "APPROVED" | "DENIED" | "STEP_THERAPY",
#     "confidence": float,
#     "reasoning": str,
#     "criteriaChecks": [{ "criterion": str, "met": bool, "detail": str }],
#     "payerName": str,
#     "drug": str,
#   }

import json
import logging
import os
import uuid
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_REQUIRED_ENV_VARS = ["DRUG_POLICY_CRITERIA_TABLE", "BEDROCK_MODEL_ID"]
for _var in _REQUIRED_ENV_VARS:
    if not os.environ.get(_var):
        logger.warning(json.dumps({"warning": "missing_env_var", "var": _var}))

# ADR: Module-level clients | Reused across warm invocations
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("REGION", "us-east-1"))

# ADR: BEDROCK_MODEL_ID from env | common_env passes the full model ARN; empty string causes fast-fail at invoke time
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
if not BEDROCK_MODEL_ID:
    logger.warning(json.dumps({"warning": "missing_env_var", "var": "BEDROCK_MODEL_ID"}))


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _fetch_criteria(drug_name: str, payer_id: str) -> list[dict]:
    """Query DrugPolicyCriteria by drugName + payerName GSI."""
    table_name = os.environ.get("DRUG_POLICY_CRITERIA_TABLE")
    if not table_name:
        return []
    table = dynamodb.Table(table_name)
    try:
        result = table.query(
            IndexName="drugName-payerName-index",
            KeyConditionExpression=(
                Key("drugName").eq(drug_name) & Key("payerName").eq(payer_id)
            ),
            Limit=10,
        )
        items = result.get("Items", [])
        # Fallback: case-insensitive payer match via scan if GSI returns nothing
        if not items:
            scan_result = table.query(
                IndexName="drugName-payerName-index",
                KeyConditionExpression=Key("drugName").eq(drug_name),
                Limit=50,
            )
            payer_lower = payer_id.lower()
            items = [
                i for i in scan_result.get("Items", [])
                if payer_lower in i.get("payerName", "").lower()
            ]
        return items
    except ClientError as e:
        logger.error(json.dumps({"error": "dynamodb_query_failed", "detail": str(e)}))
        return []


def _build_simulation_prompt(drug: str, payer_id: str, patient_profile: dict, criteria_records: list[dict]) -> str:
    criteria_summary = json.dumps(criteria_records[:5], default=str) if criteria_records else "No criteria found in database."
    prior_treatments = patient_profile.get("priorTreatments", [])
    treatments_text = (
        "\n".join(
            f"  - {t.get('drug', 'Unknown')} for {t.get('weeks', '?')} weeks ({t.get('outcome', 'unknown outcome')})"
            for t in prior_treatments
        )
        if prior_treatments else "  None documented"
    )

    return f"""You are a prior authorization specialist evaluating whether a patient meets coverage criteria.

Drug: {drug}
Payer: {payer_id}

Patient Profile:
- Diagnosis: {patient_profile.get('diagnosis', 'Not specified')}
- ICD-10: {patient_profile.get('icd10Code', 'Not specified')}
- Prescriber Specialty: {patient_profile.get('prescriberSpecialty', 'Not specified')}
- Diagnosis Documented: {patient_profile.get('diagnosisDocumented', True)}
- High Disease Activity Documented: {patient_profile.get('highDiseaseActivityDocumented', True)}
- Prior Treatments:
{treatments_text}

Extracted Policy Criteria (from database):
{criteria_summary}

Based on the patient profile and the policy criteria above, evaluate whether this patient would be APPROVED, DENIED, or requires STEP_THERAPY.

Respond with a JSON object only (no markdown fences):
{{
  "outcome": "APPROVED" | "DENIED" | "STEP_THERAPY",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<1-3 sentence explanation>",
  "criteriaChecks": [
    {{"criterion": "<criterion name>", "met": <true|false>, "detail": "<brief explanation>"}}
  ]
}}"""


def _invoke_bedrock(prompt: str) -> dict:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
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
    raw_text = result["content"][0]["text"].strip()

    # Strip markdown fences if present
    if raw_text.startswith("```"):
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw_text, re.DOTALL)
        raw_text = match.group(1).strip() if match else raw_text

    return json.loads(raw_text)


def _rule_based_fallback(drug: str, payer_id: str, patient_profile: dict, criteria_records: list[dict]) -> dict:
    """Simple rule-based simulation when Bedrock is unavailable or criteria are empty."""
    prior_treatments = patient_profile.get("priorTreatments", [])
    total_prior_weeks = sum(t.get("weeks", 0) for t in prior_treatments)
    has_diagnosis = patient_profile.get("diagnosisDocumented", True)

    checks = [
        {
            "criterion": "Diagnosis documented",
            "met": has_diagnosis,
            "detail": "Diagnosis documentation present" if has_diagnosis else "Diagnosis not documented",
        },
        {
            "criterion": "Prior treatment history",
            "met": len(prior_treatments) > 0,
            "detail": f"{len(prior_treatments)} prior treatment(s) on record",
        },
        {
            "criterion": "Adequate trial duration",
            "met": total_prior_weeks >= 12,
            "detail": f"Total prior treatment duration: {total_prior_weeks} weeks (≥12 required)",
        },
    ]

    met_count = sum(1 for c in checks if c["met"])
    confidence = round(met_count / len(checks), 2)

    if met_count == len(checks):
        outcome = "APPROVED"
        reasoning = f"Patient meets documented criteria for {drug} coverage under {payer_id}."
    elif len(prior_treatments) == 0:
        outcome = "STEP_THERAPY"
        reasoning = f"No prior treatment history on record. Step therapy required before {drug} can be approved."
    else:
        outcome = "DENIED"
        reasoning = f"Patient does not meet all required criteria for {drug} coverage under {payer_id}."

    return {"outcome": outcome, "confidence": confidence, "reasoning": reasoning, "criteriaChecks": checks}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({
        "action": "simulator_request",
        "requestId": (event.get("requestContext") or {}).get("requestId"),
    }))

    if event.get("httpMethod") == "OPTIONS" or (event.get("requestContext") or {}).get("http", {}).get("method") == "OPTIONS":
        return create_response(200, {})

    try:
        body: dict = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return create_response(400, {"message": "Invalid JSON body"})

    drug = (body.get("drug") or "").strip()
    payer_id = (body.get("payerId") or "").strip()
    patient_profile: dict = body.get("patientProfile") or {}

    if not drug or not payer_id:
        return create_response(400, {"message": "Missing required fields: drug, payerId"})

    logger.info(json.dumps({"action": "simulate", "drug": drug, "payerId": payer_id}))

    # 1. Fetch relevant criteria from DynamoDB
    criteria_records = _fetch_criteria(drug, payer_id)
    logger.info(json.dumps({"action": "criteria_fetched", "count": len(criteria_records)}))

    # 2. Run simulation — Bedrock if criteria exist, rule-based fallback otherwise
    simulation_result: dict
    if criteria_records:
        try:
            prompt = _build_simulation_prompt(drug, payer_id, patient_profile, criteria_records)
            simulation_result = _invoke_bedrock(prompt)
        except Exception as e:
            logger.warning(json.dumps({"warning": "bedrock_failed_using_fallback", "detail": str(e)}))
            simulation_result = _rule_based_fallback(drug, payer_id, patient_profile, criteria_records)
    else:
        logger.info(json.dumps({"action": "no_criteria_found_using_fallback", "drug": drug, "payerId": payer_id}))
        simulation_result = _rule_based_fallback(drug, payer_id, patient_profile, [])

    simulation_id = str(uuid.uuid4())
    response_body = {
        "simulationId": simulation_id,
        "outcome": simulation_result.get("outcome", "DENIED"),
        "confidence": simulation_result.get("confidence", 0.0),
        "reasoning": simulation_result.get("reasoning", ""),
        "criteriaChecks": simulation_result.get("criteriaChecks", []),
        "payerName": payer_id,
        "drug": drug,
    }

    logger.info(json.dumps({
        "action": "simulation_complete",
        "simulationId": simulation_id,
        "outcome": response_body["outcome"],
        "confidence": response_body["confidence"],
    }))

    return create_response(200, response_body)
