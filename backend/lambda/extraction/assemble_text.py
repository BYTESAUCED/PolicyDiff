# Owner: Mohith
# State 3 — AssembleStructuredText
#
# Reconstructs raw Textract block JSON from S3 into a hierarchical
# document structure: headers → sub-headers → bullet points → nested
# conditions, preserving table-cell relationships.
#
# Payer-specific pre-processing added for hackathon documents:
#   EmblemHealth  — footnote symbol resolution (†, ‡, ¤ → [DEFINED AS: ...])
#   UHC Botulinum — multi-product splitting + General Requirements prepend
#   Cigna 3-Phase — numbered indication splitting for 3-phase docs
#   Florida Blue  — Table 1 row extraction (indication | criteria)
#   Priority Health — 50-row formulary table batching with category tracking
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, textractOutputKey, payerName,
#             documentClass, extractionPromptId, ... }
#   Output: { ..., structuredTextS3Key, pageCount, sectionCount,
#             tableCount, boilerplateStripped, hasIndicationChunks,
#             chunkCount, chunkMetadata }

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


# ── Boilerplate stripping ─────────────────────────────────────────────────────

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
    "Aetna": {},
    "EmblemHealth": {
        "strip_before_pattern": r"^This policy applies to",
    },
    "Prime Therapeutics": {
        "strip_before_pattern": r"^This policy applies to",
    },
    "Florida Blue": {
        "strip_sections": ["Description", "Related Guidelines", "References"],
    },
    "MCG": {
        "strip_sections": ["Description", "Related Guidelines", "References"],
    },
    "BCBS NC": {
        "strip_sections": ["Policy Summary", "Revision History"],
    },
}

_PAYER_ALIASES: dict[str, str] = {
    "unitedhealthcare": "UnitedHealthcare",
    "uhc": "UHC",
    "aetna": "Aetna",
    "cigna": "Cigna",
    "emblemhealth": "EmblemHealth",
    "prime therapeutics": "Prime Therapeutics",
    "florida blue": "Florida Blue",
    "mcg": "MCG",
    "bcbs nc": "BCBS NC",
    "blue cross blue shield of north carolina": "BCBS NC",
}


def _canonical_payer(payer_name: str) -> str:
    lower = payer_name.lower()
    for alias, canonical in _PAYER_ALIASES.items():
        if alias in lower:
            return canonical
    return payer_name


def _strip_boilerplate(text: str, payer_name: str, doc_class: str) -> tuple[str, bool]:
    """Remove known boilerplate sections. Returns (stripped_text, was_stripped)."""
    canonical = _canonical_payer(payer_name)
    pattern = BOILERPLATE_PATTERNS.get(canonical, {})
    if not pattern:
        return text, False

    original_len = len(text)
    stripped = False

    # Preserve specific sections before stripping
    preserved_text = ""
    for section_name in pattern.get("preserve_sections", []):
        idx = text.find(section_name)
        if idx >= 0:
            end_idx = len(text)
            for next_marker in ["References", "INSTRUCTIONS FOR USE", "Instructions for Use"]:
                if next_marker == section_name:
                    continue
                next_idx = text.find(next_marker, idx + len(section_name))
                if next_idx > idx:
                    end_idx = min(end_idx, next_idx)
            preserved_text += "\n\n" + text[idx:end_idx]

    # Strip named sections entirely
    for section in pattern.get("strip_sections", []):
        idx = text.find(section)
        if idx > 0:
            end_idx = len(text)
            next_section = re.search(r"\n[A-Z][A-Z\s]{3,}\n", text[idx + len(section):])
            if next_section:
                end_idx = idx + len(section) + next_section.start()
            text = text[:idx] + text[end_idx:]
            stripped = True

    # Strip preamble matching a regex pattern
    strip_before_pattern = pattern.get("strip_before_pattern")
    if strip_before_pattern:
        m = re.search(strip_before_pattern, text, re.MULTILINE)
        if m and m.start() > 0:
            end = text.find("\n\n", m.end())
            if end > m.start():
                text = text[end:]
                stripped = True

    # Strip named start-of-boilerplate marker
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

    if preserved_text:
        text += preserved_text

    if stripped:
        chars_saved = original_len - len(text)
        logger.info(f"Stripped {chars_saved} chars of boilerplate for {payer_name}")

    return text, stripped


# ── Footnote resolution (EmblemHealth / Prime Therapeutics) ──────────────────

