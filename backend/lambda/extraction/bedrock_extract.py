# Owner: Mohith
# State 4 — BedrockSchemaExtraction
#
# Sends structured policy text to Bedrock Claude Sonnet to extract
# DrugPolicyCriteria records per the spec schema.
#
# Enhanced per policy-pdf-analysis.md:
#   - Two-pass ICD-10 pre-extraction (Section 7.4)
#   - Payer-specific prompt routing A/B/C (Section 5)
#   - Document class routing for D/E/F (Section 5)
#   - Indication-level chunking (Section 7.8)
#   - Skip extraction for index-only document classes
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, structuredTextS3Key,
#             payerName, planType, documentTitle, effectiveDate,
#             documentClass, extractionPromptId, skipExtraction, ... }
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
dynamodb = boto3.resource("dynamodb")

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
if not BEDROCK_MODEL_ID:
    logger.warning(json.dumps({"warning": "missing_env_var", "var": "BEDROCK_MODEL_ID"}))
MAX_DOCUMENT_CHARS = 180_000


def _enrich_event_from_dynamo(event: dict) -> dict:
    """Fetch real metadata from PolicyDocuments if payerName is missing."""
    if event.get("payerName"):
        return event  # Already have metadata

    policy_doc_id = event.get("policyDocId")
    if not policy_doc_id:
        return event

    table_name = os.environ.get("POLICY_DOCUMENTS_TABLE")
    if not table_name:
        return event

    try:
        table = dynamodb.Table(table_name)
        result = table.get_item(
            Key={"policyDocId": policy_doc_id},
            ProjectionExpression="payerName, planType, documentTitle, effectiveDate, drugName",
        )
        item = result.get("Item")
        if item:
            return {**event, **{k: v for k, v in item.items() if v}}
    except Exception as e:
        logger.warning(json.dumps({"warning": "dynamo_enrich_failed", "detail": str(e)}))

    return event


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
    return result["content"][0]["text"]


