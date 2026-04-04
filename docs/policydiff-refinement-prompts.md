# PolicyDiff — Pipeline Refinement Prompts

**For:** Mohith  
**Context:** Backend is built (States 3–7, Prompts A–F for UHC/Aetna/Cigna infliximab). Refining to handle the 6 actual hackathon documents from UHC Botulinum, Cigna Rituximab, EmblemHealth Denosumab, Florida Blue Bevacizumab, Priority Health MDL, and BCBS NC Preferred Injectable.

---

## PROMPT 1: Refine the Ingestion Pipeline (State 3.0 + State 3 + State 4)

Use this prompt with Claude Code or your IDE AI assistant to refine the existing extraction pipeline code.

```text
I have an existing AWS Lambda-based extraction pipeline for medical benefit drug policy PDFs.
The pipeline uses Step Functions: Textract → AssembleText → BedrockExtract → ConfidenceScore → WriteDynamoDB.

EXISTING CODE STRUCTURE:
- backend/lambda/extraction/classify_document.py  (State 3.0 — document type classifier)
- backend/lambda/extraction/assemble_text.py      (State 3 — Textract output assembly)
- backend/lambda/extraction/bedrock_extract.py     (State 4 — Bedrock schema extraction)
- backend/lambda/extraction/confidence_score.py    (State 5 — confidence scoring)
- backend/lambda/extraction/write_criteria.py      (State 6 — DynamoDB batch write)

EXISTING PROMPT ROUTING:
- Prompt A: UHC drug-specific (rigid template, numbered sections)
- Prompt B: Aetna CPB HTML (NOT NEEDED — no Aetna docs in hackathon set)
- Prompt C: Cigna IP#### (3-level AND/OR, Branch A/B)
- Prompt D: UHC Max Dosage supplementary (NOT NEEDED)
- Prompt E: Change bulletins (NOT NEEDED for now)
- Prompt F: Cigna PSM preferred product extraction

THE 6 ACTUAL HACKATHON DOCUMENTS I NEED TO HANDLE:

1. UHC Botulinum Toxins (2026D0017AN, 28 pages, Type A — multi-product)
   - 5 drugs in one policy: Botox, Dysport, Xeomin, Myobloc, Daxxify (excluded)
   - "General Requirements" section = universal criteria for ALL products
   - Per-product sections: "[Product] is proven in the treatment of the following conditions:"
   - Each product has DIFFERENT indication lists
   - "Unproven" section explicitly lists non-covered conditions
   - ICD-10 matrix table (pages 4-10): X markers map diagnosis codes to HCPCS codes
   - Daxxify is EXCLUDED (not just non-preferred — explicitly excluded from coverage)
   - Frequency cap: "no more frequently than every 12 weeks" applies universally

2. Cigna Rituximab Non-Oncology (IP0319, 32 pages, Type A)
   - 20+ numbered indications, each with THREE approval phases:
     A. Initial Therapy (approve for X months if ALL of i, ii, iii...)
     B. One prior course (approve for Y months if ALL of i, ii...)
     C. Two+ prior courses (approve for Z months if ALL of i, ii, iii...)
   - Approval duration EMBEDDED in criteria text: "Approve for 1 month if..."
   - "Note:" blocks = clarification context, NOT criteria (must exclude from extraction)
   - Dosing sub-section after each indication (indication-specific dosing)
   - Preferred Product tables at end of document
   - "Conditions Not Covered" explicit exclusion list

3. EmblemHealth/Prime Therapeutics Denosumab (IC-0098, 16 pages, Type A)
   - TWO-LAYER criteria: Universal Criteria (all products) + Indication-Specific
   - Product-group split: Prolia-type (osteoporosis) vs Xgeva-type (oncology)
   - Symbol footnote system: †, ‡, Ф reference definitions at bottom of section
   - Preferred biosimilar step therapy within product groups
   - Separate "Renewal Criteria" section (different from initial)
   - Dosing Limits table: product group → indication → max HCPCS units

4. Florida Blue/MCG Bevacizumab (09-J0000-66, 15 pages, Type A — DEMO LEAD)
   - TABLE FORMAT: Indication | Criteria columns
   - Nested AND/OR inside table cells ("BOTH of the following:" / "ONE of the following:")
   - Section I = universal initiation criteria (all indications)
   - Section II = continuation criteria
   - Biosimilar step therapy: non-preferred products require Mvasi/Zirabev trial
   - 10+ oncology indications
   - Line-of-business exceptions (HMO/PPO/POS variations)

5. Priority Health Medical Drug List (205 pages, Type B — FORMULARY)
   - NOT a clinical criteria doc — it's a giant table
   - Columns: HCPCS/CPT | Drug Name | Description | Coverage Level | Notes & Restrictions
   - Notes codes: PA, SOS, CC, CA:[HCPCS], ICD-10:[bypass codes]
   - ~2000-3000 drug entries across 205 pages
   - Needs completely separate schema: FormularyEntry (not DrugPolicyCriteria)

6. BCBS NC Preferred Injectable Oncology (26 pages, Type C)
   - Preferred vs non-preferred product tables per drug class (bevacizumab, rituximab, trastuzumab)
   - Step therapy is product-tier-based, not indication-based
   - FDA Approved Use sections = reference lists only, NOT clinical criteria
   - Documentation requirements for non-preferred products
   - Similar to Cigna PSM (Prompt F)

WHAT I NEED YOU TO DO:

1. REFACTOR classify_document.py:
   - Add new payer detection for EmblemHealth, Florida Blue (MCG), Priority Health, BCBS NC
   - Map each to the correct extraction prompt:
     * UHC Botulinum → Prompt A (UHC variant — add multi-product handling)
     * Cigna Rituximab → Prompt C (existing, with 3-phase enhancement)
     * EmblemHealth → NEW Prompt G (universal + specific criteria, footnote symbols, product-group split)
     * Florida Blue → NEW Prompt H (table-format parsing, Section I universal criteria)
     * Priority Health → NEW Prompt B-formulary (table row extraction to FormularyEntry schema)
     * BCBS NC → Prompt F (existing PSM prompt, adapted for broader preferred product programs)
   - Detection signals:
     * UHC: "UnitedHealthcare" + policy number pattern YYYYD####XX
     * Cigna: "Cigna" + IP#### pattern
     * EmblemHealth: "EmblemHealth" or "Prime Therapeutics" + IC-#### pattern
     * Florida Blue: "Florida Blue" or "MCG" + reference pattern ##-J####-##
     * Priority Health: "Priority Health" + "Medical Drug List"
     * BCBS NC: "Blue Cross Blue Shield of North Carolina" + "Preferred Injectable"

2. REFACTOR assemble_text.py:
   - Add payer-specific pre-processing:
     * EmblemHealth: Footnote resolution — scan for †, ‡, Ф symbols, build lookup table from footnote
       definitions at section bottoms, replace inline: "response†" → "response [DEFINED AS: fracture
       despite therapy, continued bone loss ≥5% over 12 months, or inability to tolerate]"
     * UHC Botulinum: After extracting "General Requirements" section, split remaining text into
       per-product chunks at "[Product] is proven in the treatment of..." headers. Prepend General
       Requirements to each chunk.
     * Cigna: Split at numbered indication headers (r"^\d+\.\s+[A-Z]"). Include "Preferred Product"
       tables as shared context appended to each chunk.
     * Florida Blue: Textract TABLES mode is critical — extract Table 1 rows. Each row = one indication.
       Parse the Criteria cell content preserving "BOTH of the following:" / "ONE of the following:" markers.
     * Priority Health: Textract TABLES mode. Extract rows in 50-row batches. Skip rows where
       HCPCS/CPT column is empty (those are therapeutic category headers).
   - Add boilerplate stripping rules:
     * UHC: Strip "Instructions for Use" footer (last ~2 pages), "Related Commercial Policies" sidebar
     * Cigna: Strip "INSTRUCTIONS FOR USE" (first 2-3 pages), "OVERVIEW", "Guidelines" citation list
     * EmblemHealth: Strip Prime Therapeutics header, "This policy applies to..." preamble
     * Florida Blue: Strip "Description" section, MCG disclaimers, "Related Guidelines", "References"
     * BCBS NC: Strip "Policy Summary" boilerplate, "Revision History" table

3. REFACTOR bedrock_extract.py:
   - Route to the correct prompt based on extractionPromptId from classify_document
   - For Prompt A (UHC Botulinum), inject this payer structure note:
     "This document has a 'General Requirements' section that applies to ALL products and
     indications. Extract these as universalCriteria. Then each product has its own section
     starting with '[Product] is proven in the treatment of the following conditions:'.
     Extract per-product. The 'Unproven' section lists conditions NOT covered — extract
     each as coveredStatus: 'unproven'. Daxxify is EXCLUDED from coverage entirely."
   - For Prompt C (Cigna Rituximab), inject:
     "Each indication has THREE approval phases: A (Initial Therapy), B (one prior course),
     C (two or more prior courses). Extract each as separate phase with approvalPhase field.
     'Approve for X months if...' — capture X as approvalDurationMonths. 'Note:' blocks
     are NOT criteria — do not extract them as CriteriaItem entries."
   - For Prompt G (EmblemHealth), inject:
     "Universal Criteria appear before indication-specific criteria. Extract Universal Criteria
     ONCE as universalCriteria. Symbols like †, ‡, Ф have been pre-resolved to their
     footnote definitions. Products are split into Prolia-type and Xgeva-type groups."
   - For Prompt H (Florida Blue), inject:
     "Criteria are in a table: Indication | Criteria. Each row is one indication. Parse
     Criteria cell for nested AND/OR logic ('BOTH of the following:' = AND, 'ONE of the
     following:' = OR). Section I initiation criteria apply to ALL indications — extract
     as universalCriteria."

4. UPDATE THE EXTRACTION OUTPUT SCHEMA to include these new fields:
   - universalCriteria: CriteriaItem[] — criteria that apply to ALL indications in this policy
   - approvalDurationMonths: number — on CriteriaItem, for Cigna's embedded durations
   - approvalPhase: "initial" | "continuation_1" | "continuation_2plus" — for Cigna 3-phase
   - coveredStatus: "proven" | "unproven" | "excluded" | "not_addressed"
   - productName: string — specific product brand (for multi-product policies like UHC Botulinum)
   - FIX drugIndicationId sort key: {drugName}#{productName}#{indicationCode}
     (productName is null/empty for single-product policies)
   - dosingPerIndication: [{indicationContext, regimen, maxDoseMg}] — for Cigna indication-specific dosing

5. ADD FormularyEntry schema for Priority Health (Type B docs):
   {
     policyDocId: string (PK),
     formularyEntryId: string (SK) — "{hcpcsCode}#{drugName}",
     hcpcsCode: string,
     drugName: string,
     genericName: string,
     therapeuticCategory: string,
     coverageLevel: "preferred_specialty" | "non_specialty" | "non_preferred" | "not_covered",
     priorAuthRequired: boolean,
     siteOfServiceRestriction: boolean,
     coveredAlternatives: [{hcpcsCode, drugName}],
     paBypassIcd10Codes: string[],
     rawNotesText: string,
     payerName: string,
     planType: string,
     lastUpdated: string
   }

CONSTRAINTS:
- Keep all Lambda functions under 256MB memory, 5-minute timeout
- Bedrock model: anthropic.claude-sonnet-4-5 (us-east-1)
- Textract: use TABLES + FORMS mode for Type A/C docs, TABLES-only for Type B
- All existing API contracts (State I/O) must remain backward-compatible
- Python 3.12 runtime
- boto3 for all AWS calls

OUTPUT:
- Refactored classify_document.py with new payer routing
- Refactored assemble_text.py with payer-specific pre-processing (footnote resolution,
  product splitting, boilerplate stripping)
- Refactored bedrock_extract.py with new prompt routing and payer structure notes
- Updated write_criteria.py to handle new schema fields and FormularyEntry writes
- Each file should be complete and runnable — not just the changed sections
```

