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
# Prompt A-Multiproduct — UHC Multi-Product Policy (e.g., Botulinum Toxins)
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_A_UHC_MULTIPRODUCT = """\
You are extracting structured medical benefit drug policy criteria from a UnitedHealthcare \
multi-product policy document. This document covers MULTIPLE distinct products (each with its \
own brand name) that may have DIFFERENT covered indications.

Document metadata:
- Payer: UnitedHealthcare
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Structure Note: {payerStructureNote}

CRITICAL — MULTI-PRODUCT ISOLATION:
Extract ONLY indications explicitly listed under each specific product's section header. \
Do NOT assume that an indication covered for one product is also covered for another product. \
If Botox lists "chronic migraine" but Dysport does NOT list it, then Dysport does NOT cover it.

DOCUMENT STRUCTURE:
1. "General Requirements" section — criteria that apply to ALL products and ALL indications.
   Extract these as universalCriteria on every record.
2. Per-product sections:
   Header pattern: "[Product]® ([generic]) is proven in the treatment of the following conditions:"
   Each product section lists its OWN indications.
3. "Unproven" section — conditions NOT covered (coveredStatus: "unproven").
4. Excluded products (e.g., Daxxify) — explicitly excluded from coverage (coveredStatus: "excluded").

STEP 1 — Extract universalCriteria from the "General Requirements" section. \
These apply to every record in the output.

STEP 2 — For each product section, identify the product name and extract its specific indications.

STEP 3 — For each product + indication:
  - Initial authorization criteria
  - Continuation criteria
  - Authorization duration
  - Step therapy (e.g., Myobloc may require prior trial of another toxin)

STEP 4 — Extract "Unproven" conditions (coveredStatus: "unproven", empty criteria arrays).

STEP 5 — Identify excluded products (coveredStatus: "excluded", empty criteria arrays).

STEP 6 — Frequency cap (e.g., "no more frequently than every 12 weeks") → add to \
universalCriteria AND to dosingLimits.maxFrequency.

Pre-extracted ICD-10 mapping:
{icd10Json}

OUTPUT FORMAT — Return a valid JSON array. One element per product + indication combination:
{{
  "drugName": string,
  "brandNames": [string],
  "productName": string,
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "UnitedHealthcare",
  "effectiveDate": string,
  "policyNumber": string,
  "universalCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | "dosing" | "age" | "severity",
      "logicOperator": "AND" | "OR",
      "rawExcerpt": string
    }}
  ],
  "preferredProducts": [],
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
  "combinationRestrictions": [],
  "quantityLimits": null,
  "benefitType": "medical",
  "selfAdminAllowed": null,
  "coveredStatus": "covered" | "unproven" | "excluded",
  "confidence": number
}}

CRITICAL RULES:
- universalCriteria must appear on EVERY record — do not omit it.
- Each product section is INDEPENDENT. Never cross-assign indications between products.
- Daxxify (daxibotulinumtoxinA-lanm): if mentioned as excluded, set coveredStatus: "excluded".
- Unproven conditions: coveredStatus: "unproven", empty initialAuthCriteria.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt C-3Phase — Cigna IP#### Three-Phase Approval (e.g., Rituximab)
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_C_CIGNA_3PHASE = """\
You are extracting structured medical benefit drug policy criteria from a Cigna Drug \
Coverage Policy (IP####) that uses a THREE-PHASE approval structure per indication.

Document metadata:
- Payer: Cigna
- Coverage Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Structure Note: {payerStructureNote}

CRITICAL — THREE SEPARATE PHASES:
Each numbered indication has THREE separate approval paths. Extract EACH as a separate record \
with its own approvalPhase label. NEVER merge criteria from different phases into one record.

PHASE STRUCTURE per indication:
  A) Initial Therapy:
     "Approve for [N] months if the patient meets ALL of the following..."
     → approvalPhase: "initial", approvalDurationMonths: N
  B) Patient has received one prior course of therapy:
     "Approve for [N] months if ALL of the following..."
     → approvalPhase: "continuation_1", approvalDurationMonths: N
  C) Patient has received two or more prior courses:
     "Approve for [N] months if ALL of the following..."
     → approvalPhase: "continuation_2plus", approvalDurationMonths: N

