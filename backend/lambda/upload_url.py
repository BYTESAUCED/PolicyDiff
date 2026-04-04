# Owner: AZ
# UploadUrlLambda — generates presigned S3 PUT URL for direct PDF upload.
# POST /api/policies/upload-url
# Response: { uploadUrl, policyDocId, s3Key }

import json
import logging
import os
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Validate env vars at module load; fail fast on cold start if missing
_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET_NAME")
if not _BUCKET_NAME:
    logger.error(json.dumps({"error": "missing_env_var", "var": "DOCUMENTS_BUCKET_NAME"}))

# ADR: Module-level client | Reused across warm invocations for lower latency
s3_client = boto3.client("s3")


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
    logger.info(json.dumps({
        "action": "upload_url_request",
        "requestId": (event.get("requestContext") or {}).get("requestId"),
        "sourceIp": (event.get("requestContext") or {}).get("http", {}).get("sourceIp"),
    }))

    bucket_name = os.environ.get("DOCUMENTS_BUCKET_NAME")
    if not bucket_name:
        logger.error(json.dumps({"error": "missing_env_var", "var": "DOCUMENTS_BUCKET_NAME"}))
        return create_response(500, {"message": "Server configuration error"})

    try:
        policy_doc_id = str(uuid.uuid4())
        s3_key = f"raw/{policy_doc_id}/raw.pdf"

        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": s3_key,
                "ContentType": "application/pdf",
            },
            ExpiresIn=300,
        )

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
            "error": "s3_client_error",
            "detail": str(e),
            "code": e.response["Error"]["Code"],
        }))
        return create_response(500, {"message": "Failed to generate upload URL"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return create_response(500, {"message": "Internal server error"})
