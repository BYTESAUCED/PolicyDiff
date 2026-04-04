# Owner: Mohith
# State 4 — BedrockSchemaExtraction
#
# Sends structured policy text to Bedrock Claude Sonnet to extract
# DrugPolicyCriteria records per the spec schema.
#
# Enhanced for hackathon documents:
#   - New prompt IDs: A_MULTIPRODUCT, B_FORMULARY, C_3PHASE, F_PREFERRED, G, H
#   - payerStructureNote injection into all new prompts
#   - therapeuticCategory injection for B_FORMULARY batches
#   - Extended drugIndicationId: {drug}#{productName}#{icd10_or_indication}
#   - approvalPhase-aware drugIndicationId for Cigna 3-phase docs
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, structuredTextS3Key,
#             payerName, planType, documentTitle, effectiveDate,
#             documentClass, extractionPromptId, skipExtraction,
#             payerStructureNote, ... }
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

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250514")
MAX_DOCUMENT_CHARS = 180_000


def _invoke_bedrock(prompt: str, max_tokens: int = 8192) -> str:
    """Call Bedrock Claude and return raw text response."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
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


# ── ICD-10 Pre-Extraction Pass ────────────────────────────────────────────────

def _extract_icd10_mapping(document_text: str) -> str:
    """Run ICD-10 pre-extraction pass. Returns JSON string."""
    from extraction.prompts import ICD10_EXTRACTION_PROMPT

    text_for_icd = document_text
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
        parsed = json.loads(cleaned)
        return json.dumps(parsed, default=str)
    except Exception as e:
        logger.warning(f"ICD-10 pre-extraction failed (non-fatal): {e}")
        return json.dumps({"icd10Mapping": []})


# ── Prompt selection ──────────────────────────────────────────────────────────

def _get_prompt_template(prompt_id: str, payer_name: str, doc_class: str):
    """Get the correct prompt template based on classification."""
    from extraction.prompts import PROMPT_ID_MAP, PROMPT_MAP, EXTRACTION_PROMPT

    if prompt_id and prompt_id in PROMPT_ID_MAP:
        return PROMPT_ID_MAP[prompt_id], prompt_id

    # Fallback: PROMPT_MAP lookup
    if doc_class in PROMPT_MAP:
        entry = PROMPT_MAP[doc_class]
        if isinstance(entry, dict):
            prompt = entry.get(payer_name)
            if prompt:
                payer_id_map = {
                    "UnitedHealthcare": "A", "UHC": "A",
                    "Aetna": "B",
                    "Cigna": "C",
                    "EmblemHealth": "G", "Prime Therapeutics": "G",
                    "Florida Blue": "H", "MCG": "H",
                }
                return prompt, payer_id_map.get(payer_name, "generic")
        else:
            return entry, doc_class[0].upper()

    return EXTRACTION_PROMPT, "generic"


def _format_prompt(
    prompt_template: str,
    prompt_id: str,
    event: dict,
    document_text: str,
    icd10_json: str,
    chunk_data: dict | None = None,
) -> str:
    """Format the prompt template with document metadata and chunk context."""
    therapeutic_category = ""
    if chunk_data:
        therapeutic_category = chunk_data.get("therapeuticCategory", "")

    fmt_kwargs = {
        "payerName": event.get("payerName", "Unknown"),
        "planType": event.get("planType", "Commercial"),
        "documentTitle": event.get("documentTitle", "Unknown Policy"),
        "effectiveDate": event.get("effectiveDate", "Unknown"),
        "policyNumber": event.get("policyNumber", ""),
        "documentText": document_text,
        "icd10Json": icd10_json,
        "payerStructureNote": event.get("payerStructureNote", ""),
        "therapeuticCategory": therapeutic_category,
        # Prompt E
        "documentType": event.get("documentClass", ""),
        "period": event.get("effectiveDate", ""),
        # Prompt F
        "psmNumber": event.get("policyNumber", ""),
        "companionIpNumber": event.get("companionIpNumber", ""),
    }

    try:
        return prompt_template.format(**fmt_kwargs)
    except KeyError as e:
        logger.warning(f"Missing template variable {e} for prompt {prompt_id}, using partial format")
        result = prompt_template
        for key, value in fmt_kwargs.items():
            result = result.replace("{" + key + "}", str(value))
        return result


# ── drugIndicationId construction ────────────────────────────────────────────

def _build_drug_indication_id(record: dict) -> str:
    """Build composite sort key.

    Standard:      {drugName}#{icd10 or indicationName}
    Multi-product: {drugName}#{productName}#{icd10 or indicationName}
    3-phase:       {drugName}#{indicationName}#{approvalPhase}
    Combined:      {drugName}#{productName}#{icd10 or indication}#{approvalPhase}
    """
    def slug(s: str) -> str:
        return re.sub(r"\s+", "_", s.strip().lower())

    drug = slug(record.get("drugName") or "unknown")
    product_name = record.get("productName", "")
    approval_phase = record.get("approvalPhase", "")

    icd10 = record.get("indicationICD10", "")
    if isinstance(icd10, list):
        icd10 = icd10[0] if icd10 else ""
    indication = slug(record.get("indicationName") or "unknown")
    code_part = icd10 if icd10 else indication

    parts = [drug]
    if product_name:
        parts.append(slug(product_name))
    parts.append(code_part)
    if approval_phase:
        parts.append(approval_phase)

    return "#".join(parts)


# Prompt IDs that benefit from ICD-10 pre-extraction
_ICD10_PROMPT_IDS = {"A", "A_MULTIPRODUCT", "B", "C", "C_3PHASE", "G", "H", "generic"}

# Prompt IDs that should use indication-level chunks
_CHUNKED_PROMPT_IDS = {"A", "A_MULTIPRODUCT", "B", "C", "C_3PHASE", "G", "H", "B_FORMULARY"}


# ── Main handler ──────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Extract DrugPolicyCriteria records from structured policy text via Bedrock."""
    logger.info(json.dumps({
        "state": "BedrockSchemaExtraction",
        "policyDocId": event.get("policyDocId"),
        "documentClass": event.get("documentClass"),
        "extractionPromptId": event.get("extractionPromptId"),
    }))

    policy_doc_id: str = event["policyDocId"]
    s3_bucket: str = event["s3Bucket"]
    structured_key: str = event["structuredTextS3Key"]
    doc_class: str = event.get("documentClass", "drug_specific")

    # Enrich metadata from DynamoDB if missing (direct S3 upload path)
    payer_name: str = event.get("payerName", "")
    if not payer_name:
        try:
            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments"))
            result = table.get_item(Key={"policyDocId": policy_doc_id})
            item = result.get("Item", {})
            event = {
                **event,
                "payerName": item.get("payerName", "Unknown"),
                "planType": item.get("planType", "Commercial"),
                "documentTitle": item.get("documentTitle", "Unknown Policy"),
                "effectiveDate": item.get("effectiveDate", ""),
            }
            payer_name = event["payerName"]
            logger.info(json.dumps({"action": "enriched_from_dynamo", "payerName": payer_name}))
        except Exception as e:
            logger.warning(f"Could not enrich metadata from DynamoDB: {e}")
            payer_name = "Unknown"

    # Skip extraction for index-only document classes
    from extraction.prompts import NO_EXTRACTION_CLASSES
    skip_extraction: bool = event.get("skipExtraction", False)
    if skip_extraction or doc_class in NO_EXTRACTION_CLASSES:
        logger.info(f"Skipping extraction for document class: {doc_class}")
        return {
            **event,
            "extractedCriteria": [],
            "extractionCount": 0,
            "extractedCriteriaS3Key": "",
            "extractionSkipped": True,
        }

    prompt_id: str = event.get("extractionPromptId", "") or ""

    # 1. Load structured text from S3
    resp = s3.get_object(Bucket=s3_bucket, Key=structured_key)
    structured_doc = json.loads(resp["Body"].read().decode("utf-8"))

    raw_text = structured_doc.get("rawTextWithTables", structured_doc.get("rawText", ""))
    indication_chunks = structured_doc.get("indicationChunks")

    # 2. Select prompt template
    prompt_template, resolved_prompt_id = _get_prompt_template(prompt_id, payer_name, doc_class)
    logger.info(f"Using prompt {resolved_prompt_id} for {payer_name} / {doc_class}")

    # 3. ICD-10 pre-extraction pass (for drug-specific prompts)
    icd10_json = '{"icd10Mapping": []}'
    if resolved_prompt_id in _ICD10_PROMPT_IDS:
        logger.info("Running ICD-10 pre-extraction pass...")
        icd10_json = _extract_icd10_mapping(raw_text)
        logger.info(f"ICD-10 pre-extraction result: {icd10_json[:200]}")

    # 4. Run extraction
    all_criteria: list[dict] = []

    if indication_chunks and resolved_prompt_id in _CHUNKED_PROMPT_IDS:
        for chunk_idx, chunk_data in enumerate(indication_chunks):
            chunk_text = chunk_data.get("preamble", "") + "\n\n" + chunk_data.get("indicationText", "")
            logger.info(
                f"Processing chunk {chunk_idx + 1}/{len(indication_chunks)} "
                f"({len(chunk_text)} chars, type={chunk_data.get('chunkType', '?')})"
            )

            prompt = _format_prompt(
                prompt_template, resolved_prompt_id, event, chunk_text, icd10_json, chunk_data
            )

            try:
                response_text = _invoke_bedrock(prompt)
                cleaned = _clean_json_response(response_text)
                parsed = json.loads(cleaned)
                records = parsed if isinstance(parsed, list) else [parsed]

                # Annotate records with chunk-level context
                for rec in records:
                    # Carry over productName from multi-product chunks
                    if chunk_data.get("productName") and not rec.get("productName"):
                        rec["productName"] = chunk_data["productName"]
                    # Mark unproven/excluded lists
                    if chunk_data.get("chunkType") == "unproven_list":
                        rec.setdefault("coveredStatus", "unproven")
                    # Mark formulary entries
                    if chunk_data.get("chunkType") == "formulary_batch":
                        rec["documentClass"] = "formulary"

                all_criteria.extend(records)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Bedrock response for chunk {chunk_idx}: {e}")
            except Exception as e:
                logger.error(f"Bedrock invocation failed for chunk {chunk_idx}: {e}")
                raise
    else:
        chunks = _chunk_document(raw_text)
        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} chars)")

            prompt = _format_prompt(prompt_template, resolved_prompt_id, event, chunk, icd10_json)

            try:
                response_text = _invoke_bedrock(prompt)
                cleaned = _clean_json_response(response_text)
                parsed = json.loads(cleaned)
                records = parsed if isinstance(parsed, list) else [parsed]
                all_criteria.extend(records)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Bedrock response as JSON: {e}")
                logger.error(f"Raw response: {response_text[:500]}")
            except Exception as e:
                logger.error(f"Bedrock invocation failed: {e}")
                raise

    logger.info(f"Extracted {len(all_criteria)} records")

    # 5. Enrich each record with denormalized metadata
    for record in all_criteria:
        record["policyDocId"] = policy_doc_id
        record["payerName"] = payer_name
        record["effectiveDate"] = event.get("effectiveDate", "")
        record["extractionPromptVersion"] = resolved_prompt_id
        record["drugIndicationId"] = _build_drug_indication_id(record)

    # 6. Write to S3
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
