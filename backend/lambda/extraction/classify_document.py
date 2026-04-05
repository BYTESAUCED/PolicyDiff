# Owner: Mohith
# State 3.0 — ClassifyDocument
#
# Classifies uploaded documents by type BEFORE Textract / extraction.
# Routes each document to the correct prompt (A–H + variants) or marks it as
# index-only (no extraction needed).
#
# New payers added for hackathon documents:
#   EmblemHealth / Prime Therapeutics → Prompt G
#   Florida Blue / MCG               → Prompt H
#   Priority Health Medical Drug List → Prompt B_FORMULARY
#   BCBS NC Preferred Injectable      → Prompt F_PREFERRED
#   UHC multi-product (Botulinum)     → Prompt A_MULTIPRODUCT
#   Cigna 3-phase (Rituximab)         → Prompt C_3PHASE
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, s3Key, payerName, documentTitle,
#             policyNumber, ... }
#   Output: { ..., documentClass, documentFormat, extractionPromptId,
#             skipExtraction, payerStructureNote }

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POLICY_DOCUMENTS_TABLE = os.environ.get("POLICY_DOCUMENTS_TABLE", "PolicyDocuments")
dynamodb = boto3.resource("dynamodb")


# ── Payer structure notes injected into Bedrock prompts ──────────────────────

_PAYER_STRUCTURE_NOTES: dict[str, str] = {
    "A_MULTIPRODUCT": (
        "Multi-product policy covering 5 botulinum toxin products: Botox, Dysport, Xeomin, "
        "Myobloc, and Daxxify (excluded). General Requirements apply to ALL products. "
        "Each product section lists its OWN distinct indications — do not cross-assign. "
        "Daxxify is explicitly EXCLUDED from coverage (coveredStatus: excluded). "
        "Universal frequency cap: no more frequently than every 12 weeks."
    ),
    "C_3PHASE": (
        "Three-phase approval per indication: "
        "A=Initial Therapy, B=One prior course of therapy, C=Two or more prior courses. "
        "Each phase has its own approval duration embedded in text ('Approve for N months if...'). "
        "'Note:' blocks are contextual clarifications — NOT criteria. "
        "Extract each phase as a separate JSON record with approvalPhase label."
    ),
    "G": (
        "Universal Criteria (calcium, vitamin D, no hypocalcemia, no bisphosphonate combo) "
        "apply to ALL indications — include in every record as universalCriteria. "
        "Product-group split: Prolia-type (osteoporosis) vs Xgeva-type (oncology). "
        "Preferred biosimilars: Bildyos/Jubbonti over Prolia; Bilprevda/Wyost over Xgeva. "
        "Footnote symbols (†, ‡, ¤) have been pre-resolved inline as [DEFINED AS: ...]. "
        "Separate Renewal Criteria section exists — extract as reauthorizationCriteria."
    ),
    "H": (
        "Criteria are in Table 1 format: Indication | Criteria columns. "
        "Each table row = one oncology indication. "
        "Section I (Position Statement) = universal initiation criteria for ALL indications. "
        "Section II = continuation/reauthorization criteria. "
        "Mvasi and Zirabev are PREFERRED products; Avastin (reference) is NON-PREFERRED. "
        "Nested logic: BOTH/ALL=AND, ONE/ANY=OR."
    ),
    "B_FORMULARY": (
        "Formulary table document — NOT a clinical criteria policy. "
        "Extract FormularyEntry records from table rows. "
        "Skip rows with empty HCPCS column (category headers). "
        "Notes column codes: PA=prior auth, SOS=site restriction, "
        "CA:[HCPCS]([drug])=covered alternative, ICD-10:[codes]=bypass codes."
    ),
    "F_PREFERRED": (
        "Preferred/non-preferred product program by drug class. "
        "Step therapy is product-tier-based — preferred must be tried before non-preferred. "
        "FDA Approved Use sections are reference information ONLY — not clinical criteria. "
        "Extract documentation requirements for non-preferred exception access."
    ),
    "A": (
        "UHC drug-specific policy with rigid numbered template. "
        "Diagnosis-Specific Criteria section contains per-indication blocks. "
        "Preferred products in Coverage Rationale. ICD-10 codes in Applicable Codes section."
    ),
    "C": (
        "Cigna IP#### policy with nested AND/OR structure. "
        "Branch A=Initial Therapy, Branch B=Continuation. "
        "Preferred products come from companion PSM document."
    ),
}