def _clean_json_response(text: str) -> str:
    """Strip markdown fences or preamble from model response."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    text = text.strip()
    if text and text[0] in ("[", "{"):
        return text
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
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


# ── ICD-10 Pre-Extraction Pass (Section 7.4) ─────────────────────────────

def _extract_icd10_mapping(document_text: str) -> str:
    """Run ICD-10 pre-extraction pass before main criteria extraction.

    Returns JSON string of ICD-10 mapping to inject into the main prompt.
    """
    from extraction.prompts import ICD10_EXTRACTION_PROMPT

    # Only send ~20k chars max for the ICD-10 pass — focus on coding sections
    text_for_icd = document_text
    # Try to find the coding section and send a focused window
    for marker in ["Applicable Codes", "Coding Information", "Coding"]:
        idx = document_text.find(marker)
        if idx >= 0:
            start = max(0, idx - 500)
            end = min(len(document_text), idx + 10000)
            text_for_icd = document_text[start:end]
            break

    prompt = ICD10_EXTRACTION_PROMPT.format(documentText=text_for_icd)

    try:
        response = _invoke_bedrock(prompt, max_tokens=2048)
        cleaned = _clean_json_response(response)
        # Validate it's parseable
        parsed = json.loads(cleaned)
        return json.dumps(parsed, default=str)
    except Exception as e:
        logger.warning(json.dumps({"warning": "icd10_extraction_failed", "detail": str(e)}))
        return json.dumps({"icd10Mapping": []})


# ── Prompt selection ──────────────────────────────────────────────────────

def _get_prompt_template(prompt_id: str, payer_name: str, doc_class: str):
    """Get the correct prompt template based on classification."""
    from extraction.prompts import (
        PROMPT_MAP, EXTRACTION_PROMPT,
        PROMPT_A_UHC, PROMPT_B_AETNA, PROMPT_C_CIGNA,
        PROMPT_D_DOSING, PROMPT_E_CHANGES, PROMPT_F_PSM,
    )

    if prompt_id:
        prompt_lookup = {
            "A": PROMPT_A_UHC,
            "B": PROMPT_B_AETNA,
            "C": PROMPT_C_CIGNA,
            "D": PROMPT_D_DOSING,
            "E": PROMPT_E_CHANGES,
            "F": PROMPT_F_PSM,
        }
        prompt = prompt_lookup.get(prompt_id)
        if prompt:
            return prompt, prompt_id

    # Fallback: try PROMPT_MAP
    if doc_class in PROMPT_MAP:
        entry = PROMPT_MAP[doc_class]
        if isinstance(entry, dict):
            prompt = entry.get(payer_name)
            if prompt:
                # Derive prompt_id from payer name
                payer_id_map = {"UnitedHealthcare": "A", "UHC": "A", "Aetna": "B", "Cigna": "C"}
                return prompt, payer_id_map.get(payer_name, "generic")
        elif isinstance(entry, str):
            # It's already a prompt ID string — but in our case PROMPT_MAP stores templates
            return entry, doc_class[0].upper()

    # Ultimate fallback: generic prompt
    return EXTRACTION_PROMPT, "generic"


def _format_prompt(prompt_template: str, prompt_id: str, event: dict,
                   document_text: str, icd10_json: str) -> str:
    """Format the prompt template with document metadata.

    Different prompts expect different template variables — handle gracefully.
    """
    fmt_kwargs = {
        "payerName": event.get("payerName", "Unknown"),
        "planType": event.get("planType", "Commercial"),
        "documentTitle": event.get("documentTitle", "Unknown Policy"),
        "effectiveDate": event.get("effectiveDate", "Unknown"),
        "policyNumber": event.get("policyNumber", ""),
        "documentText": document_text,
        "icd10Json": icd10_json,
        # Prompt E specific
        "documentType": event.get("documentClass", ""),
        "period": event.get("effectiveDate", ""),
        # Prompt F specific
        "psmNumber": event.get("policyNumber", ""),
        "companionIpNumber": event.get("companionIpNumber", ""),
    }

    try:
        return prompt_template.format(**fmt_kwargs)
    except KeyError as e:
        logger.warning(json.dumps({"warning": "missing_template_variable", "promptId": prompt_id, "detail": str(e)}))
        # Fallback: manually replace known keys
        result = prompt_template
        for key, value in fmt_kwargs.items():
            result = result.replace("{" + key + "}", str(value))
        return result


# ── Main handler ──────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Extract DrugPolicyCriteria records from structured policy text via Bedrock.

    Enhanced with:
    - ICD-10 pre-extraction pass (two-pass strategy)
    - Payer-specific prompt routing (A/B/C/D/E/F)
    - Indication-level chunking for large documents
    - Skip extraction for index-only document classes
    """
    logger.info(json.dumps({
        "state": "BedrockSchemaExtraction",
        "policyDocId": event.get("policyDocId"),
        "documentClass": event.get("documentClass"),
        "extractionPromptId": event.get("extractionPromptId"),
    }))

    event = _enrich_event_from_dynamo(event)

    policy_doc_id: str = event["policyDocId"]
    s3_bucket: str = event["s3Bucket"]
    structured_key: str = event["structuredTextS3Key"]

    # Check if this document class should skip extraction
    skip_extraction: bool = event.get("skipExtraction", False)
    if skip_extraction:
        logger.info(json.dumps({"action": "extraction_skipped", "documentClass": event.get("documentClass")}))
        return {
            **event,
            "extractedCriteria": [],
            "extractionCount": 0,
            "extractedCriteriaS3Key": "",
            "extractionSkipped": True,
        }

    # Metadata
    payer_name: str = event.get("payerName", "Unknown")
    doc_class: str = event.get("documentClass", "drug_specific")
    prompt_id: str = event.get("extractionPromptId", "")

    # 1. Get structured text from S3
    resp = s3.get_object(Bucket=s3_bucket, Key=structured_key)
    structured_doc = json.loads(resp["Body"].read().decode("utf-8"))

    # Use rawTextWithTables (includes TABLE: markers) if available
    raw_text = structured_doc.get("rawTextWithTables", structured_doc.get("rawText", ""))
    indication_chunks = structured_doc.get("indicationChunks")

    # 2. Select prompt template
    prompt_template, resolved_prompt_id = _get_prompt_template(prompt_id, payer_name, doc_class)
    logger.info(json.dumps({"action": "prompt_selected", "promptId": resolved_prompt_id, "payerName": payer_name, "docClass": doc_class}))

    # 3. ICD-10 pre-extraction pass (for drug-specific prompts A/B/C and generic)
    icd10_json = '{"icd10Mapping": []}'
    if resolved_prompt_id in ("A", "B", "C", "generic"):
        logger.info(json.dumps({"action": "icd10_extraction_start"}))
        icd10_json = _extract_icd10_mapping(raw_text)
        logger.info(json.dumps({"action": "icd10_extraction_complete", "resultPreview": icd10_json[:100]}))

    # 4. Run extraction — either per-indication chunks or full document
    all_criteria: list[dict] = []

    if indication_chunks and resolved_prompt_id in ("A", "B", "C"):
        # Parallel-friendly: one prompt per indication chunk
        for chunk_idx, chunk_data in enumerate(indication_chunks):
            chunk_text = chunk_data.get("preamble", "") + "\n\n" + chunk_data.get("indicationText", "")
            logger.info(json.dumps({"action": "processing_chunk", "chunkIndex": chunk_idx + 1, "totalChunks": len(indication_chunks), "charCount": len(chunk_text)}))

            prompt = _format_prompt(prompt_template, resolved_prompt_id, event, chunk_text, icd10_json)

            try:
                response_text = _invoke_bedrock(prompt)
                cleaned = _clean_json_response(response_text)
                parsed = json.loads(cleaned)

                if isinstance(parsed, list):
                    all_criteria.extend(parsed)
                elif isinstance(parsed, dict):
                    all_criteria.append(parsed)
            except json.JSONDecodeError as e:
                logger.error(json.dumps({"error": "bedrock_parse_failed", "chunkIndex": chunk_idx, "detail": str(e)}))
            except Exception as e:
                logger.error(json.dumps({"error": "bedrock_invocation_failed", "chunkIndex": chunk_idx, "detail": str(e)}))
                raise
    else:
        # Standard: chunk by context window size
        chunks = _chunk_document(raw_text)

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(json.dumps({"action": "processing_chunk", "chunkIndex": chunk_idx + 1, "totalChunks": len(chunks), "charCount": len(chunk)}))

            prompt = _format_prompt(prompt_template, resolved_prompt_id, event, chunk, icd10_json)

            try:
                response_text = _invoke_bedrock(prompt)
                cleaned = _clean_json_response(response_text)
                parsed = json.loads(cleaned)

                if isinstance(parsed, list):
                    all_criteria.extend(parsed)
                elif isinstance(parsed, dict):
                    all_criteria.append(parsed)
            except json.JSONDecodeError as e:
                logger.error(json.dumps({"error": "bedrock_json_parse_failed", "detail": str(e)}))
            except Exception as e:
                logger.error(json.dumps({"error": "bedrock_invocation_failed", "detail": str(e)}))
                raise

    logger.info(json.dumps({"action": "extraction_complete", "criteriaCount": len(all_criteria)}))

    # 5. Enrich each record with denormalized metadata
    for record in all_criteria:
        record["policyDocId"] = policy_doc_id
        record["payerName"] = payer_name
        record["effectiveDate"] = event.get("effectiveDate", "")
        record["extractionPromptVersion"] = resolved_prompt_id

        # Build composite sort key
        drug = record.get("drugName", "unknown")
        icd10 = record.get("indicationICD10", "")
        if isinstance(icd10, list):
            icd10 = icd10[0] if icd10 else ""
        indication = record.get("indicationName", "unknown")
        record["drugIndicationId"] = f"{drug}#{icd10}" if icd10 else f"{drug}#{indication}"

    # 6. Write extracted criteria to S3
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
        "extractionPromptUsed": resolved_prompt_id,
    }
