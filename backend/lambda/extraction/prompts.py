# Owner: Mohith
# All Bedrock + Gemini prompts for PolicyDiff.
#
# Per policy-pdf-analysis.md, the single generic extraction prompt (10.1)
# is replaced with payer-specific prompts A–F, plus ICD-10 pre-extraction.
#
# Prompt index:
#   A  — UHC Drug-Specific Policy
#   B  — Aetna CPB (PDF via Textract)
#   C  — Cigna Coverage Policy (IP####)
#   D  — UHC Maximum Dosage / Frequency supplementary
#   E  — Change Bulletin / Revision History
#   F  — Cigna PSM (Preferred Specialty Management)
#   ICD10  — ICD-10 pre-extraction pass (all payers)
#   TEMPORAL_DIFF — diff two versions (unchanged)
#   GEMINI_VERIFICATION — cross-model verify (unchanged)

# ─────────────────────────────────────────────────────────────────────────────
# ICD-10 Pre-Extraction Prompt  (runs BEFORE Prompt A/B/C)
# ─────────────────────────────────────────────────────────────────────────────
ICD10_EXTRACTION_PROMPT = """\
Extract ONLY the ICD-10 code mapping from this payer policy document.
Find the section titled "Applicable Codes" (UHC), "Coding Information" (Cigna), \
or "Coding" (Aetna). Extract only the indication-to-ICD10 mapping.

Return JSON only:
{{ "icd10Mapping": [{{ "indicationName": string, "icd10Codes": [string] }}] }}

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt A — UHC Drug-Specific Policy Extraction
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_A_UHC = """\
You are extracting structured medical benefit drug policy criteria from a UnitedHealthcare \
Commercial Medical Benefit Drug Policy document. Your output feeds a clinical decision \
support system — accuracy is critical.

Document metadata:
- Payer: UnitedHealthcare
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE — UHC policies follow this EXACT template. Use section names to navigate:

STEP 1 — BEFORE parsing clinical criteria, extract the ICD-10 mapping from the \
"Applicable Codes" section. This section appears BEFORE the Diagnosis-Specific Criteria \
section in the document. It contains statements like:
  "[Indication Name]: [ICD-10-1], [ICD-10-2], [ICD-10-3]"
Build a lookup map: {{ indicationName: [icd10codes] }}.

STEP 2 — Extract preferred product information from the "Coverage Rationale" section, \
which comes BEFORE the Diagnosis-Specific Criteria. It contains a "Preferred Product" \
subsection listing biosimilars in preference order (rank 1 = most preferred).

STEP 3 — Parse the "Diagnosis-Specific Criteria" section. For each indication:

  INDICATION DETECTION: A new indication block begins with a bold statement matching the \
  pattern: "Infliximab is proven for the treatment of [INDICATION]."

  INITIAL CRITERIA: The block "For initial therapy, all of the following:" contains AND logic.
  Every bullet point under this block is a REQUIRED criterion (AND).

  CONTINUATION CRITERIA: The block "For continuation of therapy, all of the following:" \
  contains reauthorization criteria.

  LOGIC MARKERS:
  - "all of the following" = AND (every item must be met)
  - "one of the following" = OR (any one is sufficient)
  - "History of failure to [N] of the following" = step therapy; N is the minimum number \
    of drugs that must have been tried. Extract N as the count.
  - Sub-bullets marked with "o" are alternatives within an OR block.

  AUTHORIZATION DURATION: Look for the phrase "Initial authorization is for no more than \
  [N] months" in the continuation criteria block. Extract N as initialAuthDurationMonths.

  PRESCRIBER: Look for "Prescribed by or in consultation with a [SPECIALIST TYPE]".

  DOSING:
  - If the text says "dosed according to U.S. FDA labeled dosing" — set dosingLimits to null \
    and note in rawExcerpt that dosing is per FDA label (see Max Dosage Policy).
  - If text specifies explicit mg/kg limits, extract them: maxDoseMgPerKg, maxFrequency.

  COMBINATION RESTRICTIONS: Look for "Patient is NOT receiving [drugName] in combination with" \
  followed by a list. Extract each listed drug as a combinationRestrictions entry.