def _resolve_footnotes(text: str) -> str:
    """Resolve footnote symbols inline.

    Scans for footnote definition lines (symbol at line start + definition),
    builds a lookup, then replaces inline occurrences mid-sentence with
    '[DEFINED AS: {definition}]'.
    """
    footnote_lookup: dict[str, str] = {}

    # Lines that start with a known footnote symbol followed by a definition
    symbol_pattern = re.compile(
        r"^([†‡¤§¶]|\*{1,2}|#{1,2})\s*(.{10,300})$",
        re.MULTILINE,
    )
    for match in symbol_pattern.finditer(text):
        symbol = match.group(1).strip()
        definition = match.group(2).strip()
        if symbol not in footnote_lookup and len(definition) > 10:
            footnote_lookup[symbol] = definition
            logger.info(f"Footnote '{symbol}': {definition[:80]}...")

    if not footnote_lookup:
        return text

    resolved = text
    for symbol, definition in footnote_lookup.items():
        escaped = re.escape(symbol)
        # Replace occurrences that follow a word character (mid-sentence, not line-start)
        inline_pat = re.compile(r"(?<=\w)" + escaped)
        resolved = inline_pat.sub(f" [DEFINED AS: {definition}]", resolved)

    return resolved


# ── UHC multi-product splitting (Botulinum Toxins, etc.) ─────────────────────

_UHC_PRODUCT_HEADER_RE = re.compile(
    r"([A-Z][a-zA-Z]+(?:®|™)?(?:\s+\([^)]+\))?)\s+is\s+proven\s+(?:for|in)\s+the\s+treatment\s+of",
    re.IGNORECASE,
)
_UHC_GENERAL_REQUIREMENTS_RE = re.compile(r"General\s+Requirements?", re.IGNORECASE)
_UHC_UNPROVEN_RE = re.compile(r"Unproven\s+(?:Use|Indications?)", re.IGNORECASE)


def _split_uhc_multiproduct(text: str) -> list[dict] | None:
    """Split UHC multi-product policy into per-product chunks.

    Prepends the 'General Requirements' section to each product chunk.
    Appends an 'Unproven Use' chunk when present.
    Returns None if fewer than 2 product sections are found.
    """
    gen_req_match = _UHC_GENERAL_REQUIREMENTS_RE.search(text)
    general_requirements_text = ""
    search_start = 0

    if gen_req_match:
        gen_req_start = gen_req_match.start()
        gen_req_end = len(text)
        # Find first product header after General Requirements
        first_prod = _UHC_PRODUCT_HEADER_RE.search(text, gen_req_start + 50)
        if first_prod:
            gen_req_end = first_prod.start()
        unproven_early = _UHC_UNPROVEN_RE.search(text, gen_req_start + 50)
        if unproven_early and unproven_early.start() < gen_req_end:
            gen_req_end = unproven_early.start()
        general_requirements_text = text[gen_req_start:gen_req_end].strip()
        search_start = gen_req_start

    # Find all product section matches
    product_matches = list(_UHC_PRODUCT_HEADER_RE.finditer(text, search_start))
    if len(product_matches) < 2:
        return None

    # Deduplicate closely spaced matches (within 20 chars)
    deduped: list[re.Match] = []
    for m in product_matches:
        if not deduped or m.start() > deduped[-1].start() + 20:
            deduped.append(m)

    if len(deduped) < 2:
        return None

    preamble = general_requirements_text or text[:2000]
    chunks: list[dict] = []

    for i, match in enumerate(deduped):
        start = match.start()
        end = deduped[i + 1].start() if i + 1 < len(deduped) else len(text)
        # Stop before Unproven section
        unproven_m = _UHC_UNPROVEN_RE.search(text, start, end)
        if unproven_m:
            end = unproven_m.start()

        product_text = text[start:end].strip()
        if len(product_text) < 50:
            continue

        # Extract product name from match group 1
        raw_product = match.group(1) if match.lastindex and match.lastindex >= 1 else "Unknown"
        product_name = re.sub(r"[®™].*$", "", raw_product).strip()

        chunks.append({
            "indicationText": product_text,
            "preamble": preamble,
            "chunkType": "per_product",
            "productName": product_name,
        })

    # Unproven section as its own chunk
    unproven_global = _UHC_UNPROVEN_RE.search(text)
    if unproven_global:
        chunks.append({
            "indicationText": text[unproven_global.start():].strip(),
            "preamble": preamble,
            "chunkType": "unproven_list",
            "productName": None,
        })

    if not chunks:
        return None

    logger.info(f"UHC multi-product: {len(chunks)} chunks")
    return chunks


