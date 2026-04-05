# Owner: AZ
# PolicyCrudLambda — CRUD operations on PolicyDocuments and DrugPolicyCriteria tables.
# Also handles UserPreferences read/write for watched-drug dashboard.
#
# Routes handled:
#   POST   /api/policies                  → create policy record
#   GET    /api/policies/{id}             → get policy by policyDocId
#   GET    /api/policies/{id}/status      → get extraction status
#   GET    /api/policies/{id}/criteria    → get extracted drug criteria
#   GET    /api/policies                  → list policies (optional filters + pagination)
#   DELETE /api/policies/{id}             → delete policy record
#   GET    /api/users/me/preferences      → get UserPreferences for caller
#   PUT    /api/users/me/preferences      → upsert UserPreferences for caller

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

# ADR: Module-level resource | Reused across warm invocations
dynamodb = boto3.resource("dynamodb")

_REQUIRED_ENV_VARS = [
    "POLICY_DOCUMENTS_TABLE",
    "DRUG_POLICY_CRITERIA_TABLE",
    "USER_PREFERENCES_TABLE",
]
for _var in _REQUIRED_ENV_VARS:
    if not os.environ.get(_var):
        logger.warning(json.dumps({"warning": "missing_env_var", "var": _var}))

ROLE_CLAIM = "https://policydiff.com/role"
REQUIRED_CREATE_FIELDS = ["payerName", "planType", "documentTitle", "effectiveDate", "policyDocId"]


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


def get_caller_claims(event: dict) -> dict:
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}


def require_admin(event: dict) -> bool:
    """Returns True if caller has admin role, False otherwise."""
    claims = get_caller_claims(event)
    return claims.get(ROLE_CLAIM) == "admin"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(json.dumps({
        "action": "policy_crud_request",
        "httpMethod": event.get("httpMethod") or (event.get("requestContext") or {}).get("http", {}).get("method"),
        "resource": event.get("resource") or event.get("rawPath"),
        "requestId": (event.get("requestContext") or {}).get("requestId"),
    }))

    # ADR: Support both REST API V1 (httpMethod/resource) and HTTP API V2 (requestContext.http.method/rawPath)
    http_method = (
        event.get("httpMethod")
        or (event.get("requestContext") or {}).get("http", {}).get("method", "")
    ).upper()
    resource = (
        event.get("resource")
        or event.get("rawPath")
        or ""
    )

    try:
        # POST /api/policies — create policy record (admin only)
        if http_method == "POST" and resource == "/api/policies":
            return handle_create_policy(event)

        # GET /api/policies/{id}/status
        elif http_method == "GET" and (resource == "/api/policies/{id}/status" or resource.endswith("/status")):
            return handle_get_status(event)

        # GET /api/policies/{id}/criteria
        elif http_method == "GET" and (resource == "/api/policies/{id}/criteria" or resource.endswith("/criteria")):
            return handle_get_criteria(event)

        # GET /api/policies/{id}
        elif http_method == "GET" and (resource == "/api/policies/{id}" or (resource.startswith("/api/policies/") and resource.count("/") == 3)):
            return handle_get_policy(event)

        # GET /api/policies — list with optional filters
        elif http_method == "GET" and resource == "/api/policies":
            return handle_list_policies(event)

        # DELETE /api/policies/{id} (admin only)
        elif http_method == "DELETE" and (resource == "/api/policies/{id}" or resource.startswith("/api/policies/")):
            return handle_delete_policy(event)

        # GET /api/users/me/preferences
        elif http_method == "GET" and resource == "/api/users/me/preferences":
            return handle_get_preferences(event)

        # PUT /api/users/me/preferences
        elif http_method == "PUT" and resource == "/api/users/me/preferences":
            return handle_put_preferences(event)

        else:
            return create_response(404, {"message": "Route not found"})

    except ClientError as e:
        logger.error(json.dumps({"error": "dynamodb_client_error", "detail": str(e)}))
        return create_response(500, {"message": "Internal server error"})

    except Exception as e:
        logger.error(json.dumps({"error": "unhandled_exception", "detail": str(e)}))
        return create_response(500, {"message": "Internal server error"})


