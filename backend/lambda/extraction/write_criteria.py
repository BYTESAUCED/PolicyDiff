# Owner: Mohith
# State 6 — WriteToDynamoDB
#
# Batch-writes all scored DrugPolicyCriteria records to DynamoDB
# and updates the PolicyDocuments record with extraction status.
#
# Extended for hackathon documents:
#   - FormularyEntry records (Priority Health B_FORMULARY) routed to
#     FORMULARY_ENTRIES_TABLE when set, else DrugPolicyCriteria table
#   - New schema fields written as-is (DynamoDB is schemaless):
#     universalCriteria, approvalPhase, approvalDurationMonths,
#     productName, productGroup, dosingPerIndication
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
# Falls back to DrugPolicyCriteria if a dedicated formulary table is not provisioned
FORMULARY_ENTRIES_TABLE = os.environ.get("FORMULARY_ENTRIES_TABLE", DRUG_POLICY_CRITERIA_TABLE)
DOCUMENTS_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET_NAME", "")

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")


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
            if not record.get("policyDocId") or not record.get("drugIndicationId"):
                logger.warning(f"Skipping record missing required keys: {record.get('drugName', '?')}")
                continue

            record["extractedAt"] = now
            item = _convert_floats(record)
            item = {k: v for k, v in item.items() if v is not None}

            try:
                batch.put_item(Item=item)
                written += 1
            except Exception as e:
                logger.error(f"Failed to write record {record.get('drugIndicationId')}: {e}")

    return written


def _batch_write_formulary_entries(entries: list[dict]) -> int:
    """Batch write FormularyEntry records.

    PK: policyDocId, SK: drugIndicationId = {hcpcsCode}#{drugName}
    Uses FORMULARY_ENTRIES_TABLE (defaults to DrugPolicyCriteria if not configured).
    """
    table = dynamodb.Table(FORMULARY_ENTRIES_TABLE)
    now = datetime.now(timezone.utc).isoformat()
    written = 0

    with table.batch_writer() as batch:
        for entry in entries:
            policy_doc_id = entry.get("policyDocId", "")
            hcpcs = entry.get("hcpcsCode", "unknown")
            drug = entry.get("drugName", "unknown")

            if not policy_doc_id:
                logger.warning("Skipping formulary entry: missing policyDocId")
                continue

            # Use drugIndicationId slot as SK for table compatibility
            entry.setdefault("drugIndicationId", f"{hcpcs}#{drug}")
            entry["extractedAt"] = now

            item = _convert_floats(entry)
            item = {k: v for k, v in item.items() if v is not None}

            try:
                batch.put_item(Item=item)
                written += 1
            except Exception as e:
                logger.error(f"Failed to write formulary entry {hcpcs}#{drug}: {e}")

    return written


def _update_policy_status(
    policy_doc_id: str,
    status: str,
    indications_found: int,
    confidence_summary: dict,
    event: dict | None = None,
) -> None:
    """Update the PolicyDocuments table with extraction results.

    Race condition guard: creates a stub record if the PolicyDocuments entry
    doesn't exist yet (EventBridge fires before POST /api/policies).
    """
    table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    if event:
        try:
            table.put_item(
                Item={
                    "policyDocId": policy_doc_id,
                    "payerName": event.get("payerName", "Unknown"),
                    "planType": event.get("planType", ""),
                    "documentTitle": event.get("documentTitle", ""),
                    "effectiveDate": event.get("effectiveDate", ""),
                    "s3Key": event.get("s3Key", ""),
                    "extractionStatus": "extracting",
                    "createdAt": now,
                    "updatedAt": now,
                },
                ConditionExpression="attribute_not_exists(policyDocId)",
            )
            logger.info(f"Created stub PolicyDocuments record for {policy_doc_id}")
        except Exception:
            pass  # Record already exists — expected

    try:
        table.update_item(
            Key={"policyDocId": policy_doc_id},
            UpdateExpression=(
                "SET extractionStatus = :s, "
                "indicationsFound = :n, "
                "extractionProgress = :p, "
                "confidenceSummary = :cs, "
                "updatedAt = :u"
            ),
            ExpressionAttributeValues={
                ":s": status,
                ":n": indications_found,
                ":p": f"Extracted {indications_found} drug-indication pairs",
                ":cs": _convert_floats(confidence_summary),
                ":u": now,
            },
        )
        logger.info(f"Updated policy {policy_doc_id} status to '{status}'")
    except Exception as e:
        logger.error(f"Failed to update policy status: {e}")
        raise