# ── Cigna 3-phase indication splitting ───────────────────────────────────────

_CIGNA_INDICATION_RE = re.compile(r"^\d+\.\s+[A-Z][^\n.]{5,80}$", re.MULTILINE)
_CIGNA_NOT_COVERED_RE = re.compile(r"Conditions?\s+Not\s+Covered", re.IGNORECASE)


def _split_cigna_3phase(text: str) -> list[dict] | None:
    """Split Cigna 3-phase document at numbered indication headers.

    Returns None if fewer than 2 indication sections are found.
    """
    if len(text) < 8000:
        return None

    preamble = _extract_preamble(text, "Cigna")
    matches = list(_CIGNA_INDICATION_RE.finditer(text))
    if len(matches) < 2:
        return None

    chunks: list[dict] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        not_covered_m = _CIGNA_NOT_COVERED_RE.search(text, start, end)
        if not_covered_m:
            end = not_covered_m.start()

        indication_text = text[start:end].strip()
        if len(indication_text) < 50:
            continue

        chunks.append({
            "indicationText": indication_text,
            "preamble": preamble,
            "chunkType": "per_indication",
            "indicationName": match.group(0).strip(),
        })

    # Add "Conditions Not Covered" as its own chunk
    not_covered_global = _CIGNA_NOT_COVERED_RE.search(text)
    if not_covered_global:
        chunks.append({
            "indicationText": text[not_covered_global.start():].strip(),
            "preamble": "",
            "chunkType": "unproven_list",
            "indicationName": "Conditions Not Covered",
        })

    if len(chunks) < 2:
        return None

    logger.info(f"Cigna 3-phase: {len(chunks)} indication chunks")
    return chunks


# ── Florida Blue table criteria parsing ──────────────────────────────────────

def _parse_florida_blue_table_chunks(
    tables: list[dict],
    raw_text: str,
) -> list[dict] | None:
    """Extract per-indication chunks from Florida Blue Table 1 (Indication | Criteria)."""
    # Extract Section I (universal) and Section II (continuation) from prose
    section_i_text = ""
    section_ii_text = ""

    sec_i_m = re.search(
        r"Section\s+I\b[^\n]*\n(.*?)(?=Section\s+II\b|\Z)",
        raw_text, re.DOTALL | re.IGNORECASE,
    )
    if sec_i_m:
        section_i_text = sec_i_m.group(1).strip()

    sec_ii_m = re.search(
        r"Section\s+II\b[^\n]*(.*?)(?=Section\s+III\b|\Z)",
        raw_text, re.DOTALL | re.IGNORECASE,
    )
    if sec_ii_m:
        section_ii_text = sec_ii_m.group(1).strip()

    # Find Table 1 with Indication | Criteria columns
    table1 = None
    for table in tables:
        rows = table.get("rows", [])
        if not rows:
            continue
        header_str = " ".join(str(c) for c in rows[0]).lower()
        if "indication" in header_str and ("criteria" in header_str or "requirement" in header_str):
            table1 = table
            break

    # Fallback: largest 2-column table
    if table1 is None:
        for table in tables:
            rows = table.get("rows", [])
            if len(rows) > 3 and rows and len(rows[0]) == 2:
                table1 = table
                break

    if table1 is None:
        return None

    rows = table1.get("rows", [])
    if len(rows) < 2:
        return None

    preamble = section_i_text or ""
    chunks: list[dict] = []

    for row in rows[1:]:  # skip header row
        if len(row) < 2:
            continue
        indication_name = str(row[0]).strip()
        criteria_text = str(row[1]).strip()
        if not indication_name or len(criteria_text) < 10:
            continue

        full_text = f"Indication: {indication_name}\n\nCriteria:\n{criteria_text}"
        if section_ii_text:
            full_text += f"\n\nContinuation Criteria (Section II):\n{section_ii_text}"

        chunks.append({
            "indicationText": full_text,
            "preamble": preamble,
            "chunkType": "per_indication",
            "indicationName": indication_name,
        })

    if not chunks:
        return None

    logger.info(f"Florida Blue: {len(chunks)} indication rows from Table 1")
    return chunks


# ── Priority Health formulary batching ───────────────────────────────────────

_FORMULARY_BATCH_SIZE = 50
_HCPCS_RE = re.compile(r"^[A-Z]\d{4}$|^\d{5}$")


