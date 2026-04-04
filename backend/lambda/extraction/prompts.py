# Owner: Mohith
# All Bedrock + Gemini prompts for PolicyDiff.
#
# Centralised here so every Lambda imports the same prompt text.
# Prompts are f-string templates — call .format(**kwargs) at invocation time.

# ─────────────────────────────────────────────────────────────────────────────
# 10.1  Policy Document Extraction Prompt
# Model: anthropic.claude-sonnet-4-5  (Bedrock)
# Called from: Step Functions State 4 — BedrockSchemaExtraction
# ─────────────────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """\
You are extracting structured medical benefit drug policy criteria from a payer \
policy document. Your output will be used directly in a clinical decision support \
system — accuracy is critical.

Document metadata:
- Payer: {payerName}
- Plan type: {planType}
- Document title: {documentTitle}
- Effective date: {effectiveDate}

The document covers one or more drugs across one or more indications. For EACH \
drug-indication pair, extract:

1. drugName: normalized generic name (e.g., "infliximab", never "Remicade")
2. brandNames: all brand names mentioned in this section
3. indicationName: exact medical condition (e.g., "rheumatoid arthritis", \
"Crohn's disease")
4. indicationICD10: ICD-10 code if stated
5. preferredProducts: ordered list [{{productName, rank}}], 1 = most preferred
6. initialAuthCriteria: array of individual requirements, each with:
   - criterionText: human-readable statement
   - criterionType: "diagnosis"|"step_therapy"|"lab_value"|\
"prescriber_requirement"|"dosing"|"combination_restriction"|"age"|"severity"
   - requiredDrugsTriedFirst: [drug names] — only for step_therapy
   - trialDurationWeeks: number — only if explicitly stated
   - prescriberType: "rheumatologist"|"dermatologist"|"gastroenterologist"|\
"any" — only for prescriber_requirement
7. reauthorizationCriteria: same structure as initialAuthCriteria, plus:
   - maxAuthDurationMonths: number
   - requiresDocumentation: string describing required clinical evidence
8. dosingLimits: {{maxDoseMg, maxFrequency, weightBased: bool, maxDoseMgPerKg}}
9. combinationRestrictions: [{{restrictedWith, restrictionType: \
"same_class"|"same_indication"}}]
10. quantityLimits: {{maxUnitsPerPeriod, periodDays}}
11. benefitType: "medical"|"pharmacy" based on document context
12. selfAdminAllowed: boolean
13. rawExcerpt: the exact text passage you extracted this from (for citation)
14. confidence: 0.0-1.0 — your confidence in the accuracy of this extraction

CRITICAL RULES:
- Parse conditional logic precisely. "All of the following" = AND (all must be \
met). "One of the following" = OR (any one sufficient). Track this in \
criterionText.
- Each indication section is INDEPENDENT. Never merge criteria across \
indications.
- If a criterion references another policy document, note this in criterionText \
but do not follow the reference.
- Normalized drug names only: "infliximab" not "REMICADE®"
- If a field is not specified in the document, omit it entirely. Do not invent \
values.
- Rate confidence below 0.7 if: the section is ambiguous, uses complex \
conditional logic, or references external policies.

Return a valid JSON array of DrugPolicyCriteriaRecord objects. Return ONLY the \
JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# 10.4  Temporal Diff Prompt
# Model: anthropic.claude-sonnet-4-5  (Bedrock)
# Called from: DiffLambda
# ─────────────────────────────────────────────────────────────────────────────
TEMPORAL_DIFF_PROMPT = """\
You are comparing two versions of the same payer's medical benefit drug policy \
to identify what changed and how significant those changes are for patients and \
pharmacy consultants.

Payer: {payerName}
Drug: {drugName}
Old policy effective: {oldDate}
New policy effective: {newDate}

OLD policy criteria:
{oldPolicyJson}

NEW policy criteria:
{newPolicyJson}

For each indication covered, identify ALL changes. For each change:
- field: which field changed ("step_therapy"|"preferred_products"|"dosing"|\
"auth_duration"|"prescriber_requirement"|"combination_restrictions"|\
"indication_added"|"indication_removed")
- oldValue: previous value (string representation)
- newValue: new value
- severity:
  - "breaking" — coverage removed, new step therapy barrier added, dosing \
limit reduced, indication removed
  - "restrictive" — additional documentation required, auth period shortened, \
new combination restriction
  - "relaxed" — step therapy removed, dosing expanded, indication added, \
fewer prior failures required
  - "neutral" — rewording only, administrative change, no functional clinical \
impact
- humanSummary: one sentence in plain English, written for a pharmacy \
consultant. Be specific about what changed and what it means.

If there are NO functional changes between versions, return an empty changes \
array.

Return JSON only:
{{
  "changes": [
    {{
      "indication": string,
      "field": string,
      "oldValue": string,
      "newValue": string,
      "severity": string,
      "humanSummary": string
    }}
  ]
}}"""