---

## PROMPT 2: Textract Parsing & Bedrock Extraction Prompt Refinement

Use this prompt to generate/refine the actual Bedrock extraction prompts that go inside bedrock_extract.py.

```text
I need to refine the Bedrock extraction prompts for a medical benefit drug policy extraction
pipeline. The pipeline uses AWS Textract for PDF-to-text, then sends structured text to
AWS Bedrock (Claude Sonnet) for schema extraction.

CURRENT STATE:
- I have a working extraction prompt (Prompt 10.1 from our spec) that handles generic
  drug policy extraction
- I have payer-specific prompts for UHC (Prompt A) and Cigna (Prompt C)
- These were built for UHC/Cigna infliximab documents

PROBLEM:
The actual hackathon documents have structural patterns my prompts don't handle:
1. Multi-product policies (UHC Botulinum: 5 drugs, different indications per drug)
2. Three-phase approval (Cigna Rituximab: Initial/1-course/2+-courses per indication)
3. Universal + specific criteria layers (EmblemHealth, UHC)
4. Table-format criteria (Florida Blue: Indication | Criteria table)
5. Symbol footnote systems (EmblemHealth: †, ‡, Ф reference definitions)
6. Formulary tables (Priority Health: 205 pages of drug list rows)
7. Preferred product programs (BCBS NC: preferred/non-preferred tiers, not clinical criteria)

WHAT I NEED:
Generate 4 refined extraction prompts as Python string constants, each with:
- A system-level instruction block
- Payer-specific structure notes (injected dynamically)
- The exact JSON output schema
- Critical extraction rules that prevent the most common errors

PROMPT A-REFINED (UHC Drug-Specific — Multi-Product Variant):
Target doc: UHC Botulinum Toxins 2026D0017AN (28 pages, 5 products)
Key challenges:
- General Requirements apply to ALL 5 products — must be extracted as universalCriteria
- Each product section lists its OWN indications (Botox has chronic migraine; Dysport does NOT)
- "Unproven" section: explicit list of conditions NOT covered → coveredStatus: "unproven"
- Daxxify is EXCLUDED entirely → coveredStatus: "excluded"
- ICD-10 codes in separate matrix table (pages 4-10), not inline
- Step therapy: Myobloc for cervical dystonia requires prior Botox/Dysport/Xeomin trial
- Sort key must be {drugName}#{productName}#{indicationCode} because Botox#chronic_migraine
  is different from Dysport#chronic_migraine

Error to prevent: Conflating indications across products. The prompt MUST say:
"Extract ONLY indications listed under the specific product named in this text chunk.
Do not assume that because Botox covers chronic migraine, other products also cover it."

PROMPT C-REFINED (Cigna IP#### — 3-Phase with Dosing):
Target doc: Cigna Rituximab IP0319 (32 pages, 20+ indications)
Key challenges:
- THREE separate approval paths per indication: A (initial), B (1 course), C (2+ courses)
- Each phase has its OWN approval duration embedded in text: "Approve for 1 month if..."
- "Note:" blocks are clarification, NOT criteria — must be excluded from CriteriaItem arrays
- Dosing sub-sections are indication-specific (RA dosing ≠ vasculitis dosing)
- Preferred Product tables appear at end, referenced by "Preferred product criteria is met"
- Appendix A/B drug lists must be resolved inline

Error to prevent: Merging Phase A/B/C criteria into a single criteria array. The prompt MUST say:
"Phase A (Initial Therapy), Phase B (one prior course), Phase C (two or more prior courses)
are THREE SEPARATE extraction targets per indication. Each gets its own criteria array with
its own approvalPhase label and its own approvalDurationMonths value."

Error to prevent: Extracting "Note:" blocks as criteria. The prompt MUST say:
"Lines beginning with 'Note:' are contextual clarifications. Do NOT create a CriteriaItem
for them. You may incorporate their content into the criterionText of the preceding criterion."

PROMPT G (EmblemHealth/Prime Therapeutics — Universal + Specific + Footnotes):
Target doc: EmblemHealth Denosumab IC-0098 (16 pages)
Key challenges:
- Universal Criteria (calcium ≥1000mg, vitamin D ≥400IU, no hypocalcemia, no bisphosphonate combo)
  apply to ALL indications — extract as universalCriteria array, do NOT repeat per indication
- Product-group split: Prolia-type (Prolia, Bildyos, Jubbonti) vs Xgeva-type (Xgeva, Bilprevda, Wyost)
- Preferred products: Bildyos/Jubbonti preferred over Prolia; Bilprevda/Wyost preferred over Xgeva
- Step therapy has two sub-options: 6-month oral bisphosphonate OR 12-month IV zoledronic acid
- Footnote symbols have been pre-resolved inline by assemble_text.py:
  "response [DEFINED AS: fracture despite therapy, continued bone loss ≥5%, or inability to tolerate]"
  The extraction should treat the [DEFINED AS: ...] content as part of the criterion definition.
- Separate "Renewal Criteria" section → map to reauthorizationCriteria
- "Length of Authorization" table at top → initialAuthDurationMonths and maxAuthDurationMonths

PROMPT H (Florida Blue/MCG — Table Format):
Target doc: Florida Blue Bevacizumab 09-J0000-66 (15 pages)
Key challenges:
- Criteria are in Table 1 format: Indication | Criteria columns
- Each table row is ONE indication (10+ oncology indications)
- Inside each Criteria cell, nested AND/OR logic uses these exact markers:
  "BOTH of the following:" = AND (numbered 1, 2)
  "ONE of the following:" = OR (lettered a, b, c)
  "ALL of the following:" = AND
  "ANY of the following:" = OR
  Logic can nest 3 levels deep inside a single table cell
- Section I (Position Statement) has initiation criteria that apply to ALL indications:
  * Indication listed in Table 1 AND criteria met
  * Dose ≤ 10 mg/kg Q2W or ≤ 15 mg/kg Q3W
  * Biosimilar step therapy for non-preferred products
  → Extract Section I items as universalCriteria
- Section II = continuation criteria → reauthorizationCriteria
- Bevacizumab products: Mvasi and Zirabev are preferred; Avastin is non-preferred
- Line-of-business exceptions (HMO/PPO/POS) → capture in a note, don't create separate records

OUTPUT FORMAT for each prompt:
A Python string constant like:

PROMPT_A_UHC = """
You are extracting structured medical benefit drug policy criteria...
[full prompt text]
...
Return a valid JSON array. Return ONLY the JSON array.
"""

Include the complete JSON output schema inline in each prompt. The schema should match
the DrugPolicyCriteria DynamoDB table structure with the new fields:
- universalCriteria, approvalDurationMonths, approvalPhase, coveredStatus, productName,
  dosingPerIndication

Also generate:

PROMPT_B_FORMULARY (for Priority Health Type B):
- Input: 50 rows of table data (HCPCS | Drug Name | Description | Coverage Level | Notes)
- Output: JSON array of FormularyEntry records
- Must parse Notes column codes: PA, SOS, CC, CA:[HCPCS]([drug]), ICD-10:[codes]

PROMPT_F_PREFERRED_PRODUCT (refined for BCBS NC Type C):
- Input: Preferred product program document text
- Output: JSON array of PreferredProductRecord (per drug class)
- MUST NOT extract FDA Approved Use sections as clinical criteria (they are reference lists)
- Extract: preferred/non-preferred products, step therapy between tiers, documentation requirements

PROMPT_D_CLASSIFIER (refined document type classifier):
- Input: First 2 pages of any uploaded document
- Output: JSON with documentType (A/B/C/D/E), payerName, extractionPromptId, payerStructureNote
- Must detect all 6 hackathon payers + document type combinations

For each prompt, also provide a VALIDATION_CHECKLIST: a list of 5-8 specific things I should
verify in the extraction output to confirm the prompt is working correctly on that document.

Example validation check: "UHC Botulinum: Verify that Botox has chronic migraine as an
indication but Dysport does NOT. If both show chronic migraine, the multi-product isolation
is failing."
```