STEP 4 — For each indication, merge the ICD-10 codes from Step 1 using the indication name \
as the key. If no match is found, set indicationICD10 to null.

Pre-extracted ICD-10 mapping (use this to populate indicationICD10 fields):
{icd10Json}

BOILERPLATE: Ignore the "Instructions for Use" section at the end of the document. It is \
administrative boilerplate and contains no clinical criteria.

CROSS-REFERENCES: If the criteria text references another UHC policy (e.g., "see Maximum \
Dosage and Frequency Policy"), note this in criterionText but do not invent values for the \
referenced data.

OUTPUT FORMAT:
Return a valid JSON array where each element is a DrugPolicyCriteriaRecord:
{{
  "drugName": string,
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "UnitedHealthcare",
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [
    {{ "productName": string, "rank": number }}
  ],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | \
                       "dosing" | "combination_restriction" | "age" | "severity",
      "logicOperator": "AND" | "OR",
      "requiredDrugsTriedFirst": [string],
      "stepTherapyMinCount": number,
      "trialDurationWeeks": number | null,
      "prescriberType": string | null,
      "requiresDocumentation": string | null,
      "rawExcerpt": string
    }}
  ],
  "reauthorizationCriteria": [
    {{
      "criterionText": string,
      "criterionType": string,
      "logicOperator": "AND" | "OR",
      "maxAuthDurationMonths": number | null,
      "requiresDocumentation": string | null,
      "rawExcerpt": string
    }}
  ],
  "dosingLimits": {{
    "maxDoseMg": number | null,
    "maxFrequency": string | null,
    "weightBased": boolean,
    "maxDoseMgPerKg": number | null,
    "perFDALabel": boolean
  }} | null,
  "combinationRestrictions": [
    {{ "restrictedWith": string, "restrictionType": "same_class" | "same_indication" | "absolute" }}
  ],
  "quantityLimits": null,
  "benefitType": "medical",
  "selfAdminAllowed": null,
  "coveredStatus": "covered" | "excluded" | "experimental",
  "confidence": number
}}

CRITICAL RULES:
- Each indication block is INDEPENDENT. Never merge criteria across indications.
- Preserve exact drug names from the document for requiredDrugsTriedFirst (e.g., "Inflectra" \
  not just "infliximab biosimilar").
- If a criterion says "History of failure to 1 of the following [list]", set \
  stepTherapyMinCount to 1 (not the count of drugs listed).
- For continuation criteria, if auth duration is stated, set maxAuthDurationMonths.
- Set confidence below 0.7 if: criteria text is ambiguous, contains cross-references to \
  other policies, or has complex conditional structures you cannot fully resolve.