def _write_excerpt_files(policy_doc_id: str, criteria: list[dict], bucket: str) -> list[str]:
    """Write per-criteria rawExcerpt text files to S3 for embed_and_index.

    Key format: {policyDocId}/excerpts/{drugIndicationId}.txt
    Returns list of S3 keys written.
    """
    if not bucket:
        logger.warning(json.dumps({"warning": "DOCUMENTS_BUCKET_NAME not set, skipping excerpt write"}))
        return []

    keys: list[str] = []
    for record in criteria:
        drug_indication_id = record.get("drugIndicationId", "")
        raw_excerpt = record.get("rawExcerpt", "") or record.get("indicationName", "")
        if not drug_indication_id or not raw_excerpt:
            continue

        # Sanitize key segment — replace characters invalid in S3 keys
        safe_id = drug_indication_id.replace("/", "_").replace("\\", "_")
        key = f"{policy_doc_id}/excerpts/{safe_id}.txt"

        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=raw_excerpt.encode("utf-8"),
                ContentType="text/plain",
            )
            keys.append(key)
        except Exception as e:
            logger.warning(json.dumps({"warning": "excerpt_write_failed", "key": key, "reason": str(e)}))

    logger.info(json.dumps({"action": "excerpts_written", "count": len(keys), "policyDocId": policy_doc_id}))
    return keys


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Batch write extracted criteria to DynamoDB and update policy status."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event is a string and could not be parsed as JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise TypeError(f"Expected event to be a dict, got {type(event).__name__}")
    logger.info(json.dumps({"state": "WriteToDynamoDB", "policyDocId": event.get("policyDocId")}))

    policy_doc_id: str = event["policyDocId"]
    criteria: list[dict] = event.get("extractedCriteria", [])
    confidence_summary: dict = event.get("confidenceSummary", {})
    bucket: str = event.get("s3Bucket", DOCUMENTS_BUCKET_NAME)

    if not criteria:
        logger.warning(f"No criteria to write for policy {policy_doc_id}")
        _update_policy_status(policy_doc_id, "complete", 0, confidence_summary, event)
        return {**event, "writeStatus": "complete", "recordsWritten": 0, "excerptKeys": []}

    # Route formulary entries separately from clinical criteria
    formulary_entries = [r for r in criteria if r.get("documentClass") == "formulary"]
    clinical_criteria = [r for r in criteria if r.get("documentClass") != "formulary"]

    records_written = 0

    if clinical_criteria:
        written = _batch_write_criteria(clinical_criteria)
        records_written += written
        logger.info(f"Wrote {written}/{len(clinical_criteria)} clinical criteria records")

    if formulary_entries:
        written = _batch_write_formulary_entries(formulary_entries)
        records_written += written
        logger.info(f"Wrote {written}/{len(formulary_entries)} formulary entries to {FORMULARY_ENTRIES_TABLE}")

    # Write rawExcerpt text files to S3 so embed_and_index can vectorise them
    excerpt_keys = _write_excerpt_files(policy_doc_id, criteria, bucket)

    review_count = confidence_summary.get("reviewCount", 0)
    status = "review_required" if review_count > 0 else "complete"
    _update_policy_status(policy_doc_id, status, records_written, confidence_summary, event)

    return {**event, "writeStatus": "complete", "recordsWritten": records_written, "excerptKeys": excerpt_keys}
