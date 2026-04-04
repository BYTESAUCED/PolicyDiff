# Owner: Mohith (stretch goal)
# SimulatorLambda — simulate policy outcomes for a given patient + drug + payer combination.
#
# Routes handled:
#   POST /api/simulate
#
# Expected input:
#   body: { "drug": str, "payerId": str, "patientProfile": { "diagnosis": str, "priorTreatments": list } }
#
# Expected output:
#   { "simulationId": str, "outcome": "APPROVED"|"DENIED"|"STEP_THERAPY", "confidence": float, "reasoning": str }

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_ENV_VARS = ["DRUG_POLICY_CRITERIA_TABLE"]
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
    logger.info(json.dumps({"action": "simulator_request", "event": event}))

    return create_response(200, {"message": "SimulatorLambda stub — implement AI logic here"})