def _get_payer_structure_note(prompt_id: str) -> str:
    return _PAYER_STRUCTURE_NOTES.get(prompt_id, "")


def classify_document(
    payer_name: str,
    document_title: str,
    s3_key: str,
    policy_number: str = "",
) -> dict:
    """Classify a policy document and determine extraction routing.

    Returns:
        {
            documentClass: str,
            documentFormat: "pdf",
            extractionPromptId: str | None,
            skipExtraction: bool,
            payerStructureNote: str,
        }
    """
    title_lower = document_title.lower() if document_title else ""
    key_lower = s3_key.lower() if s3_key else ""
    payer_lower = payer_name.lower() if payer_name else ""
    policy_lower = policy_number.lower() if policy_number else ""

    document_format = "pdf"

    # ── Formulary / Drug List (index-only for most, B_FORMULARY for Priority Health) ──
    is_priority_health = "priority health" in payer_lower
    is_medical_drug_list = "medical drug list" in title_lower or "drug list" in title_lower

    if is_priority_health and is_medical_drug_list:
        return {
            "documentClass": "formulary",
            "documentFormat": document_format,
            "extractionPromptId": "B_FORMULARY",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("B_FORMULARY"),
        }

    if "formulary" in title_lower or "drug guide" in title_lower:
        return {
            "documentClass": "formulary",
            "documentFormat": document_format,
            "extractionPromptId": None,
            "skipExtraction": True,
            "payerStructureNote": "",
        }

    # ── Self-administered / site of care / PA framework (index-only) ─────────
    if "self-administered" in title_lower or "self administered" in title_lower:
        return {
            "documentClass": "self_admin",
            "documentFormat": document_format,
            "extractionPromptId": None,
            "skipExtraction": True,
            "payerStructureNote": "",
        }

    if "site of care" in title_lower:
        return {
            "documentClass": "site_of_care",
            "documentFormat": document_format,
            "extractionPromptId": "SITE_OF_CARE",
            "skipExtraction": False,
            "payerStructureNote": (
                "Site-of-care policy. Extract selfAdminAllowed per drug. "
                "Values: infusion_center_only | home_infusion_allowed | office_only."
            ),
        }

    if "formulary exception" in title_lower:
        return {
            "documentClass": "pa_framework",
            "documentFormat": document_format,
            "extractionPromptId": None,
            "skipExtraction": True,
            "payerStructureNote": "",
        }

    # ── Preferred Injectable / Preferred Product Programs ─────────────────────
    is_bcbs_nc = (
        ("blue cross blue shield of north carolina" in payer_lower)
        or ("bcbs nc" in payer_lower)
        or ("bcbs of nc" in payer_lower)
    )
    if is_bcbs_nc and (
        "preferred injectable" in title_lower
        or "preferred oncology" in title_lower
        or "preferred product" in title_lower
    ):
        return {
            "documentClass": "preferred_injectable",
            "documentFormat": document_format,
            "extractionPromptId": "F_PREFERRED",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("F_PREFERRED"),
        }

    # ── Cigna PSM / Preferred Specialty Management ────────────────────────────
    if "preferred specialty management" in title_lower or "psm" in key_lower:
        return {
            "documentClass": "preferred_specialty_mgmt",
            "documentFormat": document_format,
            "extractionPromptId": "F",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("F"),
        }

    # ── Maximum Dosage ────────────────────────────────────────────────────────
    if "maximum dosage" in title_lower or "max dosage" in title_lower:
        return {
            "documentClass": "max_dosage",
            "documentFormat": document_format,
            "extractionPromptId": "D",
            "skipExtraction": False,
            "payerStructureNote": "",
        }

    # ── Change Bulletins / Update Bulletins ───────────────────────────────────
    if "policy update" in title_lower or "policy changes" in title_lower:
        return {
            "documentClass": "update_bulletin",
            "documentFormat": document_format,
            "extractionPromptId": "E",
            "skipExtraction": False,
            "payerStructureNote": "",
        }

    # ── Drug-specific policies — route by payer ───────────────────────────────
    doc_class = "drug_specific"

    # EmblemHealth / Prime Therapeutics
    if "emblemhealth" in payer_lower or "prime therapeutics" in payer_lower:
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "G",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("G"),
        }

    # Florida Blue / MCG
    is_florida_blue = (
        "florida blue" in payer_lower
        or "bcbs of florida" in payer_lower
        or "mcg" in payer_lower
        or ("florida" in payer_lower and "blue" in payer_lower)
    )
    if is_florida_blue:
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "H",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("H"),
        }

    # UHC — detect multi-product variant (Botulinum Toxins, etc.)
    is_uhc = any(k in payer_lower for k in ("unitedhealthcare", "uhc", "united health"))
    if is_uhc:
        is_multiproduct = (
            "botulinum" in title_lower
            or "toxin" in title_lower
            or "botox" in title_lower
        )
        if is_multiproduct:
            return {
                "documentClass": doc_class,
                "documentFormat": document_format,
                "extractionPromptId": "A_MULTIPRODUCT",
                "skipExtraction": False,
                "payerStructureNote": _get_payer_structure_note("A_MULTIPRODUCT"),
            }
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "A",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("A"),
        }

    # Cigna — detect 3-phase variant (long-form IP#### with rituximab, etc.)
    is_cigna = "cigna" in payer_lower
    if is_cigna:
        # 3-phase policies: rituximab, and others with IP#### that have multi-phase structure
        # Key signals: "IP0319" pattern or specific drug keywords
        is_3phase = (
            "rituximab" in title_lower
            or "ip03" in policy_lower  # rituximab policy series
            or "ip04" in policy_lower  # other long-form policies
        )
        if is_3phase:
            return {
                "documentClass": doc_class,
                "documentFormat": document_format,
                "extractionPromptId": "C_3PHASE",
                "skipExtraction": False,
                "payerStructureNote": _get_payer_structure_note("C_3PHASE"),
            }
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "C",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("C"),
        }

    # Aetna
    if "aetna" in payer_lower:
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "B",
            "skipExtraction": False,
            "payerStructureNote": "",
        }

    # BCBS NC — general drug/corporate medical policy → use H (table-based criteria)
    if is_bcbs_nc:
        return {
            "documentClass": doc_class,
            "documentFormat": document_format,
            "extractionPromptId": "H",
            "skipExtraction": False,
            "payerStructureNote": _get_payer_structure_note("H"),
        }

    # Unknown payer → use generic prompt A as best-effort fallback
    return {
        "documentClass": doc_class,
        "documentFormat": document_format,
        "extractionPromptId": "A",
        "skipExtraction": False,
        "payerStructureNote": "",
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Classify document type and determine extraction routing."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event is a string and could not be parsed as JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise TypeError(f"Expected event to be a dict, got {type(event).__name__}")
    logger.info(json.dumps({"state": "ClassifyDocument", "policyDocId": event.get("policyDocId")}))

    payer_name = event.get("payerName", "")
    document_title = event.get("documentTitle", "")
    s3_key = event.get("s3Key", "")
    policy_number = event.get("policyNumber", "")

    # If metadata missing from event (direct S3 upload without POST /api/policies),
    # try to enrich from DynamoDB PolicyDocuments record
    if not payer_name or not document_title:
        policy_doc_id = event.get("policyDocId", "")
        if policy_doc_id:
            try:
                table = dynamodb.Table(POLICY_DOCUMENTS_TABLE)
                result = table.get_item(Key={"policyDocId": policy_doc_id})
                item = result.get("Item", {})
                payer_name = payer_name or item.get("payerName", "")
                document_title = document_title or item.get("documentTitle", "")
                policy_number = policy_number or item.get("policyNumber", "")
                logger.info(json.dumps({
                    "action": "enriched_from_dynamo",
                    "payerName": payer_name,
                    "documentTitle": document_title,
                }))
                # ADR: merge enriched fields back into event | assemble_text + bedrock_extract need payerName
                event = {
                    **event,
                    "payerName": payer_name,
                    "documentTitle": document_title,
                    "policyNumber": policy_number,
                }
            except Exception as e:
                logger.warning(f"Could not enrich metadata from DynamoDB: {e}")

    classification = classify_document(payer_name, document_title, s3_key, policy_number)

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
                ":bs": False,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to update policy document classification: {e}")

    return {
        **event,
        **classification,
    }