- Do NOT invent values. Omit fields that are not stated in the document.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt B — Aetna CPB Extraction
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_B_AETNA = """\
You are extracting structured medical benefit drug policy criteria from an Aetna Clinical \
Policy Bulletin (CPB) document. Your output feeds a clinical decision support system.

Document metadata:
- Payer: Aetna
- CPB Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE — Aetna CPBs follow this template. Navigate by section name:

STEP 1 — Extract prescriber requirements from the "Prescriber Specialties" section.
This section contains per-indication specialist mappings, e.g.:
  "Crohn's disease: gastroenterologist or colorectal surgeon"
  "Rheumatoid arthritis: rheumatologist"
Build a lookup: {{ indicationName: prescriberType }}

STEP 2 — Extract initial criteria from "Criteria for Initial Approval" section.
Organized as numbered sections by indication.

  INDICATION DETECTION: "1. [Indication Name]" marks the beginning of each indication block.

  LOGIC MARKERS (look for italic text or emphasis patterns as signals):
  - "*all* of the following" → AND
  - "*any* of the following" → OR (3+ alternatives)
  - "*either* of the following" → OR (exactly 2 alternatives)

  AUTHORIZATION DURATION: Look for "Authorization of [N] months may be granted" — typically \
  appears as the first sentence within an indication block, before the criteria list.

  STEP THERAPY: Aetna specifies step therapy with dose AND duration together. Example:
  "3-month trial of methotrexate at maximum titrated dose of at least 15 mg per week"
  Extract: trialDurationWeeks (convert months to weeks: 3 months = ~12 weeks), \
  stepTherapyMinDoseMg (15 mg), stepTherapyDoseFrequency ("per week").

STEP 3 — Extract continuation criteria from the SEPARATE "Continuation of Therapy" section.
This section is NOT per-indication — it covers all indications with general response \
documentation requirements.

STEP 4 — Extract dosing from the "Dosing" TABLE (if present):
| Indication | Dose |
Capture: indicationName, doseMgPerKg, frequency, infusionSchedule (e.g., "at 0, 2, 6 weeks \
then every 8 weeks")

STEP 5 — Extract excluded indications from "Experimental, Investigational, or Unproven" \
section. Each listed condition should be extracted as a separate record with \
coveredStatus: "experimental".

STEP 6 — Extract ICD-10 codes from the "Coding" section tables. Match to indications.

Pre-extracted ICD-10 mapping (use this to populate indicationICD10 fields):
{icd10Json}

OUTPUT FORMAT:
Return a valid JSON array of DrugPolicyCriteriaRecord objects:
{{
  "drugName": string,
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "Aetna",
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | \
                       "dosing" | "combination_restriction" | "age" | "severity",
      "logicOperator": "AND" | "OR",
      "requiredDrugsTriedFirst": [string],
      "trialDurationWeeks": number | null,
      "stepTherapyMinDoseMg": number | null,
      "stepTherapyDoseFrequency": string | null,
      "prescriberType": string | null,
      "rawExcerpt": string
    }}
  ],
  "reauthorizationCriteria": [
    {{
      "criterionText": string,
      "criterionType": string,
      "requiresDocumentation": string | null,
      "maxAuthDurationMonths": number | null
    }}
  ],
  "dosingLimits": {{
    "maxDoseMg": number | null,
    "maxDoseMgPerKg": number | null,
    "maxFrequency": string | null,
    "infusionSchedule": string | null,
    "weightBased": boolean,
    "perFDALabel": false
  }} | null,
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered" | "excluded" | "experimental",
  "exclusionReason": string | null,
  "confidence": number
}}

CRITICAL RULES:
- The Prescriber Specialties section maps per indication — always check this section for \
  prescriberType, not just the indication criteria blocks.
- "either" = OR (binary choice). "any" = OR (multiple choices). Do not conflate these.
- Aetna's continuation section is GLOBAL, not per-indication. Apply it to all indications.
- For excluded indications (from "Experimental, Investigational, or Unproven"), create a \
  record with empty initialAuthCriteria and coveredStatus: "experimental".
- Do NOT invent values. Omit fields not present in the document.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt C — Cigna Coverage Policy (IP####)
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_C_CIGNA = """\
You are extracting structured medical benefit drug policy criteria from a Cigna Drug \
Coverage Policy document (type IP####). Your output feeds a clinical decision support system.

Document metadata:
- Payer: Cigna
- Coverage Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE — Cigna IP documents follow this template:

STEP 1 — IGNORE the "INSTRUCTIONS FOR USE" section at the beginning of the document.
It is identical boilerplate across all Cigna policies. Begin reading at "OVERVIEW".

STEP 2 — From the "OVERVIEW" section, extract:
- All FDA-approved indications (bulleted list)
- All product names (brand and biosimilar) listed in the policy title and overview

STEP 3 — Parse the "Coverage Policy" section — this is the core extraction target.
It uses a NESTED numbered/lettered structure:

  TOP-LEVEL INDICATION:
  "[NUMBER]. [Indication Name]. Approve for the duration noted if the patient meets ONE \
  of the following (A or B):"
  → TOP-LEVEL LOGIC IS ALWAYS "OR" between branches A and B
  → A = Initial Therapy branch
  → B = Continuation/Currently Receiving branch

  BRANCH A (Initial Therapy):
  "A) Initial Therapy. Approve for [N] months if the patient meets BOTH of the following \
  (i and ii):"
  → BRANCH A LOGIC IS "AND" — all sub-criteria (i, ii, iii...) must be met
  → Extract N as initialAuthDurationMonths

  BRANCH B (Continuation/Currently Receiving):
  "B) Patient is Currently Receiving. Approve for [N] months if the patient meets ALL \
  of the following (i and ii):"
  → BRANCH B LOGIC IS "AND"
  → Extract N as maxAuthDurationMonths for reauthorizationCriteria

  NESTED CRITERIA:
  Within Branch A, sub-criteria use roman numerals (i, ii, iii) and sometimes further \
  nesting with letters (a, b, c). Example nested OR:
  "iii. Patient has had inadequate response to ONE of the following (a, b, or c):
        a. Methotrexate
        b. Leflunomide
        c. Sulfasalazine"
  → This is an OR block nested INSIDE the AND block of Branch A.
  → For the step therapy criterion, set logicOperator: "OR" on the sub-items.

  PRESCRIBER: Look for "The medication is prescribed by or in consultation with a [SPECIALIST]"

  STEP THERAPY:
  - Look for "inadequate response, intolerance, or contraindication to" — all three reasons \
    count as valid prior drug failure outcomes
  - "minimum [N]-month trial" → trialDurationWeeks = N * 4
  - "at therapeutic dose" → note in criterionText

  APPROVAL DURATIONS:
  - Initial (Branch A): "Approve for [N] months if..." → initialAuthDurationMonths
  - Continuation (Branch B): "Approve for [N] months if..." → maxAuthDurationMonths
  - These are DIFFERENT values — extract both separately

STEP 4 — From "Coding Information" section, extract ICD-10 codes per indication.
Usually in a table format. Map to indication names.

Pre-extracted ICD-10 mapping (use this to populate indicationICD10 fields):
{icd10Json}

OUTPUT FORMAT:
Return a valid JSON array of DrugPolicyCriteriaRecord objects:
{{
  "drugName": string,
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "Cigna",
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "prescriber_requirement" | \
                       "age" | "severity" | "combination_restriction",
      "logicOperator": "AND" | "OR",
      "parentBranch": "A",
      "requiredDrugsTriedFirst": [string],
      "stepTherapyLogic": "any",
      "stepTherapyMinCount": 1,
      "trialDurationWeeks": number | null,
      "trialDurationNote": string | null,
      "prescriberType": string | null,
      "rawExcerpt": string
    }}
  ],
  "reauthorizationCriteria": [
    {{
      "criterionText": string,
      "criterionType": string,
      "parentBranch": "B",
      "maxAuthDurationMonths": number | null,
      "requiresDocumentation": string | null,
      "rawExcerpt": string
    }}
  ],
  "dosingLimits": null,
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered",
  "confidence": number
}}

