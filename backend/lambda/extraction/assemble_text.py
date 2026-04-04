# Owner: Mohith
# State 3 — AssembleStructuredText
#
# Reconstructs raw Textract block JSON from S3 into a hierarchical
# document structure: headers → sub-headers → bullet points → nested
# conditions, preserving table-cell relationships.
#
# Enhanced per policy-pdf-analysis.md:
#   - Payer-specific boilerplate stripping (Section 7.3)
#   - Table structure preservation with TABLE:/END TABLE markers (Section 7.5)
#   - Indication-level document splitting for large docs (Section 7.8)
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, textractOutputKey, payerName,
#             documentClass, documentFormat, ... }
#   Output: { ..., structuredTextS3Key, pageCount }

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


# ── Boilerplate stripping (Section 7.3) ──────────────────────────────────

BOILERPLATE_PATTERNS: dict[str, dict] = {
    "Cigna": {
        "strip_before": "OVERVIEW",
        "strip_after": "References",
        "preserve_sections": ["Revision Details", "Coding Information"],
    },
    "UnitedHealthcare": {
        "strip_after": "Instructions for Use",
    },
    "UHC": {
        "strip_after": "Instructions for Use",
    },
    "Aetna": {
        # No boilerplate in CPBs
    },
}


def _strip_boilerplate(text: str, payer_name: str, doc_class: str) -> tuple[str, bool]:
    """Remove known boilerplate sections before sending to Bedrock.

    Returns (stripped_text, was_stripped).
    """
    pattern = BOILERPLATE_PATTERNS.get(payer_name, {})
    if not pattern:
        return text, False

    original_len = len(text)
    stripped = False

    # Save sections we need to preserve before stripping
    preserved_text = ""
    for section_name in pattern.get("preserve_sections", []):
        idx = text.find(section_name)
        if idx >= 0:
            # Grab from section name to next major section or end
            end_idx = len(text)
            # Look for a common next-section marker
            for next_marker in ["References", "INSTRUCTIONS FOR USE", "Instructions for Use"]:
                if next_marker == section_name:
                    continue
                next_idx = text.find(next_marker, idx + len(section_name))
                if next_idx > idx:
                    end_idx = min(end_idx, next_idx)
            preserved_text += "\n\n" + text[idx:end_idx]

    # Strip everything before first meaningful section
    strip_before = pattern.get("strip_before")
    if strip_before:
        idx = text.find(strip_before)
        if idx > 0:
            text = text[idx:]
            stripped = True

    # Strip everything after end-of-content marker
    strip_after = pattern.get("strip_after")
    if strip_after and doc_class != "update_bulletin":
        idx = text.find(strip_after)
        if idx > 0:
            text = text[:idx]
            stripped = True

    # Re-append preserved sections
    if preserved_text:
        text += preserved_text

    if stripped:
        chars_saved = original_len - len(text)
        logger.info(f"Stripped {chars_saved} chars of boilerplate for {payer_name}")

    return text, stripped




# ── Table structure preservation (Section 7.5) ──────────────────────────

def _serialize_tables_for_bedrock(tables: list[dict]) -> str:
    """Serialize extracted tables with TABLE:/END TABLE markers for Bedrock.

    Per Section 7.5: markers help Bedrock correctly identify tabular data
    versus prose text.
    """
    if not tables:
        return ""

    parts: list[str] = ["\n\n"]
    for i, table in enumerate(tables, 1):
        rows = table.get("rows", [])
        if not rows:
            continue

        # Try to infer table title from first row if it looks like a header
        header = rows[0] if rows else []
        table_title = f"Table {i}"

        # Check if header row contains recognizable names
        header_text = " ".join(str(c) for c in header).lower()
        if "indication" in header_text and "dose" in header_text:
            table_title = "Dosing by Indication"
        elif "icd" in header_text or "code" in header_text:
            table_title = "ICD-10 / HCPCS Codes"
        elif "date" in header_text and "change" in header_text:
            table_title = "Revision History"
        elif "product" in header_text or "preferred" in header_text:
            table_title = "Preferred Products"

        parts.append(f"TABLE: {table_title}")
        for row in rows:
            parts.append(" | ".join(str(cell) for cell in row))
        parts.append("END TABLE")
        parts.append("")

    return "\n".join(parts)


# ── Indication-level splitting (Section 7.8) ────────────────────────────

def _split_by_indication(text: str, payer_name: str) -> list[dict] | None:
    """Split document into per-indication chunks for parallel extraction.

    Returns None if the document is small enough to process in a single call,
    or if payer-specific splitting patterns don't match.
    """
    # Only split if the document is large enough to benefit
    if len(text) < 15000:
        return None

    if payer_name in ("UnitedHealthcare", "UHC"):
        pattern = r"(?=\b\w+\s+is proven for the treatment of\s+)"
    elif payer_name == "Cigna":
        pattern = r"(?=^\d+\.\s+[A-Z][^.]+\.\s+Approve for)"
    elif payer_name == "Aetna":
        pattern = r"(?=^\d+\.\s+[A-Z])"
    else:
        return None

    chunks = re.split(pattern, text, flags=re.MULTILINE)
    chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 100]

    if len(chunks) <= 1:
        return None

    # Extract preamble (preferred products, ICD-10 mapping, overview) to include with each chunk
    preamble = _extract_preamble(text, payer_name)

    logger.info(f"Split document into {len(chunks)} indication chunks")
    return [{"indicationText": chunk, "preamble": preamble} for chunk in chunks]


