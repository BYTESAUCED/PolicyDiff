# Owner: Mohith
# QueryLambda — natural language query against extracted policy criteria via Bedrock.
#
# Routes handled:
#   POST /api/query           → submit NL query, returns queryId
#   GET  /api/query/{queryId} → poll for result
#   GET  /api/queries         → list recent queries
#
# Expected input (POST /api/query):
#   body: { "question": str, "policyIds": list[str] (optional) }
#
# Expected output:
#   { "queryId": str, "status": "PENDING"|"COMPLETE"|"FAILED", "answer": str, "citations": list }

import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_ENV_VARS = ["QUERY_LOG_TABLE", "DRUG_POLICY_CRITERIA_TABLE", "POLICY_DOCUMENTS_TABLE", "POLICY_DIFFS_TABLE"]
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
    logger.info(json.dumps({"action": "query_request", "event": event}))

    query_id = str(uuid.uuid4())
    return create_response(200, {
        "message": "QueryLambda stub — implement AI logic here",
        "queryId": query_id,
    })