CRITICAL RULES:
- The "ONE of the following (A or B)" at the top of each indication creates TWO SEPARATE \
  records: initialAuthCriteria (from Branch A) and reauthorizationCriteria (from Branch B).
  Never mix Branch A and Branch B criteria.
- preferredProducts MUST be left empty — this data comes from the companion PSM document.
- "Approve for [N] months" appears TWICE per indication — once in Branch A (initial), \
  once in Branch B (continuation). Extract BOTH.
- "ONE of the following (a, b, or c)" within Branch A = OR logic. "BOTH of the following" \
  within Branch A = AND logic. Preserve this in logicOperator.
- For step therapy, "inadequate response, intolerance, OR contraindication" — all three \
  are acceptable failure reasons; do not restrict to only "inadequate response".
- Ignore the "INSTRUCTIONS FOR USE" boilerplate. It starts with "This Coverage Policy \
  addresses coverage determinations..." and ends before "OVERVIEW".
- Do NOT invent values. Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt D — UHC Maximum Dosage / Frequency Supplementary
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_D_DOSING = """\
You are extracting dosing limit data from a UnitedHealthcare Maximum Dosage and Frequency \
policy document (Policy 2026D0034AT or similar). This data supplements drug-specific \
policy extractions where the drug policy defers dosing to "FDA labeled dosing."

Document metadata:
- Payer: UnitedHealthcare
- Policy Number: {policyNumber}
- Document Title: Maximum Dosage and Frequency
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE:
This policy contains tables organized by drug name or drug class. Each table row specifies:
  [HCPCS Code] | [Drug Description] | [Indication] | [Maximum Units] | [Per Period]

EXTRACTION TASK:
For each row in the dosing tables, extract:

{{
  "hcpcsCode": string,
  "drugName": string,
  "brandName": string | null,
  "indicationName": string | null,
  "maxUnits": number,
  "unitDefinition": string,
  "periodDays": number,
  "periodDescription": string,
  "maxDoseMg": number | null,
  "rawExcerpt": string
}}

Return a JSON array. These records will be merged into DrugPolicyCriteria records by \
matching on drugName + indicationName + hcpcsCode.

CRITICAL RULES:
- Extract ONLY drug dosing data. Ignore administrative and boilerplate sections.
- If a row specifies limits for a drug+indication pair already in the primary drug policy, \
  this row supersedes the "per FDA labeled dosing" placeholder in the drug policy.
- If HCPCS unit definition is ambiguous (e.g., "per 10 mg"), state it in unitDefinition.
- Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt E — Change Bulletin / Revision History
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_E_CHANGES = """\
You are extracting policy change records from a payer policy update document. This may be \
a Cigna monthly policy update bulletin (listing changes across many policies in a table) \
or a UHC Policy History/Revision Information table (at the end of a single policy document).