---

## PROMPT 3: Textract Output Assembly Refinement (assemble_text.py)

Use this prompt specifically for refining the Textract-to-structured-text assembly logic.

```text
I need to refine my Textract output assembly Lambda (assemble_text.py) for a medical policy
PDF extraction pipeline. This Lambda takes raw Textract JSON output and produces structured
text that gets sent to Bedrock for schema extraction.

CURRENT assemble_text.py CAPABILITIES:
- Reconstructs Textract blocks into hierarchical text (headers → bullets → nested conditions)
- Preserves TABLE/CELL block relationships for table reconstruction
- Outputs structured-text.json with a sections array
- Strips known boilerplate sections
- Splits by indication section for large documents

WHAT NEEDS TO BE ADDED/REFINED for the 6 hackathon documents:

1. FOOTNOTE RESOLUTION (EmblemHealth IC-0098):
   EmblemHealth uses symbols (†, ‡, Ф, ±, **, ¥, ◊) inline in criteria text that reference
   footnote definitions at section bottoms.

   Example input from Textract:
   "6-month trial of oral bisphosphonate with documented ineffective response†"
   ...later in document...
   "†Ineffective response is defined as: fracture despite therapy, continued bone loss
   (≥5% over 12 months), or inability to tolerate due to adverse effects"

   Required output:
   "6-month trial of oral bisphosphonate with documented ineffective response [DEFINED AS:
   fracture despite therapy, continued bone loss (≥5% over 12 months), or inability to
   tolerate due to adverse effects]"

   Implementation approach:
   - After Textract assembly, scan document text for footnote definition patterns
   - Build lookup: {"†": "Ineffective response...", "‡": "High risk for fractures...", ...}
   - Replace all inline symbol occurrences with "[DEFINED AS: {definition}]"
   - Handle edge cases: symbol at end of word vs standalone, multiple symbols per line

2. MULTI-PRODUCT SPLITTING (UHC 2026D0017AN — Botulinum Toxins):
   The document has one "General Requirements" section followed by 5 per-product sections.

   Required behavior:
   - Extract "General Requirements" section as a standalone chunk (shared context)
   - Split remaining text at product section headers matching pattern:
     "[Product]® ([generic]) is proven in the treatment of the following conditions:"
     or "[Product] is proven in the treatment of the following conditions:"
   - Produce 5 chunks, each prepended with the General Requirements text
   - Also extract the "Unproven" section as a separate chunk
   - Extract ICD-10 matrix table (pages 4-10) as a separate pre-pass chunk

   Product headers to detect:
   - "Botox® (onabotulinumtoxinA)"
   - "Dysport® (abobotulinumtoxinA)"
   - "Xeomin® (incobotulinumtoxinA)"
   - "Myobloc® (rimabotulinumtoxinB)"
   - "Daxxify® (daxibotulinumtoxinA-lanm)" — may appear in "Excluded" section

3. TABLE CRITERIA PARSING (Florida Blue 09-J0000-66):
   Florida Blue uses a table format: Indication | Criteria columns.
   Textract TABLES mode returns cell contents, but nested AND/OR logic inside Criteria cells
   may lose formatting.

   Required behavior:
   - After Textract table extraction, for each row in Table 1:
     * Column 1 = indicationName
     * Column 2 = criteria text with nested logic markers
   - Preserve the exact text markers: "BOTH of the following:", "ONE of the following:",
     "ALL of the following:", "ANY of the following:"
   - Maintain numbered (1, 2, 3) and lettered (a, b, c) item hierarchy
   - Output each row as a separate chunk: {indicationName, criteriaText}
   - Extract Section I (Position Statement) as a universal criteria chunk
   - Extract Section II (Continuation) as a reauthorization chunk

4. FORMULARY TABLE BATCHING (Priority Health — 205 pages):
   The entire document is a single large table.

   Required behavior:
   - Use Textract TABLES mode output
   - Extract all rows, preserving column alignment
   - Skip rows where HCPCS/CPT column is empty (therapeutic category headers)
   - Batch into 50-row chunks for Bedrock processing
   - Track therapeutic category context: when a category header row is encountered,
     store it and prepend it as metadata to subsequent drug rows until the next header
   - Output: list of chunks, each with {startRow, endRow, therapeuticCategory, rows[]}

5. BOILERPLATE STRIPPING (all payers):
   Add payer-specific section stripping based on section header detection.

   | Payer | Strip sections |
   |-------|---------------|
   | UHC   | "Instructions for Use" (last 2 pages), "Related Commercial Policies" sidebar |
   | Cigna | "INSTRUCTIONS FOR USE" (first 2-3 pages), "OVERVIEW", "Guidelines" |
   | EmblemHealth | Prime Therapeutics header, "This policy applies to..." preamble |
   | Florida Blue | "Description", MCG disclaimers, "Related Guidelines", "References" |
   | Priority Health | Header/footer rows (not drug data rows) |
   | BCBS NC | "Policy Summary" boilerplate, "Revision History" |

   Implementation: regex match on known section headers. When matched, skip all content
   until the next recognized non-stripped section header.

6. CIGNA INDICATION SPLITTING (Cigna IP0319 — 20+ indications):
   Split at numbered indication headers for parallel extraction.

   Pattern: r"^\d+\.\s+[A-Z][^.]+$" (e.g., "1. Rheumatoid Arthritis (RA)")
   - Each chunk = one indication with its A/B/C phases + dosing sub-section
   - Append Preferred Product tables as shared context to each chunk
   - Append "Conditions Not Covered" as a separate chunk

OUTPUT for each payer's pre-processing:
Return the standard State 3 output contract:
{
  "structuredTextS3Key": "{policyDocId}/structured-text.json",
  "pageCount": N,
  "sectionCount": N,
  "tableCount": N,
  "boilerplateStripped": true,
  "hasIndicationChunks": true,
  "chunkCount": N,
  "chunkMetadata": [
    {
      "chunkIndex": 0,
      "chunkType": "universal_criteria" | "per_product" | "per_indication" | "icd10_table" |
                   "unproven_list" | "continuation_criteria" | "formulary_batch" | "preferred_products",
      "productName": "Botox" | null,
      "indicationName": "Rheumatoid Arthritis" | null,
      "startRow": null | 0,
      "endRow": null | 49,
      "tokenEstimate": N
    }
  ]
}

Write the complete refactored assemble_text.py with all 6 payer pre-processing paths.
Use clean function decomposition: one function per payer's pre-processing logic, called
from a main handler that routes based on payerName from the Step Functions event.

Python 3.12. boto3 for S3 reads/writes. No external dependencies beyond standard library + boto3.
```

