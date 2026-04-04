# Owner: Mohith
# State 4.5 — GeminiVerification (Gemini API Track)
#
# Cross-model verification: takes Bedrock-extracted criteria and sends them
# to Gemini 1.5 Pro with the original policy text to spot misclassifications.
#
# Enhanced per policy-pdf-analysis.md:
#   - Added stepTherapyMinCount verification check
#   - Added initialAuthDurationMonths / maxAuthDurationMonths checks
#
# If Gemini call fails (rate limit, quota, key missing), log and continue —
# extraction does NOT fail.
#
# Step Functions I/O:
#   Input:  { ..., extractedCriteria: [...], structuredTextS3Key, ... }
#   Output: { ..., verificationResult: { issues, overallConfidence }, ... }

import json
import logging
import os
import re
from typing import Any

import boto3
import urllib.request
import urllib.error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GEMINI_SECRET_NAME = os.environ.get("GEMINI_SECRET_NAME", "policydiff/gemini-api-key")
GEMINI_MODEL = "gemini-1.5-pro"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
MAX_RAW_TEXT_CHARS = 8000

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _get_gemini_key() -> str | None:
    """Retrieve Gemini API key from Secrets Manager. Returns None on failure."""
    try:
        resp = secrets.get_secret_value(SecretId=GEMINI_SECRET_NAME)
        secret = json.loads(resp["SecretString"])
        return secret.get("key") or secret.get("api_key") or secret.get("apiKey")
    except Exception as e:
        logger.warning(f"Could not retrieve Gemini API key: {e}")
        return None


def _call_gemini(api_key: str, prompt: str) -> dict:
    """Call Gemini 1.5 Pro via REST. Returns parsed JSON response body."""
    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Verify Bedrock extraction with Gemini 1.5 Pro for cross-model validation."""
    logger.info(json.dumps({"state": "GeminiVerification", "policyDocId": event.get("policyDocId")}))

    extracted_criteria = event.get("extractedCriteria", [])
    s3_bucket = event.get("s3Bucket", "")
    structured_key = event.get("structuredTextS3Key", "")

    # Default passthrough — verification is non-blocking
    default_result = {
        "issues": [],
        "overallVerificationConfidence": 1.0,
        "status": "skipped",
    }

    # Skip if extraction was skipped or no criteria
    if event.get("extractionSkipped") or not extracted_criteria:
        logger.info("No criteria to verify, skipping Gemini verification")
        return {**event, "verificationResult": default_result}

    # 1. Get Gemini API key
    api_key = _get_gemini_key()
    if not api_key:
        logger.warning("Gemini API key unavailable — skipping verification")
        default_result["status"] = "no_api_key"
        return {**event, "verificationResult": default_result}

    # 2. Get raw text for context
    raw_text = ""
    if s3_bucket and structured_key:
        try:
            resp = s3.get_object(Bucket=s3_bucket, Key=structured_key)
            structured_doc = json.loads(resp["Body"].read().decode("utf-8"))
            raw_text = structured_doc.get("rawText", "")[:MAX_RAW_TEXT_CHARS]
        except Exception as e:
            logger.warning(f"Could not read structured text for verification: {e}")

    # 3. Build prompt (enhanced with stepTherapyMinCount and auth duration checks)
    from extraction.prompts import GEMINI_VERIFICATION_PROMPT

    prompt = GEMINI_VERIFICATION_PROMPT.format(
        extracted=json.dumps(extracted_criteria[:5], default=str),
        raw_text=raw_text,
    )

    # 4. Call Gemini (non-blocking — catch all errors)
    try:
        gemini_response = _call_gemini(api_key, prompt)

        candidates = gemini_response.get("candidates", [])
        if not candidates:
            logger.warning("Gemini returned no candidates")
            default_result["status"] = "empty_response"
            return {**event, "verificationResult": default_result}

        response_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        # Parse JSON from response
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", response_text, re.DOTALL)
        if match:
            response_text = match.group(1).strip()

        verification = json.loads(response_text)
        verification["status"] = "complete"

        issues = verification.get("issues", [])
        if issues:
            logger.info(f"Gemini found {len(issues)} issues in extraction")
            for issue in issues:
                logger.info(f"  Issue: {issue.get('field')} — extracted={issue.get('extractedValue')}, "
                           f"correct={issue.get('correctValue')}")
        else:
            logger.info("Gemini verification: no issues found")

        return {**event, "verificationResult": verification}

    except urllib.error.HTTPError as e:
        logger.warning(f"Gemini API HTTP error {e.code}: {e.reason}")
        default_result["status"] = f"http_error_{e.code}"
    except urllib.error.URLError as e:
        logger.warning(f"Gemini API connection error: {e.reason}")
        default_result["status"] = "connection_error"
    except json.JSONDecodeError as e:
        logger.warning(f"Could not parse Gemini response as JSON: {e}")
        default_result["status"] = "parse_error"
    except Exception as e:
        logger.warning(f"Gemini verification failed (non-fatal): {e}")
        default_result["status"] = "error"

    return {**event, "verificationResult": default_result}
