# Owner: AZ 
# UploadUrlLambda — generates a presigned S3 PUT URL for policy PDF uploads.
#
# Expected input (POST /api/policies/upload-url):
#   body: { "fileName": str, "contentType": str }
#
# Expected output:
#   { "uploadUrl": str, "policyDocId": str, "s3Key": str }

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# TODO: validate env vars at startup (POLICY_BUCKET_NAME, CORS_ORIGIN)
# TODO: init boto3 s3 client at module level


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({"event": event}))

    # TODO: parse body, validate fileName + contentType
    # TODO: generate policyDocId (uuid)
    # TODO: generate presigned PUT URL via s3_client.generate_presigned_url
    # TODO: store pending record in PolicyDocuments table

    cors_origin = os.environ.get("CORS_ORIGIN", "")
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": cors_origin,
            "Content-Type": "application/json",
        },
        "body": json.dumps({"message": "UploadUrlLambda stub"}),
    }