def _batch_priority_health_formulary(tables: list[dict]) -> list[dict] | None:
    """Extract Priority Health formulary rows in 50-row batches with category tracking."""
    # Find the formulary table (has HCPCS/CPT column)
    formulary_table = None
    for table in tables:
        rows = table.get("rows", [])
        if not rows:
            continue
        header_str = " ".join(str(c) for c in rows[0]).lower()
        if "hcpcs" in header_str or "cpt" in header_str:
            formulary_table = table
            break

    if formulary_table is None:
        return None

    all_rows = formulary_table.get("rows", [])
    if len(all_rows) < 3:
        return None

    current_category = "Unknown"
    drug_rows: list[dict] = []

    for row in all_rows[1:]:  # skip header
        if not row:
            continue
        hcpcs_col = str(row[0]).strip() if row else ""

        # Rows with empty or non-HCPCS first column are category headers
        if not hcpcs_col or not _HCPCS_RE.match(hcpcs_col):
            for cell in row:
                cell_str = str(cell).strip()
                if cell_str and len(cell_str) > 3:
                    current_category = cell_str
                    break
            continue

        row_text = " | ".join(str(cell).strip() for cell in row)
        drug_rows.append({"row_text": row_text, "therapeutic_category": current_category})

    if not drug_rows:
        return None

    chunks: list[dict] = []
    for batch_start in range(0, len(drug_rows), _FORMULARY_BATCH_SIZE):
        batch = drug_rows[batch_start: batch_start + _FORMULARY_BATCH_SIZE]
        batch_text = "\n".join(r["row_text"] for r in batch)
        batch_category = batch[0]["therapeutic_category"] if batch else current_category

        chunks.append({
            "indicationText": batch_text,
            "preamble": "",
            "chunkType": "formulary_batch",
            "startRow": batch_start,
            "endRow": batch_start + len(batch) - 1,
            "therapeuticCategory": batch_category,
        })

    logger.info(f"Priority Health: {len(drug_rows)} drug rows → {len(chunks)} batches")
    return chunks


# ── Table structure preservation ─────────────────────────────────────────────

def _serialize_tables_for_bedrock(tables: list[dict]) -> str:
    """Serialize extracted tables with TABLE:/END TABLE markers for Bedrock."""
    if not tables:
        return ""

    parts: list[str] = ["\n\n"]
    for i, table in enumerate(tables, 1):
        rows = table.get("rows", [])
        if not rows:
            continue

        header = rows[0] if rows else []
        table_title = f"Table {i}"
        header_text = " ".join(str(c) for c in header).lower()

        if "indication" in header_text and "dose" in header_text:
            table_title = "Dosing by Indication"
        elif "icd" in header_text or "code" in header_text:
            table_title = "ICD-10 / HCPCS Codes"
        elif "date" in header_text and "change" in header_text:
            table_title = "Revision History"
        elif "product" in header_text or "preferred" in header_text:
            table_title = "Preferred Products"
        elif "indication" in header_text and ("criteria" in header_text or "requirement" in header_text):
            table_title = "Indication Criteria Table"

        parts.append(f"TABLE: {table_title}")
        for row in rows:
            parts.append(" | ".join(str(cell) for cell in row))
        parts.append("END TABLE")
        parts.append("")

    return "\n".join(parts)


# ── General indication splitting (UHC standard, Aetna) ───────────────────────

def _split_by_indication(text: str, payer_name: str) -> list[dict] | None:
    """Split document into per-indication chunks for standard payers."""
    if len(text) < 15000:
        return None

    canonical = _canonical_payer(payer_name)

    if canonical in ("UnitedHealthcare", "UHC"):
        pattern = r"(?=\b\w+\s+is proven for the treatment of\s+)"
    elif canonical == "Aetna":
        pattern = r"(?=^\d+\.\s+[A-Z])"
    else:
        return None

    chunks = re.split(pattern, text, flags=re.MULTILINE)
    chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 100]

    if len(chunks) <= 1:
        return None

    preamble = _extract_preamble(text, canonical)
    logger.info(f"Split document into {len(chunks)} indication chunks")
    return [
        {"indicationText": chunk, "preamble": preamble, "chunkType": "per_indication"}
        for chunk in chunks
    ]


def _extract_preamble(text: str, payer_name: str) -> str:
    """Extract preamble sections (preferred products, ICD-10) to include with each chunk."""
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
    return text[:2000]


# ── Textract block processing helpers ─────────────────────────────────────────

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