def _find_previous_version(table, payer_name: str, plan_type: str, drug_name: str) -> str | None:
    # ADR: Server-side version linking | Prevents client from forging previousVersionId
    try:
        result = table.query(
            IndexName="payerName-effectiveDate-index",
            KeyConditionExpression=Key("payerName").eq(payer_name),
        )
        candidates = [
            item for item in result.get("Items", [])
            if item.get("planType") == plan_type and item.get("drugName") == drug_name
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.get("effectiveDate", ""))["policyDocId"]
    except ClientError as e:
        logger.error(json.dumps({"error": "find_previous_version_failed", "detail": str(e)}))
        return None


def handle_create_policy(event: dict) -> dict:
    if not require_admin(event):
        return create_response(403, {"message": "Forbidden: admin role required"})

    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return create_response(400, {"message": "Invalid JSON body"})

    missing = [f for f in REQUIRED_CREATE_FIELDS if not body.get(f)]
    if missing:
        logger.warning(json.dumps({"warning": "missing_required_fields", "fields": missing}))
        return create_response(400, {"message": "Missing required fields", "missingFields": missing})

    table = dynamodb.Table(table_name)
    item = {
        "policyDocId": body["policyDocId"],
        "payerName": body["payerName"],
        "planType": body["planType"],
        "documentTitle": body["documentTitle"],
        "effectiveDate": body["effectiveDate"],
        "extractionStatus": "pending",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    # Include optional fields if provided
    for opt in ["s3Key", "version", "drugName"]:
        if body.get(opt) is not None:
            item[opt] = body[opt]

    # Auto-link previous version server-side when drugName is present
    if body.get("drugName"):
        previous_version_id = _find_previous_version(
            table, body["payerName"], body["planType"], body.get("drugName", "")
        )
        if previous_version_id:
            item["previousVersionId"] = previous_version_id

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(policyDocId) OR extractionStatus = :pending",
            ExpressionAttributeValues={":pending": "pending"},
        )
        logger.info(json.dumps({"action": "policy_created", "policyDocId": item["policyDocId"]}))
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        # Extraction already in progress or complete — only update metadata fields
        update_expr_parts = [
            "payerName = :payer",
            "planType = :plan",
            "documentTitle = :title",
            "effectiveDate = :date",
            "updatedAt = :updated",
        ]
        expr_values = {
            ":payer": item["payerName"],
            ":plan": item["planType"],
            ":title": item["documentTitle"],
            ":date": item["effectiveDate"],
            ":updated": datetime.now(timezone.utc).isoformat(),
        }
        for opt_field, expr_key in [("s3Key", ":s3key"), ("version", ":ver"), ("drugName", ":drug")]:
            if item.get(opt_field):
                update_expr_parts.append(f"{opt_field} = {expr_key}")
                expr_values[expr_key] = item[opt_field]
        if item.get("previousVersionId"):
            update_expr_parts.append("previousVersionId = :prev")
            expr_values[":prev"] = item["previousVersionId"]

        table.update_item(
            Key={"policyDocId": item["policyDocId"]},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeValues=expr_values,
        )
        logger.info(json.dumps({"action": "policy_metadata_updated_safe", "policyDocId": item["policyDocId"]}))
    return create_response(201, item)


def handle_get_policy(event: dict) -> dict:
    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    policy_doc_id = (event.get("pathParameters") or {}).get("id")
    if not policy_doc_id:
        return create_response(400, {"message": "Missing path parameter: id"})

    table = dynamodb.Table(table_name)
    result = table.get_item(Key={"policyDocId": policy_doc_id})
    item = result.get("Item")
    if not item:
        return create_response(404, {"message": "Policy not found"})

    return create_response(200, item)


def handle_get_status(event: dict) -> dict:
    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    policy_doc_id = (event.get("pathParameters") or {}).get("id")
    if not policy_doc_id:
        return create_response(400, {"message": "Missing path parameter: id"})

    table = dynamodb.Table(table_name)
    result = table.get_item(
        Key={"policyDocId": policy_doc_id},
        ProjectionExpression="extractionStatus, extractionJobId",
    )
    item = result.get("Item")
    if not item:
        return create_response(404, {"message": "Policy not found"})

    return create_response(200, {
        "extractionStatus": item.get("extractionStatus"),
        "extractionJobId": item.get("extractionJobId"),
    })