---

## Quick Reference: Which Prompt Handles Which Document

| Document | Classify (3.0) | Assemble (3) | Extract (4) |
|----------|---------------|-------------|-------------|
| UHC Botulinum | Type A, UHC | Multi-product split + General Requirements prepend + ICD-10 pre-pass | Prompt A-Refined (multi-product) |
| Cigna Rituximab | Type A, Cigna | Indication split + Preferred Products append | Prompt C-Refined (3-phase) |
| EmblemHealth Denosumab | Type A, EmblemHealth | Footnote resolution + product-group awareness | Prompt G (new) |
| Florida Blue Bevacizumab | Type A, Florida Blue | Table row extraction + Section I/II separation | Prompt H (new) |
| Priority Health MDL | Type B | 50-row table batching + category tracking | Prompt B-Formulary (new) |
| BCBS NC Preferred | Type C | Minimal — 26 pages fits in one chunk | Prompt F-Refined |

## Validation Checklist (Run After Each Document Extraction)

### UHC Botulinum
- [ ] Botox has chronic migraine; Dysport does NOT
- [ ] Myobloc lists cervical dystonia with step therapy requiring prior Botox/Dysport/Xeomin trial
- [ ] Daxxify has coveredStatus: "excluded"
- [ ] "General Requirements" appear as universalCriteria, not duplicated per indication
- [ ] drugIndicationId includes productName: "botulinum_toxin#Botox#chronic_migraine"
- [ ] Frequency cap "every 12 weeks" appears in universalCriteria or quantityLimits
- [ ] At least 3 conditions appear in "unproven" coveredStatus records

