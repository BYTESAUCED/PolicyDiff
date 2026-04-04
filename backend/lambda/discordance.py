# Owner: Mohith
# DiscordanceLambda — detect and surface payer discordances for a given drug.
#
# Routes handled:
#   GET /api/discordance                  → list all discordance summaries
#   GET /api/discordance/{drug}/{payer}   → get discordance detail for drug+payer pair
#
# Expected output (list):
#   { "items": [ { "drug": str, "payer": str, "discordanceScore": float, "summary": str } ] }
#
# Expected output (detail):
#   { "drug": str, "payer": str, "criteria": {...}, "industryBaseline": {...}, "gaps": [...] }

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_ENV_VARS = ["DRUG_POLICY_CRITERIA_TABLE", "POLICY_DIFFS_TABLE"]
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
    logger.info(json.dumps({"action": "discordance_request", "event": event}))

    return create_response(200, {"message": "DiscordanceLambda stub — implement AI logic here"})