# ── Main handler ──────────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Assemble Textract output into hierarchical structured text.

    Routes to payer-specific pre-processing based on extractionPromptId:
      A_MULTIPRODUCT → multi-product splitting + General Requirements prepend
      C_3PHASE       → numbered indication splitting
      G              → footnote symbol resolution (EmblemHealth)
      H              → Florida Blue Table 1 row extraction
      B_FORMULARY    → 50-row formulary table batching (Priority Health)
    """
    logger.info(json.dumps({"state": "AssembleStructuredText", "event_keys": list(event.keys())}))

    s3_bucket: str = event["s3Bucket"]
    payer_name: str = event.get("payerName", "")
    doc_class: str = event.get("documentClass", "drug_specific")
    prompt_id: str = event.get("extractionPromptId", "") or ""

    # Parse policyDocId from s3Key if not provided
    policy_doc_id: str = event.get("policyDocId") or ""
    if not policy_doc_id:
        s3_key = event.get("s3Key", "")
        parts = s3_key.strip("/").split("/")
        if len(parts) >= 2:
            policy_doc_id = parts[1]
    if not policy_doc_id:
        raise ValueError("policyDocId missing and could not be parsed from s3Key")

    # Derive Textract output key
    textract_output_key: str = event.get("textractOutputKey", "")
    if not textract_output_key:
        job_id = (event.get("textractResult") or {}).get("JobId", "")
        if job_id:
            textract_output_key = f"textract-output/{policy_doc_id}/{job_id}/1"
            logger.info(json.dumps({"action": "derived_textract_key", "key": textract_output_key}))
        else:
            raise ValueError("textractOutputKey not set and textractResult.JobId not found")

    # Load Textract output
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

    # ── Payer-specific pre-processing ─────────────────────────────────────────
    indication_chunks: list[dict] | None = None
    boilerplate_stripped = False

    if prompt_id == "G":
        # EmblemHealth: resolve footnote symbols, then standard strip
        logger.info("EmblemHealth: running footnote resolution")
        raw_text = _resolve_footnotes(raw_text)
        raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)

    elif prompt_id == "A_MULTIPRODUCT":
        raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)
        logger.info("UHC multi-product: splitting by product section")
        indication_chunks = _split_uhc_multiproduct(raw_text)

    elif prompt_id == "C_3PHASE":
        raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)
        logger.info("Cigna 3-phase: splitting by numbered indication")
        indication_chunks = _split_cigna_3phase(raw_text)

    elif prompt_id == "H":
        raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)
        logger.info("Florida Blue: extracting Table 1 indication rows")
        indication_chunks = _parse_florida_blue_table_chunks(tables, raw_text)

    elif prompt_id == "B_FORMULARY":
        # No boilerplate strip for formulary tables
        logger.info("Priority Health: batching formulary table rows")
        indication_chunks = _batch_priority_health_formulary(tables)

    else:
        # Standard: boilerplate strip + general indication splitting
        raw_text, boilerplate_stripped = _strip_boilerplate(raw_text, payer_name, doc_class)
        indication_chunks = _split_by_indication(raw_text, payer_name)

    # ── Section detection and table serialization ─────────────────────────────
    sections = _detect_sections(raw_text)
    table_text = _serialize_tables_for_bedrock(tables)

    # ── Build chunk metadata for downstream routing ───────────────────────────
    chunk_metadata: list[dict] = []
    if indication_chunks:
        for idx, chunk in enumerate(indication_chunks):
            chunk_metadata.append({
                "chunkIndex": idx,
                "chunkType": chunk.get("chunkType", "per_indication"),
                "productName": chunk.get("productName"),
                "indicationName": chunk.get("indicationName"),
                "startRow": chunk.get("startRow"),
                "endRow": chunk.get("endRow"),
                "therapeuticCategory": chunk.get("therapeuticCategory"),
                "tokenEstimate": len(chunk.get("indicationText", "")) // 4,
            })

    # ── Build structured document ─────────────────────────────────────────────
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
        "chunkMetadata": chunk_metadata,
    }

    structured_key = f"{policy_doc_id}/structured-text.json"
    s3.put_object(
        Bucket=s3_bucket,
        Key=structured_key,
        Body=json.dumps(structured_doc, default=str),
        ContentType="application/json",
    )
    logger.info(f"Wrote structured text to s3://{s3_bucket}/{structured_key}")

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
        "chunkCount": len(indication_chunks) if indication_chunks else 0,
        "chunkMetadata": chunk_metadata,
    }
