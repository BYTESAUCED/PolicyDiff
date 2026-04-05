# Owner: Mohith
# State 5 — ConfidenceScoring
#
# Post-processes extracted criteria, applies confidence thresholds.
# Any field with confidence < 0.7 gets flagged with needsReview: true.
#
# Enhanced per policy-pdf-analysis.md Section 7.7:
#   - Payer-specific confidence calibration targets
#   - Cross-document dependency penalty (e.g., UHC "per FDA labeled dosing")
#   - Nested logic complexity penalty (Cigna 3-level nesting)
#   - Missing initialAuthDurationMonths penalty
#
# Step Functions I/O:
#   Input:  { ..., extractedCriteria: [...], payerName, documentClass, ... }
#   Output: { ..., extractedCriteria: [...] (updated), reviewCount }

import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CONFIDENCE_THRESHOLD = 0.7

# ── Payer-specific confidence calibration (Section 7.7) ──────────────────

PAYER_CONFIDENCE_RULES: dict[str, dict] = {
    "UnitedHealthcare": {
        # UHC has rigid template → high base confidence
        "base_adjustment": 0.0,
        "fda_dosing_penalty": -0.15,  # "per FDA labeled dosing" = incomplete data
        "cross_reference_penalty": -0.15,
    },
    "UHC": {
        "base_adjustment": 0.0,
        "fda_dosing_penalty": -0.15,
        "cross_reference_penalty": -0.15,
    },
    "Aetna": {
        # Aetna CPBs have explicit dosing tables → good data completeness
        "base_adjustment": 0.0,
        "global_continuation_penalty": -0.10,  # continuation criteria is global, not per-indication
    },
    "Cigna": {
        # Cigna 3-level nesting → inherently harder to extract
        "base_adjustment": -0.05,
        "missing_psm_penalty": -0.20,  # preferredProducts empty without PSM companion
        "nested_logic_penalty": -0.08,  # additional penalty for deep nesting
    },
}


