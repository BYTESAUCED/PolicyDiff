# Owner: Mohith
# State 5 — ConfidenceScoring
#
# Post-processes extracted criteria, applies confidence thresholds.
# Any field with confidence < 0.7 gets flagged with needsReview: true.
# Incorporates Gemini verification issues to further reduce confidence.
#
# Step Functions I/O:
#   Input:  { ..., extractedCriteria: [...], verificationResult: {...} }
#   Output: { ..., extractedCriteria: [...] (updated), reviewCount }

import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CONFIDENCE_THRESHOLD = 0.7
GEMINI_PENALTY = 0.15  # Confidence reduction per Gemini-flagged issue


def _score_record(record: dict, gemini_issues: list[dict]) -> dict:
    """Apply confidence rules and needsReview flagging to a single record.

    Rules:
    - Self-reported confidence < 0.7 → needsReview = True
    - Missing critical fields (drugName, indicationName) → confidence -= 0.2
    - Gemini found issue on this record → confidence -= 0.15 per issue
    - Complex conditional logic detected → confidence -= 0.1
    """
    confidence = float(record.get("confidence", 0.8))
    review_reasons: list[str] = []

    # Rule 1: Missing critical fields
    if not record.get("drugName"):
        confidence -= 0.2
        review_reasons.append("Missing drugName")
    if not record.get("indicationName"):
        confidence -= 0.2
        review_reasons.append("Missing indicationName")

    # Rule 2: Empty criteria lists for expected fields
    if not record.get("initialAuthCriteria") and not record.get("reauthorizationCriteria"):
        confidence -= 0.1
        review_reasons.append("No authorization criteria extracted")

    # Rule 3: Check for complex conditional markers in rawExcerpt
    excerpt = record.get("rawExcerpt", "")
    complex_markers = ["one of the following", "all of the following", "either", "unless"]
    if any(marker in excerpt.lower() for marker in complex_markers):
        confidence -= 0.05
        review_reasons.append("Complex conditional logic detected")

    # Rule 4: Cross-reference Gemini verification issues
    drug = record.get("drugName", "").lower()
    indication = record.get("indicationName", "").lower()
    for issue in gemini_issues:
        issue_field = issue.get("field", "").lower()
        # Check if this issue plausibly relates to the current record
        if drug in issue_field or indication in issue_field or issue_field in str(record).lower():
            confidence -= GEMINI_PENALTY
            review_reasons.append(
                f"Gemini flagged: {issue.get('field')} "
                f"(extracted={issue.get('extractedValue')}, "
                f"correct={issue.get('correctValue')})"
            )

    # Clamp confidence to [0, 1]
    confidence = max(0.0, min(1.0, confidence))
    record["confidence"] = round(confidence, 3)

    # Flag for review
    if confidence < CONFIDENCE_THRESHOLD:
        record["needsReview"] = True
        record["reviewReasons"] = review_reasons
    else:
        record["needsReview"] = False

    return record


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Apply confidence scoring and review flagging to extracted criteria."""
    logger.info(json.dumps({"state": "ConfidenceScoring", "policyDocId": event.get("policyDocId")}))

    criteria: list[dict] = event.get("extractedCriteria", [])
    verification: dict = event.get("verificationResult", {})
    gemini_issues: list[dict] = verification.get("issues", [])

    review_count = 0
    scored_criteria: list[dict] = []

    for record in criteria:
        scored = _score_record(record, gemini_issues)
        if scored.get("needsReview"):
            review_count += 1
        scored_criteria.append(scored)

    logger.info(
        f"Confidence scoring complete: {len(scored_criteria)} records, "
        f"{review_count} flagged for review"
    )

    # Build confidence summary
    confidences = [r["confidence"] for r in scored_criteria]
    confidence_summary = {
        "totalRecords": len(scored_criteria),
        "reviewCount": review_count,
        "avgConfidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "minConfidence": round(min(confidences), 3) if confidences else 0,
        "maxConfidence": round(max(confidences), 3) if confidences else 0,
        "geminiIssuesCount": len(gemini_issues),
        "geminiVerificationStatus": verification.get("status", "unknown"),
    }

    return {
        **event,
        "extractedCriteria": scored_criteria,
        "reviewCount": review_count,
        "confidenceSummary": confidence_summary,
    }