Document metadata:
- Payer: {payerName}
- Document Type: {documentType}
- Period Covered: {period}
- Effective Date: {effectiveDate}

EXTRACTION TASK:
For each policy change entry, extract a PolicyDiff record:

{{
  "payer": string,
  "policyNumber": string | null,
  "policyTitle": string | null,
  "drugName": string | null,
  "indicationName": string | null,
  "changeEffectiveDate": string,
  "changeType": "revision_summary",
  "rawChangeText": string,
  "inferredSeverity": "breaking" | "restrictive" | "relaxed" | "neutral" | "unknown",
  "inferredSeverityReason": string
}}

SEVERITY CLASSIFICATION GUIDE:
- "breaking" — coverage removed entirely, mandatory biosimilar step therapy added for the \
  first time, indication removed, trial duration increased (more restrictive baseline)
- "restrictive" — additional documentation required, auth period shortened, new combination \
  restriction added, prescriber requirement narrowed
- "relaxed" — new indication added, step therapy requirement removed, auth period extended, \
  biosimilar requirement loosened, trial duration reduced
- "neutral" — administrative language change only, formatting change, reference update, \
  no change to clinical criteria

CIGNA MONTHLY BULLETIN FORMAT:
The document contains tables with columns:
  Coverage Policy Number | Policy Title | Summary of Changes | Effective Date
Extract one record per table row.

UHC REVISION HISTORY FORMAT:
The table at the end of a policy document has columns:
  Date | Summary of Changes
Extract one record per table row. Use the parent policy's policy number and title.

Return a JSON array of PolicyDiffRecord objects.

