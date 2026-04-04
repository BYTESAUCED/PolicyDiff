# Owner: Mohith
# DiffLambda — temporal policy diffs between versions of the same payer's policy.
#
# Routes handled:
#   GET /api/diffs           → list diffs (filter by policyId, drug, date range)
#   GET /api/diffs/{diffId}  → get full diff detail
#   GET /api/diffs/feed      → chronological change feed across all policies
#
# Expected output (getDiff):
#   { "diffId": str, "drugName": str, "diffType": str, "changes": [ { "field": str, "oldValue": any, "newValue": any } ] }

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_ENV_VARS = ["POLICY_DIFFS_TABLE", "DRUG_POLICY_CRITERIA_TABLE"]
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
    logger.info(json.dumps({"action": "diff_request", "event": event}))

    return create_response(200, {"message": "DiffLambda stub — implement AI logic here"})
