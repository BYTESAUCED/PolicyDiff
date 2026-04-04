# Owner: AZ
# PolicyMonitorLambda — monitors S3 inbox/ prefix for new PDFs, moves to raw/ to trigger extraction.
# Triggered by: EventBridge Scheduler (daily)
#
# NOTE: Auto-scraping payer websites is not feasible for hackathon scope.
# Aetna CPBs are HTML-only (no PDF endpoint). Cigna blocks automated requests.
# UHC requires navigating a search UI. Workflow: manually download PDFs and
# drop into the inbox/ prefix, or upload via the UI at POST /api/policies/upload-url.

import json
import logging
import os
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET_NAME")
if not _BUCKET_NAME:
    logger.warning(json.dumps({"warning": "missing_env_var", "var": "DOCUMENTS_BUCKET_NAME"}))

# ADR: Module-level client | Reused across warm invocations
s3_client = boto3.client("s3")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({
        "action": "policy_monitor_start",
        "source": event.get("source"),
        "detail-type": event.get("detail-type"),
    }))

    bucket_name = os.environ.get("DOCUMENTS_BUCKET_NAME")
    if not bucket_name:
        logger.error(json.dumps({"error": "missing_env_var", "var": "DOCUMENTS_BUCKET_NAME"}))
        return {"processed": 0, "error": "DOCUMENTS_BUCKET_NAME not set"}

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix="inbox/")

        processed = 0
        for page in pages:
            for obj in page.get("Contents", []):
                source_key = obj["Key"]
                if source_key == "inbox/" or not source_key.endswith(".pdf"):
                    continue

                policy_doc_id = str(uuid.uuid4())
                dest_key = f"raw/{policy_doc_id}/raw.pdf"

                s3_client.copy_object(
                    Bucket=bucket_name,
                    CopySource={"Bucket": bucket_name, "Key": source_key},
                    Key=dest_key,
                )
                s3_client.delete_object(Bucket=bucket_name, Key=source_key)

                logger.info(json.dumps({
                    "action": "inbox_file_moved",
                    "policyDocId": policy_doc_id,
                    "sourceKey": source_key,
                    "destKey": dest_key,
                }))
                processed += 1

        if processed == 0:
            logger.info(json.dumps({"action": "inbox_empty"}))

        logger.info(json.dumps({"action": "policy_monitor_complete", "processed": processed}))
        return {"processed": processed}

    except ClientError as e:
        logger.error(json.dumps({"error": "s3_client_error", "detail": str(e)}))
        return {"processed": 0, "error": "S3 operation failed"}

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return {"processed": 0, "error": "Internal error"}