CRITICAL RULES:
- Do NOT infer or add clinical criteria — only extract what is stated in the change summary.
- If the change summary is too vague to classify severity (e.g., "Policy updated"), use \
  inferredSeverity: "unknown".
- Normalize drug names to generic: "REMICADE" → "infliximab", "HUMIRA" → "adalimumab".
- For Cigna bulletins, one policy may have multiple changes in one row — split into \
  separate records if the summary lists multiple distinct changes.
- Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt F — Cigna PSM (Preferred Specialty Management)
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_F_PSM = """\
You are extracting preferred product and non-preferred product exception criteria from a \
Cigna Preferred Specialty Management (PSM) document. This data supplements a companion \
Coverage Policy (IP####) for the same drug.

Document metadata:
- Payer: Cigna
- PSM Policy Number: {psmNumber}
- Companion IP Policy Number: {companionIpNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE — Cigna PSM documents follow this template:

STEP 1 — IGNORE the "INSTRUCTIONS FOR USE" boilerplate at the beginning.

STEP 2 — From "POLICY STATEMENT" section, extract:
- Preferred products list (explicitly labeled "Preferred")
- Non-preferred products list (explicitly labeled "Non-Preferred")

STEP 3 — From "NON-PREFERRED PRODUCT EXCEPTION CRITERIA" section (may be a table):
The table format is:
  | Non-Preferred Products | Exception Criteria |
Each exception criterion specifies what the patient must demonstrate to access the \
non-preferred product when preferred products have failed.

EXTRACTION OUTPUT:
{{
  "psmPolicyNumber": string,
  "companionIpPolicyNumber": string,
  "drugName": string,
  "preferredProducts": [
    {{
      "productName": string,
      "genericSuffix": string | null,
      "rank": 1,
      "preferredStatus": "preferred"
    }}
  ],
  "nonPreferredProducts": [
    {{
      "productName": string,
      "preferredStatus": "non_preferred",
      "exceptionCriteria": [
        {{
          "criterionText": string,
          "criterionType": "step_therapy" | "prescriber_attestation" | "diagnosis" | "other",
          "requiredTrialProduct": string | null,
          "trialDurationWeeks": number | null,
          "trialOutcomeRequired": string | null,
          "logicOperator": "AND" | "OR",
          "rawExcerpt": string
        }}
      ]
    }}
  ],
  "effectiveDate": string,
  "payerName": "Cigna"
}}

Return a JSON object (not an array — this is one PSM document, not multiple records).

CRITICAL RULES:
- Preferred products typically include all approved biosimilars; non-preferred is typically \
  the reference (originator) product.
- "hypersensitivity reaction" is a distinct failure reason from "intolerance" — preserve all \
  three: inadequate response, intolerance, hypersensitivity.
- The trial duration in PSM documents refers to a trial of the PREFERRED product, not \
  prior conventional therapy.
- This output will be merged into DrugPolicyCriteria.preferredProducts for the companion \
  IP policy. The merge key is companionIpPolicyNumber + drugName.
- Return ONLY the JSON object. No explanation, no markdown.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Legacy generic fallback prompt — kept for unknown payers
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

Pre-extracted ICD-10 mapping (use this to populate indicationICD10 fields):
{icd10Json}

The document covers one or more drugs across one or more indications. For EACH \
drug-indication pair, extract:

1. drugName: normalized generic name (e.g., "infliximab", never "Remicade")
2. brandNames: all brand names mentioned in this section
3. indicationName: exact medical condition (e.g., "rheumatoid arthritis", \
"Crohn's disease")
4. indicationICD10: [string] from pre-extracted ICD-10 mapping above
5. preferredProducts: ordered list [{{productName, rank}}], 1 = most preferred
6. initialAuthDurationMonths: number — initial authorization period in months
7. initialAuthCriteria: array of individual requirements, each with:
   - criterionText: human-readable statement
   - criterionType: "diagnosis"|"step_therapy"|"lab_value"|\
"prescriber_requirement"|"dosing"|"combination_restriction"|"age"|"severity"
   - logicOperator: "AND"|"OR"
   - requiredDrugsTriedFirst: [drug names] — only for step_therapy
   - stepTherapyMinCount: number — minimum drugs that must fail
   - trialDurationWeeks: number — only if explicitly stated
   - prescriberType: string — only for prescriber_requirement
   - rawExcerpt: exact text passage
8. reauthorizationCriteria: same structure as initialAuthCriteria, plus:
   - maxAuthDurationMonths: number
   - requiresDocumentation: string describing required clinical evidence
9. dosingLimits: {{maxDoseMg, maxFrequency, weightBased: bool, maxDoseMgPerKg, \
perFDALabel: bool}}
10. combinationRestrictions: [{{restrictedWith, restrictionType: \
"same_class"|"same_indication"|"absolute"}}]
11. quantityLimits: {{maxUnitsPerPeriod, periodDays}}
12. benefitType: "medical"|"pharmacy" based on document context
13. selfAdminAllowed: boolean
14. coveredStatus: "covered"|"excluded"|"experimental"
15. rawExcerpt: the exact text passage you extracted this from (for citation)
16. confidence: 0.0-1.0 — your confidence in the accuracy of this extraction

CRITICAL RULES:
- Parse conditional logic precisely. "All of the following" = AND (all must be \
met). "One of the following" = OR (any one sufficient). Track this in logicOperator.
- Each indication section is INDEPENDENT. Never merge criteria across indications.
- If a criterion references another policy document, note this in criterionText \
but do not follow the reference.
- Normalized drug names only: "infliximab" not "REMICADE®"
- If a field is not specified in the document, omit it entirely. Do not invent values.
- Rate confidence below 0.7 if: the section is ambiguous, uses complex \
conditional logic, or references external policies.

Return a valid JSON array of DrugPolicyCriteriaRecord objects. Return ONLY the \
JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Temporal Diff Prompt (unchanged from spec 10.4)
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


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Verification Prompt (unchanged from spec 10.6)
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_VERIFICATION_PROMPT = """\
You are verifying the accuracy of an AI extraction of medical benefit drug \
policy criteria. Another AI model extracted the following structured data from \
the policy text. Your job is to identify any errors or misclassifications.

