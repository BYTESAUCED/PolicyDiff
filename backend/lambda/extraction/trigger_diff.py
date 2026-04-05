# Owner: Mohith
# State 7 — TriggerDiffIfVersionExists
#
# Checks whether the PolicyDocuments record has a previousVersionId.
# If yes, asynchronously invokes DiffLambda to compute a temporal diff
# between the old and new policy versions.
#
# Step Functions I/O:
#   Input:  { policyDocId, ..., all passthrough fields }
#   Output: { ..., diffTriggered: bool, diffTargetPolicyId? }

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments")
DIFF_FUNCTION_NAME = os.environ.get("DIFF_FUNCTION_NAME", "")
if not DIFF_FUNCTION_NAME:
    logger.warning(json.dumps({"warning": "missing_env_var", "var": "DIFF_FUNCTION_NAME"}))

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Trigger temporal diff if a previous version of this policy exists."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event is a string and could not be parsed as JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise TypeError(f"Expected event to be a dict, got {type(event).__name__}")
    logger.info(json.dumps({"state": "TriggerDiffIfVersionExists", "policyDocId": event.get("policyDocId")}))

    policy_doc_id: str = event["policyDocId"]

    # 1. Read full policy record to check for previousVersionId
    table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
    result = table.get_item(Key={"policyDocId": policy_doc_id})
    item = result.get("Item")

    if not item:
        logger.warning(json.dumps({"warning": "policy_not_found", "policyDocId": policy_doc_id}))
        return {**event, "diffTriggered": False}

    previous_version_id = item.get("previousVersionId")

    if not previous_version_id:
        logger.info(json.dumps({"action": "no_previous_version", "policyDocId": policy_doc_id}))
        return {**event, "diffTriggered": False}

    # 2. Verify previous version exists
    prev_result = table.get_item(Key={"policyDocId": previous_version_id})
    prev_item = prev_result.get("Item")
    if not prev_item:
        logger.warning(json.dumps({"warning": "previous_version_not_found", "previousVersionId": previous_version_id}))
        return {**event, "diffTriggered": False}

    # 3. Asynchronously invoke DiffLambda
    if not DIFF_FUNCTION_NAME:
        logger.warning("DIFF_FUNCTION_NAME env var not set — skipping diff trigger")
        return {**event, "diffTriggered": False, "diffTargetPolicyId": previous_version_id}

    diff_payload = {
        "diffType": "temporal",
        "policyDocIdOld": previous_version_id,
        "policyDocIdNew": policy_doc_id,
        "drugName": event.get("extractedCriteria", [{}])[0].get("drugName", "unknown") if event.get("extractedCriteria") else "unknown",
        "payerName": item.get("payerName", ""),
        "oldDate": prev_item.get("effectiveDate", ""),
        "newDate": item.get("effectiveDate", ""),
    }

    try:
        lambda_client.invoke(
            FunctionName=DIFF_FUNCTION_NAME,
            InvocationType="Event",  # async — fire and forget
            Payload=json.dumps(diff_payload).encode("utf-8"),
        )
        logger.info(json.dumps({"action": "diff_triggered", "oldPolicyDocId": previous_version_id, "newPolicyDocId": policy_doc_id}))
    except Exception as e:
        logger.error(json.dumps({"error": "diff_invoke_failed", "detail": str(e)}))
        # Non-fatal — the extraction pipeline still succeeded
        return {**event, "diffTriggered": False, "diffError": str(e)}

    return {
        **event,
        "diffTriggered": True,
        "diffTargetPolicyId": previous_version_id,
    }