STEP 1 — IGNORE "INSTRUCTIONS FOR USE" boilerplate at document start.

STEP 2 — Parse each numbered indication: "1. Rheumatoid Arthritis (RA)"

STEP 3 — Within each indication, find Phase A, B, and C sub-sections.

STEP 4 — Extract criteria for each phase separately. \
"Approve for [N] months if..." → capture N as approvalDurationMonths for that phase.

STEP 5 — NOTE BLOCKS: Lines beginning with "Note:" are clarifications, NOT criteria. \
Do NOT create a CriteriaItem for "Note:" lines. You may incorporate their content into \
the criterionText of the immediately preceding criterion if directly relevant.

STEP 6 — DOSING: Each indication may have a dosing sub-section. \
Extract as dosingPerIndication entries.

STEP 7 — "Conditions Not Covered" section at end: extract as records with \
coveredStatus: "excluded".

Pre-extracted ICD-10 mapping:
{icd10Json}

OUTPUT FORMAT — Return a valid JSON array. \
One element per indication + phase (3 records per indication):
{{
  "drugName": string,
  "brandNames": [string],
  "indicationName": string,
  "approvalPhase": "initial" | "continuation_1" | "continuation_2plus",
  "approvalDurationMonths": number | null,
  "indicationICD10": [string] | null,
  "payerName": "Cigna",
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | "dosing" | "age" | "severity",
      "logicOperator": "AND" | "OR",
      "requiredDrugsTriedFirst": [string],
      "stepTherapyMinCount": number,
      "trialDurationWeeks": number | null,
      "prescriberType": string | null,
      "requiresDocumentation": string | null,
      "rawExcerpt": string
    }}
  ],
  "reauthorizationCriteria": [],
  "dosingPerIndication": [
    {{
      "indicationContext": string,
      "regimen": string,
      "maxDoseMg": number | null
    }}
  ],
  "dosingLimits": null,
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered" | "excluded",
  "confidence": number
}}

