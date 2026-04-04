# Owner: Mohith
# State 6 — WriteToDynamoDB
#
# Batch-writes all scored DrugPolicyCriteria records to DynamoDB
# and updates the PolicyDocuments record with extraction status.
#
# Step Functions I/O:
#   Input:  { policyDocId, extractedCriteria: [...], confidenceSummary, ... }
#   Output: { ..., writeStatus: "complete", recordsWritten }

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments")
DRUG_POLICY_CRITERIA_TABLE = os.environ.get("DRUG_POLICY_CRITERIA_TABLE", "DrugPolicyCriteria")

dynamodb = boto3.resource("dynamodb")


def _convert_floats(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


def _batch_write_criteria(criteria: list[dict]) -> int:
    """Batch write DrugPolicyCriteria records. Returns count written."""
    table = dynamodb.Table(DRUG_POLICY_CRITERIA_TABLE)
    now = datetime.now(timezone.utc).isoformat()
    written = 0

    with table.batch_writer() as batch:
        for record in criteria:
            # Ensure required keys exist
            if not record.get("policyDocId") or not record.get("drugIndicationId"):
                logger.warning(f"Skipping record missing required keys: {record.get('drugName', '?')}")
                continue

            # Add extraction timestamp
            record["extractedAt"] = now

            # Convert floats to Decimal (DynamoDB requirement)
            item = _convert_floats(record)

            # Remove any None values (DynamoDB doesn't support them)
            item = {k: v for k, v in item.items() if v is not None}

            try:
                batch.put_item(Item=item)
                written += 1
            except Exception as e:
                logger.error(f"Failed to write record {record.get('drugIndicationId')}: {e}")

    return written


def _update_policy_status(
    policy_doc_id: str,
    status: str,
    indications_found: int,
    confidence_summary: dict,
) -> None:
    """Update the PolicyDocuments table with extraction results."""
    table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    update_expr = (
        "SET extractionStatus = :s, "
        "indicationsFound = :n, "
        "extractionProgress = :p, "
        "confidenceSummary = :cs, "
        "updatedAt = :u"
    )
    expr_values = {
        ":s": status,
        ":n": indications_found,
        ":p": f"Extracted {indications_found} drug-indication pairs",
        ":cs": _convert_floats(confidence_summary),
        ":u": now,
    }

    try:
        table.update_item(
            Key={"policyDocId": policy_doc_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        logger.info(f"Updated policy {policy_doc_id} status to '{status}'")
    except Exception as e:
        logger.error(f"Failed to update policy status: {e}")
        raise


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Batch write extracted criteria to DynamoDB and update policy status."""
    logger.info(json.dumps({"state": "WriteToDynamoDB", "policyDocId": event.get("policyDocId")}))

    policy_doc_id: str = event["policyDocId"]
    criteria: list[dict] = event.get("extractedCriteria", [])
    confidence_summary: dict = event.get("confidenceSummary", {})

    if not criteria:
        logger.warning(f"No criteria to write for policy {policy_doc_id}")
        _update_policy_status(policy_doc_id, "complete", 0, confidence_summary)
        return {
            **event,
            "writeStatus": "complete",
            "recordsWritten": 0,
        }

    # 1. Batch write criteria records
    records_written = _batch_write_criteria(criteria)
    logger.info(f"Wrote {records_written}/{len(criteria)} criteria records to DynamoDB")

    # 2. Update policy document status
    review_count = confidence_summary.get("reviewCount", 0)
    status = "review_required" if review_count > 0 else "complete"

    _update_policy_status(policy_doc_id, status, records_written, confidence_summary)

    return {
        **event,
        "writeStatus": "complete",
        "recordsWritten": records_written,
    }