### Cigna Rituximab
- [ ] Rheumatoid Arthritis has 3 separate criteria arrays (phases A, B, C)
- [ ] Phase A approvalDurationMonths = 1 (for RA); Phases B/C = 12
- [ ] No CriteriaItem contains text starting with "Note:"
- [ ] Dosing for RA: "1000 mg IV on days 1 and 15" in dosingPerIndication
- [ ] At least 15 distinct indications extracted
- [ ] "Preferred product criteria is met" appears as a step_therapy criterion referencing the tables

### EmblemHealth Denosumab
- [ ] universalCriteria includes calcium ≥1000mg, vitamin D ≥400IU, no hypocalcemia, no bisphosphonates
- [ ] Prolia-type and Xgeva-type indications are separated with correct product groups
- [ ] Footnote symbols (†, ‡, Ф) do NOT appear in output — all resolved to definitions
- [ ] Preferred products: Bildyos/Jubbonti preferred over Prolia
- [ ] Renewal criteria exist as separate reauthorizationCriteria (simpler than initial)
- [ ] Step therapy includes "6-month oral bisphosphonate OR 12-month IV zoledronic acid"

### Florida Blue Bevacizumab
- [ ] At least 10 oncology indications extracted from Table 1
- [ ] Section I criteria appear as universalCriteria (dose cap, biosimilar step therapy)
- [ ] Mvasi and Zirabev listed as preferred; Avastin as non-preferred
- [ ] Nested AND/OR correctly captured: "BOTH of" = AND, "ONE of" = OR
- [ ] Section II continuation criteria in reauthorizationCriteria
- [ ] No "Description" section boilerplate in rawExcerpt

### Priority Health MDL
- [ ] FormularyEntry records, NOT DrugPolicyCriteria records
- [ ] Therapeutic category headers NOT extracted as drug rows
- [ ] PA, SOS, CA codes correctly parsed from Notes column
- [ ] ICD-10 bypass codes captured in paBypassIcd10Codes array
- [ ] Coverage levels correctly mapped to enum values

### BCBS NC Preferred Injectable
- [ ] 3 drug classes extracted: bevacizumab, rituximab, trastuzumab
- [ ] Preferred vs non-preferred products correctly categorized per class
- [ ] FDA Approved Use lists captured as reference ONLY, not as clinical criteria
- [ ] Step therapy criteria are product-tier-based (preferred → non-preferred)
- [ ] Documentation requirements captured