Extracted data:
{extracted}

Original policy text (excerpt):
{raw_text}

Check specifically for:
1. Incorrectly classified criterionType (e.g., a step_therapy requirement \
labeled as "diagnosis")
2. Missing required drugs in requiredDrugsTriedFirst
3. Incorrect trial duration numbers
4. Missing indications (a drug-indication pair present in the text but not \
extracted)
5. Incorrect benefitType classification
6. Incorrect stepTherapyMinCount (e.g., "1 of the following" extracted as count=3)
7. Missing initialAuthDurationMonths or maxAuthDurationMonths

For each issue found, specify: field, extractedValue, correctValue, \
confidence (0-1).
If no issues found, return empty issues array.

Return JSON only:
{{
  "issues": [
    {{ "field": string, "extractedValue": string, "correctValue": string, \
"confidence": number }}
  ],
  "overallVerificationConfidence": number
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt routing map — used by bedrock_extract.py to select the right prompt
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_MAP = {
    "drug_specific": {
        "UnitedHealthcare": PROMPT_A_UHC,
        "UHC": PROMPT_A_UHC,
        "Aetna": PROMPT_B_AETNA,
        "Cigna": PROMPT_C_CIGNA,
    },
    "max_dosage": PROMPT_D_DOSING,
    "update_bulletin": PROMPT_E_CHANGES,
    "preferred_specialty_mgmt": PROMPT_F_PSM,
}

# Document classes that should NOT be extracted (index-only)
NO_EXTRACTION_CLASSES = {"formulary", "self_admin", "pa_framework", "site_of_care"}
