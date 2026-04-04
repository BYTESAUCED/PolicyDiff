# Owner: Mohith
# State 3.0 — ClassifyDocument
#
# Classifies uploaded documents by type BEFORE Textract / extraction.
# Routes each document to the correct prompt (A–F) or marks it as
# index-only (no extraction needed).
#
# All documents are assumed to be PDF and processed via Textract.
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, s3Key, payerName, documentTitle, ... }
#   Output: { ..., documentClass, documentFormat, extractionPromptId, skipExtraction }

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments")
dynamodb = boto3.resource("dynamodb")


def classify_document(payer_name: str, document_title: str, s3_key: str) -> dict:
    """Classify a policy document and determine extraction routing.

    Returns:
        {
            documentClass: str,
            documentFormat: "pdf",
            extractionPromptId: str | None,
            skipExtraction: bool,
        }
    """
    title_lower = document_title.lower() if document_title else ""
    key_lower = s3_key.lower() if s3_key else ""
    payer_lower = payer_name.lower() if payer_name else ""

    # All documents are PDF — processed via Textract
    document_format = "pdf"

    # Classify by document title / key patterns
    if "maximum dosage" in title_lower or "max dosage" in title_lower:
        doc_class = "max_dosage"
        prompt_id = "D"
    elif "self-administered" in title_lower or "self administered" in title_lower:
        doc_class = "self_admin"
        prompt_id = None
    elif "site of care" in title_lower:
        doc_class = "site_of_care"
        prompt_id = None
    elif "preferred specialty management" in title_lower or "psm" in key_lower:
        doc_class = "preferred_specialty_mgmt"
        prompt_id = "F"
    elif "formulary" in title_lower or "drug guide" in title_lower or "drug list" in title_lower:
        doc_class = "formulary"
        prompt_id = None
    elif "policy update" in title_lower or "policy changes" in title_lower:
        doc_class = "update_bulletin"
        prompt_id = "E"
    elif "formulary exception" in title_lower:
        doc_class = "pa_framework"
        prompt_id = None
    else:
        # Default: drug-specific policy — route by payer
        doc_class = "drug_specific"
        payer_prompt_map = {
            "unitedhealthcare": "A", "uhc": "A", "united": "A",
            "aetna": "B",
            "cigna": "C",
        }
        prompt_id = payer_prompt_map.get(payer_lower, None)  # None → use generic fallback

    skip_extraction = prompt_id is None

    return {
        "documentClass": doc_class,
        "documentFormat": document_format,
        "extractionPromptId": prompt_id,
        "skipExtraction": skip_extraction,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Classify document type and determine extraction routing."""
    logger.info(json.dumps({"state": "ClassifyDocument", "policyDocId": event.get("policyDocId")}))

    payer_name = event.get("payerName", "")
    document_title = event.get("documentTitle", "")
    s3_key = event.get("s3Key", "")

    classification = classify_document(payer_name, document_title, s3_key)

    logger.info(json.dumps({
        "classification": classification,
        "payer": payer_name,
        "title": document_title,
    }))

    # Update PolicyDocuments table with classification metadata
    try:
        table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
        table.update_item(
            Key={"policyDocId": event["policyDocId"]},
            UpdateExpression=(
                "SET documentClass = :dc, documentFormat = :df, "
                "extractionPromptId = :ep, boilerplateStripped = :bs"
            ),
            ExpressionAttributeValues={
                ":dc": classification["documentClass"],
                ":df": classification["documentFormat"],
                ":ep": classification["extractionPromptId"] or "none",
                ":bs": False,  # will be set to True after State 3 strips boilerplate
            },
        )
    except Exception as e:
        logger.warning(f"Failed to update policy document classification: {e}")

    return {
        **event,
        **classification,
    }
