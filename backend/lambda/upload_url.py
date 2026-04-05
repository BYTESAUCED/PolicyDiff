# Owner: AZ
# UploadUrlLambda — generates presigned S3 PUT URL for direct PDF upload.
# POST /api/policies/upload-url
# Response: { uploadUrl, policyDocId, s3Key }

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

# Validate env vars at module load; fail fast on cold start if missing
_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET_NAME")
if not _BUCKET_NAME:
    logger.error(json.dumps({"error": "missing_env_var", "var": "DOCUMENTS_BUCKET_NAME"}))
_TABLE_NAME = os.environ.get("POLICY_DOCUMENTS_TABLE")
if not _TABLE_NAME:
    logger.error(json.dumps({"error": "missing_env_var", "var": "POLICY_DOCUMENTS_TABLE"}))

# ADR: Module-level clients | Reused across warm invocations for lower latency
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def create_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({
        "action": "upload_url_request",
        "requestId": (event.get("requestContext") or {}).get("requestId"),
    }))

    bucket_name = os.environ.get("DOCUMENTS_BUCKET_NAME")
    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not bucket_name or not table_name:
        logger.error(json.dumps({"error": "missing_env_var", "vars": ["DOCUMENTS_BUCKET_NAME", "POLICY_DOCUMENTS_TABLE"]}))
        return create_response(500, {"message": "Server configuration error"})

    try:
        body: dict = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError:
                return create_response(400, {"message": "Invalid JSON body"})

        policy_doc_id = str(uuid.uuid4())
        s3_key = f"raw/{policy_doc_id}/raw.pdf"

        # ── Duplicate detection ───────────────────────────────────────────────
        # Check if a non-deleted policy with same payer + title + effectiveDate exists
        payer_name = body.get("payerName", "")
        document_title = body.get("documentTitle", "")
        effective_date = body.get("effectiveDate", "")

        if payer_name and effective_date:
            try:
                from boto3.dynamodb.conditions import Key as DKey
                table = dynamodb.Table(table_name)
                existing = table.query(
                    IndexName="payerName-effectiveDate-index",
                    KeyConditionExpression=DKey("payerName").eq(payer_name) & DKey("effectiveDate").eq(effective_date),
                    Limit=10,
                )
                for item in existing.get("Items", []):
                    if (
                        item.get("extractionStatus") not in ("deleted", "PENDING")
                        and item.get("documentTitle", "").lower() == document_title.lower()
                    ):
                        logger.info(json.dumps({"action": "duplicate_detected", "existingId": item["policyDocId"]}))
                        return create_response(409, {
                            "message": "A policy with the same payer, title, and effective date already exists.",
                            "existingPolicyDocId": item["policyDocId"],
                            "duplicate": True,
                        })
            except Exception as e:
                logger.warning(json.dumps({"warning": "duplicate_check_failed", "detail": str(e)}))
        # ─────────────────────────────────────────────────────────────────────

        # ADR: ContentLength not enforceable on presigned PUT | Use S3 Object Lambda or bucket policy for size limits
        # Max 50MB enforced client-side; server-side enforcement requires presigned POST (not PUT)
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": s3_key,
                "ContentType": "application/pdf",
            },
            ExpiresIn=300,
        )

        # ADR: Create PolicyDocuments row at presign time | classify_document and bedrock_extract
        # enrich metadata only if the row already exists; without this row, extraction runs with
        # empty payer/title/date context when POST /api/policies hasn't been called yet
        now = datetime.now(timezone.utc).isoformat()
        item: dict = {
            "policyDocId": policy_doc_id,
            "s3Key": s3_key,
            "extractionStatus": "PENDING",
            "createdAt": now,
        }
        # Carry forward any metadata the client provided at presign time
        for field in ("payerName", "planType", "documentTitle", "effectiveDate", "policyNumber", "drugName"):
            if body.get(field):
                item[field] = body[field]

        dynamodb.Table(table_name).put_item(Item=item)

        logger.info(json.dumps({
            "action": "presigned_url_generated",
            "policyDocId": policy_doc_id,
            "s3Key": s3_key,
        }))

        return create_response(200, {
            "uploadUrl": upload_url,
            "policyDocId": policy_doc_id,
            "s3Key": s3_key,
        })

    except ClientError as e:
        logger.error(json.dumps({
            "error": "aws_client_error",
            "detail": str(e),
            "code": e.response["Error"]["Code"],
        }))
        return create_response(500, {"message": "Failed to generate upload URL"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return create_response(500, {"message": "Internal server error"})
