# Owner: Mohith
# State 4 — BedrockSchemaExtraction
#
# Sends structured policy text to Bedrock Claude Sonnet to extract
# DrugPolicyCriteria records per the spec schema.
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, structuredTextS3Key,
#             payerName, planType, documentTitle, effectiveDate, ... }
#   Output: { ..., extractedCriteria: [...], extractionCount }

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Bedrock model ID for Claude Sonnet
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250514")
MAX_DOCUMENT_CHARS = 180_000  # Claude Sonnet context limit safety margin


def _invoke_bedrock(prompt: str, max_tokens: int = 8192) -> str:
    """Call Bedrock Claude and return raw text response."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    })

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(response["body"].read().decode("utf-8"))
    # Claude response structure: { content: [{ type: "text", text: "..." }] }
    return result["content"][0]["text"]


def _clean_json_response(text: str) -> str:
    """Strip markdown fences or preamble that the model may add despite instructions."""
    # Remove ```json ... ``` wrapper
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Trim leading/trailing whitespace
    text = text.strip()
    # If it starts with [ or {, assume it's already JSON
    if text and text[0] in ("[", "{"):
        return text
    # Last resort: find first [ or { and take from there
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            return text[i:]
    return text


def _chunk_document(full_text: str, max_chars: int = MAX_DOCUMENT_CHARS) -> list[str]:
    """Split very long documents into chunks that fit Claude's context."""
    if len(full_text) <= max_chars:
        return [full_text]

    chunks: list[str] = []
    lines = full_text.split("\n")
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Extract DrugPolicyCriteria records from structured policy text via Bedrock."""
    logger.info(json.dumps({"state": "BedrockSchemaExtraction", "policyDocId": event.get("policyDocId")}))

    policy_doc_id: str = event["policyDocId"]
    s3_bucket: str = event["s3Bucket"]
    structured_key: str = event["structuredTextS3Key"]

    # Metadata needed for extraction prompt
    payer_name: str = event.get("payerName", "Unknown")
    plan_type: str = event.get("planType", "Commercial")
    doc_title: str = event.get("documentTitle", "Unknown Policy")
    effective_date: str = event.get("effectiveDate", "Unknown")

    # 1. Get structured text from S3
    resp = s3.get_object(Bucket=s3_bucket, Key=structured_key)
    structured_doc = json.loads(resp["Body"].read().decode("utf-8"))
    raw_text = structured_doc.get("rawText", "")

    # Include table data in the document text for completeness
    tables = structured_doc.get("tables", [])
    if tables:
        table_text_parts = ["\n\n--- TABLES EXTRACTED FROM DOCUMENT ---"]
        for i, table in enumerate(tables, 1):
            table_text_parts.append(f"\nTable {i}:")
            for row in table.get("rows", []):
                table_text_parts.append(" | ".join(str(cell) for cell in row))
        raw_text += "\n".join(table_text_parts)

    # 2. Import prompt template
    from extraction.prompts import EXTRACTION_PROMPT

    # 3. Chunk if necessary and run extraction per chunk
    chunks = _chunk_document(raw_text)
    all_criteria: list[dict] = []

    for chunk_idx, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} chars)")

        prompt = EXTRACTION_PROMPT.format(
            payerName=payer_name,
            planType=plan_type,
            documentTitle=doc_title,
            effectiveDate=effective_date,
            documentText=chunk,
        )

        try:
            response_text = _invoke_bedrock(prompt)
            cleaned = _clean_json_response(response_text)
            parsed = json.loads(cleaned)

            if isinstance(parsed, list):
                all_criteria.extend(parsed)
            elif isinstance(parsed, dict):
                # Single record returned
                all_criteria.append(parsed)
            else:
                logger.warning(f"Unexpected response type: {type(parsed)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock response as JSON: {e}")
            logger.error(f"Raw response: {response_text[:500]}")
            # Continue with other chunks rather than failing
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            raise

    logger.info(f"Extracted {len(all_criteria)} drug-indication criteria records")

    # 4. Enrich each record with denormalized metadata
    for record in all_criteria:
        record["policyDocId"] = policy_doc_id
        record["payerName"] = payer_name
        record["effectiveDate"] = effective_date

        # Build composite sort key: drugName#indicationICD10 or drugName#indicationName
        drug = record.get("drugName", "unknown")
        icd10 = record.get("indicationICD10", "")
        indication = record.get("indicationName", "unknown")
        record["drugIndicationId"] = f"{drug}#{icd10}" if icd10 else f"{drug}#{indication}"

    # 5. Write extracted criteria to S3 (intermediate artifact)
    criteria_key = f"{policy_doc_id}/extracted-criteria.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=criteria_key,
        Body=json.dumps(all_criteria, default=str),
        ContentType="application/json",
    )

    return {
        **event,
        "extractedCriteria": all_criteria,
        "extractionCount": len(all_criteria),
        "extractedCriteriaS3Key": criteria_key,
    }