def _score_record(record: dict, payer_name: str, doc_class: str) -> dict:
    """Apply confidence rules and needsReview flagging to a single record.

    Enhanced with payer-specific calibration from Section 7.7 of the analysis.
    """
    confidence = float(record.get("confidence", 0.8))
    review_reasons: list[str] = []
    payer_rules = PAYER_CONFIDENCE_RULES.get(payer_name, {})

    # Apply payer base adjustment
    confidence += payer_rules.get("base_adjustment", 0.0)

    # ── Universal rules ──────────────────────────────────────────────────

    # Missing critical fields
    if not record.get("drugName"):
        confidence -= 0.2
        review_reasons.append("Missing drugName")
    if not record.get("indicationName"):
        confidence -= 0.2
        review_reasons.append("Missing indicationName")

    # Missing authorization criteria entirely
    if not record.get("initialAuthCriteria") and not record.get("reauthorizationCriteria"):
        if record.get("coveredStatus", "covered") == "covered":
            confidence -= 0.1
            review_reasons.append("No authorization criteria extracted for covered indication")

    # Missing initialAuthDurationMonths (new field from analysis)
    if not record.get("initialAuthDurationMonths") and record.get("initialAuthCriteria"):
        confidence -= 0.05
        review_reasons.append("Missing initialAuthDurationMonths")

    # ── Payer-specific rules ─────────────────────────────────────────────

    # UHC: "per FDA labeled dosing" penalty
    dosing = record.get("dosingLimits") or {}
    if payer_name in ("UnitedHealthcare", "UHC"):
        if dosing.get("perFDALabel") is True or dosing is None:
            raw_excerpt = record.get("rawExcerpt", "")
            criteria_text = json.dumps(record.get("initialAuthCriteria", []))
            if "fda labeled dosing" in (raw_excerpt + criteria_text).lower():
                confidence += payer_rules.get("fda_dosing_penalty", 0)
                review_reasons.append("Dosing defers to FDA label — incomplete without Max Dosage Policy")

        # UHC: cross-document reference detection
        for field_text in [record.get("rawExcerpt", ""), json.dumps(record.get("initialAuthCriteria", []))]:
            if "see " in field_text.lower() and "policy" in field_text.lower():
                confidence += payer_rules.get("cross_reference_penalty", 0)
                review_reasons.append("Cross-reference to another policy detected — data may be incomplete")
                break

    # Cigna: missing PSM penalty (preferredProducts empty)
    if payer_name == "Cigna":
        if not record.get("preferredProducts"):
            confidence += payer_rules.get("missing_psm_penalty", 0)
            review_reasons.append("Cigna preferredProducts empty — companion PSM document not merged")

        # Cigna: nested logic complexity
        criteria_list = record.get("initialAuthCriteria", [])
        has_nested_or = any(
            c.get("logicOperator") == "OR" for c in criteria_list
            if isinstance(c, dict)
        )
        if has_nested_or:
            confidence += payer_rules.get("nested_logic_penalty", 0)
            review_reasons.append("Complex nested AND/OR logic detected")

    # Aetna: global continuation criteria penalty
    if payer_name == "Aetna":
        reauth = record.get("reauthorizationCriteria", [])
        if not reauth:
            confidence += payer_rules.get("global_continuation_penalty", 0)
            review_reasons.append("Continuation criteria may be global (Aetna applies single section to all indications)")

    # ── Complex conditional logic detection (universal) ──────────────────

    excerpt = record.get("rawExcerpt", "")
    complex_markers = ["one of the following", "all of the following", "either", "unless"]
    complex_count = sum(1 for marker in complex_markers if marker in excerpt.lower())
    if complex_count >= 2:
        confidence -= 0.05 * complex_count
        review_reasons.append(f"Multiple conditional logic markers detected ({complex_count})")

    # ── Clamp and flag ───────────────────────────────────────────────────

    confidence = max(0.0, min(1.0, confidence))
    record["confidence"] = round(confidence, 3)

    if confidence < CONFIDENCE_THRESHOLD:
        record["needsReview"] = True
        record["reviewReasons"] = review_reasons
    else:
        record["needsReview"] = False
        # Still include review reasons if any exist (informational)
        if review_reasons:
            record["reviewReasons"] = review_reasons

    return record


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Apply confidence scoring and review flagging to extracted criteria."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event is a string and could not be parsed as JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise TypeError(f"Expected event to be a dict, got {type(event).__name__}")
    logger.info(json.dumps({"state": "ConfidenceScoring", "policyDocId": event.get("policyDocId")}))

    criteria: list[dict] = event.get("extractedCriteria", [])
    payer_name: str = event.get("payerName", "")
    doc_class: str = event.get("documentClass", "drug_specific")

    # Skip scoring if extraction was skipped
    if event.get("extractionSkipped"):
        return {
            **event,
            "extractedCriteria": [],
            "reviewCount": 0,
            "confidenceSummary": {"totalRecords": 0, "reviewCount": 0},
        }

    review_count = 0
    scored_criteria: list[dict] = []

    for record in criteria:
        scored = _score_record(record, payer_name, doc_class)
        if scored.get("needsReview"):
            review_count += 1
        scored_criteria.append(scored)

    logger.info(json.dumps({
        "action": "confidence_scoring_complete",
        "totalRecords": len(scored_criteria),
        "reviewCount": review_count,
        "payerName": payer_name,
    }))

    # Build confidence summary
    confidences = [r["confidence"] for r in scored_criteria]
    confidence_summary = {
        "totalRecords": len(scored_criteria),
        "reviewCount": review_count,
        "avgConfidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "minConfidence": round(min(confidences), 3) if confidences else 0,
        "maxConfidence": round(max(confidences), 3) if confidences else 0,
        "payerName": payer_name,
        "extractionPromptUsed": event.get("extractionPromptUsed", "unknown"),
    }

    return {
        **event,
        "extractedCriteria": scored_criteria,
        "reviewCount": review_count,
        "confidenceSummary": confidence_summary,
    }
