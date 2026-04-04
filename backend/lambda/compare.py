# Owner: Mohith
# CompareLambda — cross-payer comparison matrix for a given drug.
#
# Routes handled:
#   GET /api/compare        → returns comparison matrix (drug × payer grid)
#   GET /api/compare/export → returns CSV/PDF download URL
#
# Expected query params: drug (required), policyIds (optional, comma-separated)
# Expected output: { "drug": str, "matrix": [ { "payer": str, "criteria": {...} } ] }

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_ENV_VARS = ["DRUG_POLICY_CRITERIA_TABLE", "DOCUMENTS_BUCKET_NAME"]
for _var in _ENV_VARS:
    if not os.environ.get(_var):
        logger.warning(json.dumps({"warning": "missing_env_var", "var": _var}))


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({"action": "compare_request", "event": event}))

    return create_response(200, {"message": "CompareLambda stub — implement AI logic here"})