def handle_get_criteria(event: dict) -> dict:
    table_name = os.environ.get("DRUG_POLICY_CRITERIA_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    policy_doc_id = (event.get("pathParameters") or {}).get("id")
    if not policy_doc_id:
        return create_response(400, {"message": "Missing path parameter: id"})

    table = dynamodb.Table(table_name)
    result = table.query(
        KeyConditionExpression=Key("policyDocId").eq(policy_doc_id)
    )
    return create_response(200, {"items": result.get("Items", [])})


def handle_list_policies(event: dict) -> dict:
    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    params = event.get("queryStringParameters") or {}
    payer_name = params.get("payerName")
    drug_name = params.get("drugName")

    try:
        limit = min(int(params.get("limit", 20)), 100)
    except (ValueError, TypeError):
        limit = 20

    next_token = params.get("nextToken")

    table = dynamodb.Table(table_name)
    scan_kwargs: dict = {"Limit": limit}

    if next_token:
        try:
            scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
        except (json.JSONDecodeError, TypeError):
            return create_response(400, {"message": "Invalid nextToken"})

    if payer_name:
        # ADR: GSI query for payerName filter | Avoids full table scan
        exclusive_start = {}
        if next_token:
            try:
                exclusive_start = {"ExclusiveStartKey": json.loads(next_token)}
            except (json.JSONDecodeError, TypeError):
                return create_response(400, {"message": "Invalid nextToken"})
        result = table.query(
            IndexName="payerName-effectiveDate-index",
            KeyConditionExpression=Key("payerName").eq(payer_name),
            Limit=limit,
            **exclusive_start,
        )
    else:
        result = table.scan(**scan_kwargs)

    response_body: dict = {"items": result.get("Items", [])}
    # Filter out soft-deleted records
    response_body["items"] = [
        i for i in response_body["items"]
        if i.get("extractionStatus") != "deleted"
    ]
    # Apply drugName client-side filter (PolicyDocuments doesn't have a drugName GSI)
    if drug_name:
        response_body["items"] = [
            i for i in response_body["items"]
            if i.get("drugName", "").lower() == drug_name.lower()
        ]
    last_key = result.get("LastEvaluatedKey")
    if last_key:
        response_body["nextToken"] = json.dumps(last_key)

    return create_response(200, response_body)


def handle_delete_policy(event: dict) -> dict:
    if not require_admin(event):
        return create_response(403, {"message": "Forbidden: admin role required"})

    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    policy_doc_id = (event.get("pathParameters") or {}).get("id")
    if not policy_doc_id:
        return create_response(400, {"message": "Missing path parameter: id"})

    table = dynamodb.Table(table_name)
    # ADR: Soft delete | Set extractionStatus = "deleted" to preserve audit trail and diff history
    table.update_item(
        Key={"policyDocId": policy_doc_id},
        UpdateExpression="SET extractionStatus = :s, deletedAt = :d",
        ExpressionAttributeValues={
            ":s": "deleted",
            ":d": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(json.dumps({"action": "policy_soft_deleted", "policyDocId": policy_doc_id}))
    return create_response(200, {"deleted": True})


def handle_get_preferences(event: dict) -> dict:
    table_name = os.environ.get("USER_PREFERENCES_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    claims = get_caller_claims(event)
    user_id = claims.get("sub")
    if not user_id:
        return create_response(401, {"message": "Unable to determine user identity"})

    table = dynamodb.Table(table_name)
    result = table.get_item(Key={"userId": user_id})
    item = result.get("Item", {"userId": user_id, "watchedDrugs": [], "watchedPayers": []})
    return create_response(200, item)


def handle_put_preferences(event: dict) -> dict:
    table_name = os.environ.get("USER_PREFERENCES_TABLE")
    if not table_name:
        return create_response(500, {"message": "Server configuration error"})

    claims = get_caller_claims(event)
    user_id = claims.get("sub")
    if not user_id:
        return create_response(401, {"message": "Unable to determine user identity"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return create_response(400, {"message": "Invalid JSON body"})

    table = dynamodb.Table(table_name)
    item = {
        "userId": user_id,
        "watchedDrugs": body.get("watchedDrugs", []),
        "watchedPayers": body.get("watchedPayers", []),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    user_id_hash = hashlib.sha256(user_id.encode()).hexdigest()[:12]
    logger.info(json.dumps({"action": "preferences_updated", "userIdHash": user_id_hash}))
    return create_response(200, item)
