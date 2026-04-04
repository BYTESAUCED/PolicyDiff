# Owner: Mohith
# State 3 — AssembleStructuredText
#
# Reconstructs raw Textract block JSON from S3 into a hierarchical
# document structure: headers → sub-headers → bullet points → nested
# conditions, preserving table-cell relationships.
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, textractOutputKey, payerName, ... }
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

                # Resolve cell text through WORD children
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

        # Get key text
        key_text = _get_text_from_relations(block, block_map)

        # Find VALUE block
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
    """Heuristic section splitter for medical policy documents.

    Identifies common header patterns:
      - Numbered sections  (1. / 1.1 / I. / A.)
      - ALL CAPS lines
      - Lines ending with a colon
    Returns a list of { title, level, content } dicts.
    """
    lines = text.split("\n")
    sections: list[dict] = []
    current: dict = {"title": "Preamble", "level": 0, "content": []}

    header_patterns = [
        (re.compile(r"^\d+\.\d+\s+"), 2),          # 1.1 Sub-section
        (re.compile(r"^\d+\.\s+"), 1),              # 1. Section
        (re.compile(r"^[IVX]+\.\s+"), 1),           # I. Roman numeral
        (re.compile(r"^[A-Z]\.\s+"), 2),            # A. Letter sub-header
        (re.compile(r"^[A-Z][A-Z\s]{4,}$"), 1),     # ALL CAPS HEADER
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current["content"].append("")
            continue

        matched = False
        for pattern, level in header_patterns:
            if pattern.match(stripped):
                # Save previous section
                if current["content"] or current["title"] != "Preamble":
                    sections.append(current)
                current = {"title": stripped, "level": level, "content": []}
                matched = True
                break

        if not matched:
            current["content"].append(stripped)

    # Flush last section
    if current["content"]:
        sections.append(current)

    return sections


# ── Main handler ──────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Assemble Textract output into hierarchical structured text.

    Reads Textract JSON blocks from S3, parses text/tables/forms,
    splits into sections, and writes structured JSON back to S3.
    """
    logger.info(json.dumps({"state": "AssembleStructuredText", "event_keys": list(event.keys())}))

    policy_doc_id: str = event["policyDocId"]
    s3_bucket: str = event["s3Bucket"]
    textract_output_key: str = event["textractOutputKey"]

    # 1. Read Textract JSON blocks from S3
    try:
        resp = s3.get_object(Bucket=s3_bucket, Key=textract_output_key)
        textract_results = json.loads(resp["Body"].read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"Failed to read Textract output from s3://{s3_bucket}/{textract_output_key}: {exc}")
        raise

    # Textract may return results as a list (multi-page) or single dict
    if isinstance(textract_results, list):
        all_blocks: list[dict] = []
        for page_result in textract_results:
            all_blocks.extend(page_result.get("Blocks", []))
    else:
        all_blocks = textract_results.get("Blocks", [])

    page_count = len({b.get("Page", 1) for b in all_blocks})
    logger.info(f"Textract returned {len(all_blocks)} blocks across {page_count} pages")

    # 2. Extract text, tables, key-value pairs
    raw_text = _extract_text_from_blocks(all_blocks)
    tables = _extract_tables_from_blocks(all_blocks)
    kv_pairs = _extract_kv_pairs_from_blocks(all_blocks)

    # 3. Heuristic section detection
    sections = _detect_sections(raw_text)

    # 4. Build structured document
    structured_doc = {
        "policyDocId": policy_doc_id,
        "pageCount": page_count,
        "totalBlocks": len(all_blocks),
        "rawText": raw_text,
        "sections": sections,
        "tables": tables,
        "keyValuePairs": kv_pairs,
    }

    # 5. Write to S3
    structured_key = f"{policy_doc_id}/structured-text.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=structured_key,
        Body=json.dumps(structured_doc, default=str),
        ContentType="application/json",
    )
    logger.info(f"Wrote structured text to s3://{s3_bucket}/{structured_key}")

    # 6. Pass through to next state
    return {
        **event,
        "structuredTextS3Key": structured_key,
        "pageCount": page_count,
        "sectionCount": len(sections),
        "tableCount": len(tables),
    }