def _extract_preamble(text: str, payer_name: str) -> str:
    """Extract the preamble sections that should be included with every chunk."""
    preamble_end_markers = {
        "UnitedHealthcare": "is proven for the treatment of",
        "UHC": "is proven for the treatment of",
        "Cigna": "Coverage Policy",
        "Aetna": "Criteria for Initial Approval",
    }
    marker = preamble_end_markers.get(payer_name, "")
    if marker:
        idx = text.find(marker)
        if idx > 0:
            return text[:idx]
    return text[:2000]  # Fallback: first 2000 chars


# ── Textract block processing helpers ─────────────────────────────────────

def _extract_text_from_blocks(blocks: list[dict]) -> str:
    """Pull plain text from LINE blocks in reading order."""
    lines: list[str] = []
    for block in blocks:
        if block.get("BlockType") == "LINE":
            lines.append(block.get("Text", ""))
    return "\n".join(lines)


def _extract_tables_from_blocks(blocks: list[dict]) -> list[dict]:
    """Rebuild TABLE → CELL hierarchy from Textract block relationships."""
    block_map: dict[str, dict] = {b["Id"]: b for b in blocks}
    tables: list[dict] = []

    for block in blocks:
        if block.get("BlockType") != "TABLE":
            continue

        table: dict[str, Any] = {"rows": {}}
        for rel in block.get("Relationships", []):
            if rel["Type"] != "CHILD":
                continue
            for child_id in rel["Ids"]:
                cell = block_map.get(child_id)
                if not cell or cell.get("BlockType") != "CELL":
                    continue
                row_idx = cell.get("RowIndex", 0)
                col_idx = cell.get("ColumnIndex", 0)

                cell_text_parts: list[str] = []
                for crel in cell.get("Relationships", []):
                    if crel["Type"] != "CHILD":
                        continue
                    for wid in crel["Ids"]:
                        word = block_map.get(wid)
                        if word and word.get("BlockType") == "WORD":
                            cell_text_parts.append(word.get("Text", ""))
                cell_text = " ".join(cell_text_parts)

                table["rows"].setdefault(row_idx, {})[col_idx] = cell_text

        # Convert to ordered list-of-lists
        if table["rows"]:
            max_row = max(table["rows"].keys())
            max_col = max(
                c for row_cells in table["rows"].values() for c in row_cells.keys()
            )
            ordered: list[list[str]] = []
            for r in range(1, max_row + 1):
                row_data: list[str] = []
                for c in range(1, max_col + 1):
                    row_data.append(table["rows"].get(r, {}).get(c, ""))
                ordered.append(row_data)
            table["rows"] = ordered
            tables.append(table)

    return tables


def _extract_kv_pairs_from_blocks(blocks: list[dict]) -> list[dict]:
    """Extract KEY_VALUE_SET pairs from FORMS feature output."""
    block_map: dict[str, dict] = {b["Id"]: b for b in blocks}
    kv_pairs: list[dict] = []

    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET" or block.get("EntityTypes") != ["KEY"]:
            continue

        key_text = _get_text_from_relations(block, block_map)

        value_text = ""
        for rel in block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                for vid in rel["Ids"]:
                    vblock = block_map.get(vid)
                    if vblock:
                        value_text = _get_text_from_relations(vblock, block_map)

        if key_text:
            kv_pairs.append({"key": key_text, "value": value_text})

    return kv_pairs


def _get_text_from_relations(block: dict, block_map: dict) -> str:
    parts: list[str] = []
    for rel in block.get("Relationships", []):
        if rel["Type"] != "CHILD":
            continue
        for cid in rel["Ids"]:
            child = block_map.get(cid)
            if child and child.get("BlockType") == "WORD":
                parts.append(child.get("Text", ""))
    return " ".join(parts)