CRITICAL RULES:
- Phase A → approvalPhase: "initial", put all criteria in initialAuthCriteria.
- Phase B → approvalPhase: "continuation_1", put criteria in initialAuthCriteria (for this phase's record).
- Phase C → approvalPhase: "continuation_2plus", put criteria in initialAuthCriteria (for this phase's record).
- approvalDurationMonths: extract the N from "Approve for N months if..." for THIS specific phase.
- Do NOT extract "Note:" lines as CriteriaItem entries.
- "Preferred product criteria is met" → extract as step_therapy criterion referencing preferred products.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt G — EmblemHealth / Prime Therapeutics
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_G_EMBLEMHEALTH = """\
You are extracting structured medical benefit drug policy criteria from an EmblemHealth / \
Prime Therapeutics policy document. This document uses universal criteria plus \
indication-specific criteria, organized by product group.

Document metadata:
- Payer: EmblemHealth
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Structure Note: {payerStructureNote}

DOCUMENT STRUCTURE:
1. Universal Criteria — apply to ALL products and ALL indications in this policy \
   (e.g., calcium ≥1000 mg/day, vitamin D ≥400 IU/day, no hypocalcemia, \
   no concurrent bisphosphonate). Extract as universalCriteria on every record.
2. Product-group split:
   - Prolia-type: products indicated for osteoporosis (Prolia, Bildyos, Jubbonti)
   - Xgeva-type: products indicated for oncology (Xgeva, Bilprevda, Wyost)
3. Within each product group: indication-specific initial criteria.
4. Preferred products within each group:
   - Prolia-type: Bildyos / Jubbonti preferred over Prolia
   - Xgeva-type: Bilprevda / Wyost preferred over Xgeva
5. Renewal / Reauthorization Criteria section — extract as reauthorizationCriteria. \
   These are simpler than initial criteria (typically response documentation only).
6. "Length of Authorization" table — extract initialAuthDurationMonths and maxAuthDurationMonths.

FOOTNOTE SYMBOLS (pre-resolved):
Footnote symbols (†, ‡, ¤) have already been replaced inline with \
"[DEFINED AS: full definition text]". \
Treat the [DEFINED AS: ...] content as integral to the criterion definition.

STEP THERAPY WITHIN PRODUCT GROUPS:
The Prolia-type group requires a prior trial of EITHER:
  - 6-month oral bisphosphonate, OR
  - 12-month IV zoledronic acid
Extract as: criterionType: "step_therapy", logicOperator: "OR", \
requiredDrugsTriedFirst: ["oral bisphosphonate (6-month)", "IV zoledronic acid (12-month)"], \
stepTherapyMinCount: 1.

Pre-extracted ICD-10 mapping:
{icd10Json}

OUTPUT FORMAT — Return a valid JSON array. One element per product group + indication:
{{
  "drugName": string,
  "brandNames": [string],
  "productGroup": "prolia_type" | "xgeva_type",
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "EmblemHealth",
  "effectiveDate": string,
  "policyNumber": string,
  "universalCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "lab_value" | "dosing" | "combination_restriction" | "age",
      "logicOperator": "AND",
      "rawExcerpt": string
    }}
  ],
  "preferredProducts": [
    {{ "productName": string, "rank": number, "preferredStatus": "preferred" | "non_preferred" }}
  ],
  "initialAuthDurationMonths": number | null,
  "maxAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | \
                       "dosing" | "age" | "severity",
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
    "perFDALabel": boolean
  }} | null,
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered",
  "confidence": number
}}

CRITICAL RULES:
- universalCriteria must appear on EVERY record — do not omit.
- [DEFINED AS: ...] inline text is part of the criterion — include it in criterionText.
- Prolia-type step therapy: OR between oral bisphosphonate (6-month) and IV zoledronic acid (12-month).
- Preferred biosimilar hierarchy: Bildyos/Jubbonti preferred over Prolia; \
  Bilprevda/Wyost preferred over Xgeva.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt H — Florida Blue / MCG Table-Format Policy
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_H_FLORIDA_BLUE = """\
You are extracting structured medical benefit drug policy criteria from a Florida Blue / MCG \
policy document that uses a TABLE FORMAT for coverage criteria.

Document metadata:
- Payer: Florida Blue
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Structure Note: {payerStructureNote}

DOCUMENT STRUCTURE:
- Table 1: Two-column table — Indication | Criteria. Each row = one clinical indication.
- Section I (Position Statement): initiation criteria applying to ALL indications → universalCriteria.
- Section II: continuation / reauthorization criteria → reauthorizationCriteria.
- Preferred products: Mvasi and Zirabev are preferred; Avastin (reference) is non-preferred.

TABLE 1 PARSING — for each row:
- Column 1 = indicationName
- Column 2 = criteria text with nested AND/OR logic

NESTED LOGIC MARKERS (exact text signals — preserve the logic hierarchy):
- "BOTH of the following:" → AND (numbered sub-items 1, 2)
- "ALL of the following:" → AND (numbered or bulleted sub-items)
- "ONE of the following:" → OR (lettered sub-items a, b, c)
- "ANY of the following:" → OR (lettered sub-items)
Logic can nest up to 3 levels inside a single table cell.

SECTION I — UNIVERSAL CRITERIA:
Extract as universalCriteria. Typical items:
- Indication is listed in Table 1 AND criteria are met
- Dose at or below the threshold (e.g., ≤ 10 mg/kg Q2W or ≤ 15 mg/kg Q3W)
- Biosimilar step therapy (non-preferred products require Mvasi or Zirabev trial first)

SECTION II — CONTINUATION CRITERIA:
Extract as reauthorizationCriteria. Apply to all indications.

Pre-extracted ICD-10 mapping:
{icd10Json}

OUTPUT FORMAT — Return a valid JSON array. One element per Table 1 indication row:
{{
  "drugName": string,
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,
  "payerName": "Florida Blue",
  "effectiveDate": string,
  "policyNumber": string,
  "universalCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "dosing" | "prescriber_requirement",
      "logicOperator": "AND" | "OR",
      "requiredDrugsTriedFirst": [string],
      "rawExcerpt": string
    }}
  ],
  "preferredProducts": [
    {{ "productName": string, "rank": number }}
  ],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {{
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | \
                       "dosing" | "age" | "severity",
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
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered",
  "confidence": number
}}

CRITICAL RULES:
- universalCriteria (from Section I) must appear on EVERY record.
- BOTH/ALL → AND logic. ONE/ANY → OR logic. Map to logicOperator.
- Mvasi and Zirabev are preferred; Avastin is non-preferred.
- Do NOT extract "Description" section boilerplate or MCG disclaimers as clinical criteria.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt B-Formulary — Formulary / Medical Drug List Table Extraction
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_B_FORMULARY_TABLE = """\
You are extracting formulary entries from a health plan Medical Drug List table. \
This is NOT a clinical criteria document — it is a structured list of covered drugs \
with their coverage levels and restrictions.

Document metadata:
- Payer: {payerName}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Therapeutic Category Context: {therapeuticCategory}

INPUT FORMAT — Table rows: HCPCS/CPT | Drug Name | Description | Coverage Level | Notes

NOTES COLUMN CODE MEANINGS:
- PA = Prior Authorization required
- SOS = Site of Service restriction
- CC = Clinical Criteria apply
- SP = Specialty Pharmacy required
- CA:[HCPCS]([drug]) = Covered Alternative (preferred product) — parse as coveredAlternatives
- ICD-10:[codes] = ICD-10 bypass codes — parse comma-separated codes into paBypassIcd10Codes

COVERAGE LEVEL MAPPING:
- "Preferred Specialty" or "Preferred" → "preferred_specialty"
- "Non-Specialty" or "Standard" or "Covered" → "non_specialty"
- "Non-Preferred" → "non_preferred"
- "Not Covered" or "Excluded" or "N/C" → "not_covered"

EXTRACTION TASK — For each drug row (skip headers, skip rows with empty HCPCS column):
{{
  "hcpcsCode": string,
  "drugName": string,
  "genericName": string | null,
  "therapeuticCategory": string,
  "coverageLevel": "preferred_specialty" | "non_specialty" | "non_preferred" | "not_covered",
  "priorAuthRequired": boolean,
  "siteOfServiceRestriction": boolean,
  "specialtyPharmacyRequired": boolean,
  "clinicalCriteriaApply": boolean,
  "coveredAlternatives": [{{ "hcpcsCode": string, "drugName": string }}],
  "paBypassIcd10Codes": [string],
  "rawNotesText": string,
  "documentClass": "formulary"
}}

CRITICAL RULES:
- Skip rows where the HCPCS/CPT column is empty — those are category headers.
- Skip the header row (column labels).
- Use the therapeuticCategory from the metadata above for all rows in this batch.
- Parse CA:[HCPCS]([drug]) into coveredAlternatives entries.
- Parse ICD-10:[codes] — split on commas, trim spaces → paBypassIcd10Codes array.
- If drug name contains both brand and generic (e.g., "RITUXIMAB (Rituxan)"), \
  set drugName to brand name and genericName to generic.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Table rows:
{documentText}"""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt F-Preferred — BCBS NC Preferred Injectable / Preferred Product Programs
# ─────────────────────────────────────────────────────────────────────────────
PROMPT_F_PREFERRED_PRODUCT = """\
You are extracting preferred product program data from a Blue Cross Blue Shield \
Preferred Injectable Oncology policy or similar preferred product program document.

CRITICAL: FDA Approved Use / FDA-Approved Indications sections are REFERENCE LISTS only. \
Do NOT extract their contents as clinical coverage criteria.

Document metadata:
- Payer: {payerName}
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}
- Structure Note: {payerStructureNote}

DOCUMENT STRUCTURE:
- Drug class sections (e.g., bevacizumab agents, rituximab agents, trastuzumab agents)
- Within each drug class: preferred products table and non-preferred products table
- Step therapy is PRODUCT-TIER-BASED: non-preferred product requires trial/failure of preferred product
- Documentation requirements for non-preferred exception access

EXTRACTION TASK — For each drug class, extract ONE preferred product program record:
{{
  "drugClass": string,
  "drugName": string,
  "brandNames": [string],
  "payerName": string,
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [
    {{
      "productName": string,
      "genericSuffix": string | null,
      "rank": 1,
      "preferredStatus": "preferred",
      "hcpcsCode": string | null
    }}
  ],
  "nonPreferredProducts": [
    {{
      "productName": string,
      "preferredStatus": "non_preferred",
      "hcpcsCode": string | null,
      "exceptionCriteria": [
        {{
          "criterionText": string,
          "criterionType": "step_therapy" | "prescriber_attestation" | "diagnosis" | "other",
          "requiredTrialProduct": string | null,
          "trialDurationWeeks": number | null,
          "trialOutcomeRequired": string | null,
          "documentationRequired": string | null,
          "logicOperator": "AND" | "OR",
          "rawExcerpt": string
        }}
      ]
    }}
  ],
  "documentationRequirements": [string],
  "stepTherapySummary": string,
  "documentClass": "preferred_specialty_mgmt"
}}

CRITICAL RULES:
- FDA Approved Use sections = reference only. Do NOT extract as criteria.
- Step therapy is product-tier: preferred must be tried before non-preferred.
- documentationRequirements = prescriber attestations, medical records, or clinical notes required \
  when requesting non-preferred product exception.
- Return a JSON array (one element per drug class). No explanation, no markdown.

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
        "EmblemHealth": PROMPT_G_EMBLEMHEALTH,
        "Prime Therapeutics": PROMPT_G_EMBLEMHEALTH,
        "Florida Blue": PROMPT_H_FLORIDA_BLUE,
        "MCG": PROMPT_H_FLORIDA_BLUE,
    },
    "max_dosage": PROMPT_D_DOSING,
    "update_bulletin": PROMPT_E_CHANGES,
    "preferred_specialty_mgmt": PROMPT_F_PSM,
    "preferred_injectable": PROMPT_F_PREFERRED_PRODUCT,
}

# Explicit prompt ID → template lookup (used by bedrock_extract._get_prompt_template)
PROMPT_ID_MAP: dict = {
    "A": PROMPT_A_UHC,
    "A_MULTIPRODUCT": PROMPT_A_UHC_MULTIPRODUCT,
    "B": PROMPT_B_AETNA,
    "B_FORMULARY": PROMPT_B_FORMULARY_TABLE,
    "C": PROMPT_C_CIGNA,
    "C_3PHASE": PROMPT_C_CIGNA_3PHASE,
    "D": PROMPT_D_DOSING,
    "E": PROMPT_E_CHANGES,
    "F": PROMPT_F_PSM,
    "F_PREFERRED": PROMPT_F_PREFERRED_PRODUCT,
    "G": PROMPT_G_EMBLEMHEALTH,
    "H": PROMPT_H_FLORIDA_BLUE,
}

# Document classes that should NOT be extracted (index-only)
NO_EXTRACTION_CLASSES = {"self_admin", "pa_framework", "site_of_care"}