def _detect_sections(text: str) -> list[dict]:
    """Heuristic section splitter for medical policy documents."""
    lines = text.split("\n")
    sections: list[dict] = []
    current: dict = {"title": "Preamble", "level": 0, "content": []}

    header_patterns = [
        (re.compile(r"^\d+\.\d+\s+"), 2),
        (re.compile(r"^\d+\.\s+"), 1),
        (re.compile(r"^[IVX]+\.\s+"), 1),
        (re.compile(r"^[A-Z]\.\s+"), 2),
        (re.compile(r"^[A-Z][A-Z\s]{4,}$"), 1),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current["content"].append("")
            continue

        matched = False
        for pattern, level in header_patterns:
            if pattern.match(stripped):
                if current["content"] or current["title"] != "Preamble":
                    sections.append(current)
                current = {"title": stripped, "level": level, "content": []}
                matched = True
                break

        if not matched:
            current["content"].append(stripped)

    if current["content"]:
        sections.append(current)

    return sections


# ── Main handler ──────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Assemble Textract output into hierarchical structured text.

    Enhanced with:
    - Payer-specific boilerplate stripping
    - Table structure preservation with TABLE:/END TABLE markers
    - Indication-level document splitting for large documents
    """
    logger.info(json.dumps({"state": "AssembleStructuredText", "event_keys": list(event.keys())}))

    s3_bucket: str = event["s3Bucket"]
    payer_name: str = event.get("payerName", "")
    doc_class: str = event.get("documentClass", "drug_specific")

    # Parse policyDocId from s3Key if not explicitly provided
    # EventBridge passes s3Key = "raw/{policyDocId}/raw.pdf"; we extract index 1
    policy_doc_id: str = event.get("policyDocId") or ""
    if not policy_doc_id:
        s3_key = event.get("s3Key", "")
        parts = s3_key.strip("/").split("/")
        if len(parts) >= 2:
            policy_doc_id = parts[1]  # raw/{policyDocId}/raw.pdf → index 1
    if not policy_doc_id:
        raise ValueError("policyDocId missing and could not be parsed from s3Key")

    # ── PDF path: Textract ────────────────────────────────────────────────
    # ADR: textractOutputKey derived from OutputConfig path | StartDocumentAnalysis writes blocks to
    # s3Bucket/textract-output/{policyDocId}/{jobId}/ — key passed through SFN state or derived here
    textract_output_key: str = event.get("textractOutputKey", "")
    if not textract_output_key:
        # Derive from textractResult.JobId set by StartTextractJob state
        job_id = (event.get("textractResult") or {}).get("JobId", "")
        if job_id:
            textract_output_key = f"textract-output/{policy_doc_id}/{job_id}/1"
            logger.info(json.dumps({"action": "derived_textract_key", "key": textract_output_key}))
        else:
            logger.error(json.dumps({"error": "missing_textract_output_key", "policyDocId": policy_doc_id}))
            raise ValueError("textractOutputKey not set and textractResult.JobId not found in event")

    try:
        resp = s3.get_object(Bucket=s3_bucket, Key=textract_output_key)
        textract_results = json.loads(resp["Body"].read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"Failed to read Textract output: {exc}")
        raise

    if isinstance(textract_results, list):
        all_blocks: list[dict] = []
        for page_result in textract_results:
            all_blocks.extend(page_result.get("Blocks", []))
    else:
        all_blocks = textract_results.get("Blocks", [])

    page_count = len({b.get("Page", 1) for b in all_blocks})
    logger.info(f"Textract returned {len(all_blocks)} blocks across {page_count} pages")

    raw_text = _extract_text_from_blocks(all_blocks)
    tables = _extract_tables_from_blocks(all_blocks)
    kv_pairs = _extract_kv_pairs_from_blocks(all_blocks)

    # ── Boilerplate stripping ─────────────────────────────────────────────
    raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)

    # ── Section detection ─────────────────────────────────────────────────
    sections = _detect_sections(raw_text)

    # ── Serialize tables with Bedrock-friendly markers ────────────────────
    table_text = _serialize_tables_for_bedrock(tables)

    # ── Indication-level splitting ────────────────────────────────────────
    indication_chunks = _split_by_indication(raw_text, payer_name)

    # ── Build structured document ─────────────────────────────────────────
    structured_doc = {
        "policyDocId": policy_doc_id,
        "pageCount": page_count,
        "rawText": raw_text,
        "rawTextWithTables": raw_text + table_text,
        "sections": sections,
        "tables": tables,
        "keyValuePairs": kv_pairs,
        "boilerplateStripped": boilerplate_stripped,
        "indicationChunks": indication_chunks,
    }

    # ── Write to S3 ──────────────────────────────────────────────────────
    structured_key = f"{policy_doc_id}/structured-text.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=structured_key,
        Body=json.dumps(structured_doc, default=str),
        ContentType="application/json",
    )
    logger.info(f"Wrote structured text to s3://{s3_bucket}/{structured_key}")

    # ── Update PolicyDocuments with boilerplate flag ──────────────────────
    if boilerplate_stripped:
        try:
            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments"))
            table.update_item(
                Key={"policyDocId": policy_doc_id},
                UpdateExpression="SET boilerplateStripped = :b",
                ExpressionAttributeValues={":b": True},
            )
        except Exception as e:
            logger.warning(f"Failed to update boilerplate flag: {e}")

    return {
        **event,
        "policyDocId": policy_doc_id,
        "structuredTextS3Key": structured_key,
        "pageCount": page_count,
        "sectionCount": len(sections),
        "tableCount": len(tables),
        "boilerplateStripped": boilerplate_stripped,
        "hasIndicationChunks": indication_chunks is not None,
    }
