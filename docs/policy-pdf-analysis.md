# PolicyDiff — Policy PDF Analysis Report
**Prepared for:** Hackathon Team (Atharva, Mohith, Om, Dominic)  
**Date:** April 2026  
**Purpose:** Comprehensive analysis of 15+ real insurance policy PDFs from UHC, Aetna, and Cigna to inform prompt engineering, schema design, and pre-processing pipeline architecture for PolicyDiff.  
**Cross-reference:** All recommendations reference the current spec at `policydiff-spec-nextjs.md` — specifically Section 7 (Database Schema), Section 8 (Feature Specifications), and Section 10 (Bedrock Prompts).

---

## Executive Summary

After reading 15+ real insurance policy PDFs and HTML documents across UHC, Aetna, and Cigna, five critical findings stand out:

1. **The current generic extraction prompt (Section 10.1) will fail on real documents.** It does not account for payer-specific structural patterns, cross-document dependencies, or the 3–4 level nesting of Cigna's AND/OR logic. Each payer needs its own extraction prompt.

2. **Aetna's primary medical drug policies are HTML, not PDF.** The entire architecture assumes PDF/Textract ingestion. Aetna Clinical Policy Bulletins (CPBs) live at `aetna.com/cpb/medical/data/` as HTML pages. An HTML ingestion path is required.

3. **ICD-10 codes are NEVER inline with clinical criteria.** In every payer's documents, ICD-10 codes live in a separate "Applicable Codes" or "Coding Information" section at the end of the document. The extraction prompt must know to look there, not in the criteria blocks.

4. **Authorization duration is encoded differently by every payer.** UHC: separate line. Cigna: embedded in criteria text. Aetna: preamble to criteria block. The schema is missing `initialAuthDurationMonths` — currently only `maxAuthDurationMonths` exists in `reauthorizationCriteria`.

5. **Preferred product rules require cross-document merging for Cigna.** Cigna's PA policy (IP####) and its Preferred Specialty Management document (PSM###) are separate files that must be combined for a complete picture. The pipeline does not currently support document linking.

---

## 1. Document Catalog & Classification

### 1.1 Complete Document Table

| # | Payer | Document Title | Policy Number | Effective Date | Document Type | Pages | PolicyDiff Relevance | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | UHC | Infliximab (Avsola, Inflectra, Remicade, Renflexis) | 2026D0004AR | 02/01/2026 | Drug-Specific Policy | 29 | **HIGH** | Gold standard doc; 10+ indications, all criteria inline |
| 2 | UHC | Maximum Dosage and Frequency | 2026D0034AT | 01/01/2026 | Administrative Policy | 34 | **MEDIUM** | Supplements drug policies with exact HCPCS unit limits |
| 3 | UHC | Self-Administered Medications | 2025D0073J | 2025 | Administrative Policy | 3 | **MEDIUM** | Maps to `benefitType` / `selfAdminAllowed` fields |
| 4 | UHC | Provider Administered Drugs — Site of Care | 2026D0121T | 2026 | Administrative Policy | 13 | **LOW-MEDIUM** | Site-of-care rules; affects where drugs can be administered |
| 5 | UHC | Medical Benefit Therapeutic Equivalent Excluded Drugs | 2025D0113D | 2025 | Preferred Product/Exclusion List | 3 | **MEDIUM** | Maps to `preferredProducts` field; preferred alternatives listed |
| 6 | Aetna | Medicare Part B Universal Criteria | 5606-A | 2024 | Prior Auth Framework | 7 | **MEDIUM** | Fallback criteria when no drug-specific CPB exists |
| 7 | Aetna | Advanced Control Plan Drug Guide (MAR2024) | MAR2024 | 03/01/2024 | Formulary/Drug List | 200+ | **LOW** | Pharmacy benefit; tier information, step therapy for pharmacy drugs |
| 8 | Aetna | 2025 Drug Guide — Standard Plan | 2025 | 2025 | Formulary/Drug List | ~150 | **LOW** | Pharmacy benefit formulary; not medical benefit |
| 9 | Aetna | Infliximab Clinical Policy Bulletin (CPB 0341) | 0341 | Current | Drug-Specific Policy (HTML) | N/A | **HIGH** | HTML page at aetna.com; per-indication criteria, prescriber mapping, dosing table |
| 10 | Cigna | Infliximab Coverage Policy (IP0660) | IP0660 | 03/15/2026 | Drug-Specific Policy | 22 | **HIGH** | Per-indication PA criteria; complex nested AND/OR logic |
| 11 | Cigna | Infliximab Preferred Specialty Management (PSM005) | PSM005 | Current | Preferred Product/Exclusion List | 3 | **HIGH** | Preferred vs. non-preferred product exception criteria; companion to IP0660 |
| 12 | Cigna | Abilify Mycite Coverage Position (IP0534) | IP0534 | Current | Drug-Specific Policy | 2 | **MEDIUM** | "Conditions Not Covered" only — demonstrates negative-coverage document type |
| 13 | Cigna | Formulary Exception Framework | CNF002 | Current | Prior Auth Framework | 2 | **LOW** | Exception handling framework; minimal clinical criteria |
| 14 | Cigna | Pharmacy Prior Authorization Policy | 1407 | Current | Prior Auth Framework | 8 | **LOW-MEDIUM** | General PA framework; revision history table example |
| 15 | Cigna | December 2025 Policy Updates Bulletin | N/A | 12/2025 | Policy Update Bulletin | 33 | **MEDIUM** | Change-tracking document; tables of updates across many policies |
| 16 | Cigna | National Preferred Formulary — Abridged | N/A | 2025 | Formulary/Drug List | Varies | **LOW** | Pharmacy benefit formulary list |
| 17 | Cigna | National Preferred Prescription 5-Tier — Abridged | N/A | 2025 | Formulary/Drug List | Varies | **LOW** | Pharmacy benefit tier structure |

### 1.2 Relevance Summary by Purpose

| Relevance | Count | Documents |
|---|---|---|
| **HIGH** — Has extractable drug-indication-criteria data for DrugPolicyCriteria schema | 4 | UHC Infliximab Policy, Aetna CPB 0341, Cigna IP0660, Cigna PSM005 |
| **MEDIUM** — Has dosing/preferred product/admin data that supplements drug policies | 7 | UHC Max Dosage, UHC Self-Admin, UHC Excluded Drugs, Aetna 5606-A, Cigna IP0534, Cigna Policy 1407, Cigna December Updates |
| **LOW** — Formulary lists or administrative boilerplate | 6 | Aetna Drug Guides (×2), Cigna CNF002, Cigna Formulary Lists (×2), UHC Site of Care |

### 1.3 Document Type Classification for the Pipeline

The pipeline must handle these distinct document types differently — the same extraction prompt cannot work across all of them:

| Document Type | Pipeline Treatment | Extraction Prompt |
|---|---|---|
| Drug-Specific Policy (PDF) | Textract → Payer-specific extraction prompt | Prompt A (UHC), Prompt C (Cigna) |
| Drug-Specific Policy (HTML) | HTML fetch → Prompt B (Aetna) | Prompt B |
| Preferred Specialty Management | Textract → PSM extraction | Prompt F |
| Maximum Dosage Policy | Textract → Supplementary dosing extraction | Prompt D |
| Policy Update Bulletin | Textract → Change extraction | Prompt E |
| Formulary/Drug List | Index only; do not extract clinical criteria | No extraction prompt needed |
| Prior Auth Framework | Index only; use as reference context | No extraction prompt needed |

---

## 2. Payer-Specific Document Structure Analysis

### 2.1 UHC Document Structure

**Template:** UHC drug-specific policies follow an extremely rigid, consistent template. Once you know the template, extraction is deterministic.

**Header block (always present, always first):**
```
UnitedHealthcare® Commercial Medical Benefit Drug Policy
Policy Number: YYYYD####XX
Effective Date: MONTH DD, YYYY
```

**Sidebar: "Related Commercial Policies"**  
Always present. Lists cross-referenced policies by title and policy number. This is where you discover that dosing data is in a separate document (e.g., "Maximum Dosage and Frequency, Policy 2026D0034AT"). The current spec's extraction prompt ignores this section entirely. **This is a critical gap.**

**Section order (invariant):**
1. **Coverage Rationale** — Preferred product requirements FIRST (before any indication criteria). Contains a table or bulleted list naming preferred biosimilars and their rank.
2. **Applicable Codes** — HCPCS codes and ICD-10 codes mapped to indications. ICD-10s are here, NOT inline with clinical criteria.
3. **Diagnosis-Specific Criteria** — One block per indication.
4. **Background**
5. **Benefit Considerations**
6. **Clinical Evidence**
7. **U.S. FDA** (labeling summary)
8. **CMS**
9. **References**
10. **Policy History/Revision Information** — A table with `Date` and `Summary of Changes` columns. This is the revision history.
11. **Instructions for Use** — Boilerplate footer (identical across all UHC policies).

**Per-indication block structure (exact pattern):**
```
[BOLD] Infliximab is proven for the treatment of [INDICATION].

Infliximab is medically necessary for the treatment of [INDICATION] when all of the following 
criteria is met:

For initial therapy, all of the following:
  • Prescriber requirement: Prescribed by or in consultation with a [SPECIALIST]
  • Diagnosis criteria (may have sub-bullets with specifics)
  • Step therapy: History of failure to [N] of the following [class of drugs]:
      o [Drug name 1]
      o [Drug name 2]
      o [Drug name 3]
  • Combination restriction: Patient is NOT receiving infliximab in combination with [drug list]
  • Dosing statement: Infliximab is dosed according to U.S. FDA labeled dosing for [indication]
    OR: Infliximab is dosed no higher than [X] mg/kg, administered every [N] weeks

For continuation of therapy, all of the following:
  • Patient demonstrated clinical response to initial therapy
  • Documentation requirement: [specific records required]
  • Initial authorization is for no more than [N] months
```

**Key UHC extraction rules:**
- The phrase "all of the following criteria is met" (grammatically incorrect "criteria is") signals the start of a criteria block
- "For initial therapy, all of the following:" = AND logic block for initial criteria
- "For continuation of therapy, all of the following:" = AND logic block for reauth criteria
- "One of the following:" = OR logic; "All of the following:" = AND logic at any nesting level
- "History of failure to [N] of the following" — the N matters (1 vs. 2 vs. 3 drugs that must fail)
- Authorization duration is a SEPARATE line at the end of continuation criteria: "Initial authorization is for no more than 12 months"
- Dosing language has two forms: (a) "dosed according to U.S. FDA labeled dosing" = no explicit limit; look in Max Dosage Policy. (b) Explicit: "dosed no higher than 5 mg/kg, administered every 8 weeks" — extract these numbers directly.
- Combination restrictions use the explicit phrase "Patient is NOT receiving infliximab in combination with" followed by a list — highly parseable.

**ICD-10 code mapping (Applicable Codes section):**
```
The following codes may be used to describe:
[INDICATION NAME]: [ICD-10-1], [ICD-10-2], [ICD-10-3]
```
This section comes BEFORE the Diagnosis-Specific Criteria section. The extraction prompt must make two passes: one to read ICD-10 mappings from Applicable Codes, then merge with the indication criteria blocks.

**Revision history (Policy History section):**
```
| Date | Summary of Changes |
|---|---|
| 01/01/2026 | Policy updated to include Avsola as preferred product |
| 02/01/2026 | Biosimilar trial duration increased from 12 to 14 weeks |
```
This is parseable with Prompt E and maps directly to `PolicyDiffs` records.

---

### 2.2 Aetna Document Structure

**Critical architectural note:** Aetna's primary clinical policy documents (CPBs) are HTML pages, not PDFs. The URL pattern is:
```
https://www.aetna.com/cpb/medical/data/300_399/0341.html  (infliximab CPB 0341)
```
The Textract pipeline does not apply here. A separate HTML ingestion path is required.

**CPB HTML page section order:**
1. **Scope of Policy** — Drug name, date last reviewed, drug class
2. **Prescriber Specialties** — A per-indication table or list mapping indication → required specialist type. Example:
   ```
   Crohn's disease: gastroenterologist or colorectal surgeon
   Rheumatoid arthritis: rheumatologist
   Psoriatic arthritis: rheumatologist or dermatologist
   ```
3. **Criteria for Initial Approval** — Numbered sections per indication:
   ```
   1. Rheumatoid Arthritis
   Aetna considers [drug] medically necessary for members with rheumatoid arthritis 
   when *all* of the following criteria are met:
     a. Diagnosis confirmed by a rheumatologist
     b. Inadequate response to *either* of the following:
        i.  3-month trial of methotrexate at maximum titrated dose of at least 15 mg/week
        ii. [alternative drug]
     c. [additional criterion]
   Authorization of 12 months may be granted for initial approval.
   ```
4. **Continuation of Therapy** — A SEPARATE section (not embedded in each indication block like UHC). Single section covering all indications with general response documentation requirements.
5. **Dosing** — An explicit TABLE:
   ```
   | Indication | Dose |
   |---|---|
   | Rheumatoid arthritis | 3 mg/kg IV at weeks 0, 2, 6, then every 8 weeks |
   | Crohn's disease | 5 mg/kg IV at weeks 0, 2, 6, then every 8 weeks |
   ```
6. **Experimental, Investigational, or Unproven** — Lists covered indications that have been specifically excluded from coverage.
7. **Coding** — ICD-10 and HCPCS codes in tables.
8. **Background** — Clinical narrative, drug mechanism.

**Aetna AND/OR logic markers (unique to Aetna):**
- Uses *italic* emphasis in HTML: `*all* of the following`, `*any* of the following`, `*either* of the following`
- "either" means OR between exactly 2 choices
- "any" means OR among 3+ choices
- "all" means AND
- These italic markers are critical for correctly parsing logic structure

**Aetna step therapy specifics:**
Aetna is highly specific about prior therapy requirements, specifying dose and duration simultaneously:
- "3-month trial of methotrexate at maximum titrated dose of at least 15 mg per week"
- "6-week trial of a corticosteroid at prednisone equivalent ≥ 10 mg/day"
The `trialDurationWeeks` field is rarely enough — a `trialDoseMg` subfield may be needed.

**Aetna Medicare Part B document (5606-A):**
This is a simpler document format — a single-page universal criteria framework that applies when no drug-specific CPB exists. It references evidence compendia rather than specific step therapy. For demo purposes, this is fallback-only context, not primary extraction target.

**Aetna pharmacy drug guides (LOW relevance):**
The 200+ page pharmacy guides (MAR2024, 2025-Drug-guide) are formulary lists for pharmacy benefit only. They contain tier information, step therapy for pharmacy benefit, and prior auth flags — but these are pharmacy benefit data, not medical benefit drug policy. Do not send to the medical benefit extraction prompt. If ingested, tag `benefitType: "pharmacy"` and do not populate `initialAuthCriteria`.

---

### 2.3 Cigna Document Structure

Cigna policies split into two distinct document types that must be handled separately.

#### Type 1: Prior Authorization Policy (IP#### format)

**Header block:**
```
Drug Coverage Policy
Coverage Policy Number: IP0660
Effective Date: March 15, 2026
Policy Title: Infliximab Products [REMICADE, INFLECTRA, AVSOLA, RENFLEXIS, IXIFI]
```

**Section order:**
1. **INSTRUCTIONS FOR USE** — Boilerplate (first ~half page, 100% identical across ALL Cigna policies). **Strip before extraction.** Begins: "This Coverage Policy addresses coverage determinations for all lines of Cigna business when a medical claim is submitted..."
2. **OVERVIEW** — FDA-approved indications listed as a bulleted list. Also lists biosimilar products. Good for `brandNames` extraction.
3. **Guidelines** — Professional society recommendations (ACR, ACG, AAD, NCCN, etc.) cited as text. Provides clinical context but rarely maps directly to schema fields.
4. **Coverage Policy** — The actual criteria. Numbered by indication. This is the core extraction target.
5. **Coding Information** — HCPCS J-codes and ICD-10 codes. ICD-10s are in a table.
6. **References** — Numbered list of citations.
7. **Revision Details** — Table: `Type of Revision | Summary of Changes | Date`

**Coverage Policy section structure — exact nested logic pattern:**
```
1. Rheumatoid Arthritis. Approve for the duration noted if the patient meets ONE of the 
   following (A or B):

   A) Initial Therapy. Approve for 6 months if the patient meets BOTH of the following 
      (i and ii):
      i. The patient has a confirmed diagnosis of moderate-to-severe rheumatoid arthritis; 
         AND
      ii. The medication is prescribed by or in consultation with a rheumatologist; AND
      iii. The patient has demonstrated an inadequate response, intolerance, or contraindication 
           to ONE of the following (a, b, or c):
           a. Methotrexate (minimum 3-month trial at therapeutic dose)
           b. Leflunomide (minimum 3-month trial at therapeutic dose)
           c. Sulfasalazine (minimum 3-month trial at therapeutic dose)

   B) Patient is Currently Receiving. Approve for 12 months if the patient meets ALL of 
      the following (i and ii):
      i. The patient has been established on infliximab with documented clinical response; AND
      ii. [documentation requirement]
```

**Critical nesting observations:**
- Top level: "ONE of the following (A or B)" — this is OR
- A-level: "BOTH of the following (i and ii)" — this is AND inside an OR branch
- iii-level: "ONE of the following (a, b, or c)" — this is OR inside AND inside OR
- Authorization duration is EMBEDDED in the criteria text: "Approve for 6 months if..." (Initial) vs. "Approve for 12 months if..." (Continuation)
- The current schema has `maxAuthDurationMonths` in `reauthorizationCriteria` only — it's missing from `initialAuthCriteria`

**Approval duration encoding:**
Unlike UHC (separate line) and Aetna (preamble sentence), Cigna bakes the duration INTO the criteria phrase: "Approve for 6 months if the patient meets BOTH..." The extraction prompt must parse the number before extracting the criteria.

**Cigna step therapy specifics:**
- Lists specific drug names with minimum trial duration
- Sometimes lists a drug class ("conventional DMARD") and sometimes specific drugs
- "inadequate response, intolerance, or contraindication" — three acceptable reasons for prior drug failure. The extraction should capture all three in `stepTherapyLogic`

#### Type 2: Preferred Specialty Management (PSM### format)

**Header block:**
```
Drug Coverage Policy
Coverage Policy Number: PSM005
Effective Date: [Date]
Policy Title: Infliximab Preferred Specialty Management
```

**Structure:**
1. **INSTRUCTIONS FOR USE** — Same boilerplate as IP documents. Strip.
2. **POLICY STATEMENT** — Defines preferred and non-preferred products:
   ```
   Preferred products: Inflectra (infliximab-dyyb), Avsola (infliximab-axxq), Renflexis (infliximab-abda)
   Non-preferred products: Remicade (infliximab)
   ```
3. **NON-PREFERRED PRODUCT EXCEPTION CRITERIA** — Table format:
   ```
   | Non-Preferred Products | Exception Criteria |
   |---|---|
   | Remicade | Approve if the patient meets BOTH of the following (A and B):
   |           | A. 14-week trial of preferred product (Inflectra, Avsola, or Renflexis) with 
   |           |    documented inadequate response, intolerance, or hypersensitivity reaction; AND
   |           | B. Physician attestation of medical necessity for brand-specific product |
   ```

This document MUST be merged with IP0660 for a complete Cigna infliximab policy picture. The `preferredProducts` field in the DynamoDB schema should be populated primarily from the PSM document, not the IP document.

---

## 3. Schema Mapping: Real Documents → DrugPolicyCriteria

For each field in the `DrugPolicyCriteria` DynamoDB schema, this section documents where it lives in each payer's document, extraction difficulty (1=trivial, 5=very hard), and whether the current Section 10.1 prompt handles it correctly.

### 3.1 Field-by-Field Mapping Table

| Schema Field | UHC Location | Aetna Location | Cigna Location | Difficulty (1–5) | Current Prompt Handles? |
|---|---|---|---|---|---|
| `drugName` | Policy title + header | CPB title | IP document title | **1** | Yes — but normalize to generic name |
| `brandNames` | Coverage Rationale "Preferred Product" section | CPB title and Background | OVERVIEW section | **1** | Yes |
| `indicationName` | Bold statement: "Infliximab is proven for..." | Numbered section headers | Numbered section headers | **2** | Partially — UHC phrasing is unique |
| `indicationICD10` | **Applicable Codes section** (NOT inline) | **Coding section** (NOT inline) | **Coding Information section** (NOT inline) | **3** | **NO — current prompt assumes inline** |
| `preferredProducts` | Coverage Rationale → Preferred Product section | CPB has step therapy through biologics, not a ranking hierarchy | **PSM### document** (separate file) | **2** | Partially for UHC; fails for Cigna |
| `initialAuthCriteria` | "For initial therapy, all of the following:" block | "Criteria for Initial Approval" numbered sections | "A) Initial Therapy" branch of numbered sections | **4** | Partially — misses nesting |
| `reauthorizationCriteria` | "For continuation of therapy, all of the following:" block | Separate "Continuation of Therapy" section | "B) Patient is Currently Receiving" branch | **3** | Partially |
| `dosingLimits` | Often "per FDA labeled dosing" (implicit) or explicit mg/kg statement; ALSO: separate Max Dosage Policy | **Explicit dosing TABLE** in CPB | "dosage, frequency, duration should be reasonable" (vague) | **3** | Partially — misses cross-doc dependencies |
| `combinationRestrictions` | Explicit: "Patient is NOT receiving infliximab in combination with [list]" | Embedded in criteria or Background | Embedded in criteria | **2** | Yes for UHC; fragile for others |
| `quantityLimits` | Often not explicit; UHC Max Dosage Policy has HCPCS unit limits | Dosing table implies limits | Not usually explicit | **3** | No — not in drug-specific policy |
| `benefitType` | "obtained under the pharmacy benefit" for self-admin subcutaneous; otherwise medical | CPB = medical; Drug Guide = pharmacy | IP = medical; Formulary = pharmacy | **2** | Yes — document type is a strong signal |
| `selfAdminAllowed` | Separate Self-Administered Medications policy | Not usually in CPB | Not usually in IP | **2** | No — not in drug-specific policy |
| `confidence` | N/A — LLM-generated | N/A | N/A | N/A | Yes |
| `rawExcerpt` | Any text passage | Any text passage | Any text passage | **1** | Yes |

### 3.2 Critical Field-Level Findings

#### `indicationICD10` — Most Commonly Mishandled
**Finding:** ICD-10 codes are NEVER embedded in the clinical criteria text in any of the three payers' documents. They are always in a separate section (UHC: "Applicable Codes", Aetna: "Coding", Cigna: "Coding Information") that maps indication names to ICD-10 ranges.

**What this means for extraction:** The prompt cannot extract ICD-10 while parsing criteria blocks. It needs a two-pass approach:
1. Pass 1: Parse the Applicable Codes/Coding section → build a `{indicationName: [icd10codes]}` lookup map
2. Pass 2: Parse criteria blocks → merge ICD-10 codes from the lookup map

The current prompt instruction "4. indicationICD10: ICD-10 code if stated" will produce `null` for nearly every record because the code is not stated inline.

**Example from UHC infliximab policy (Applicable Codes section):**
```
Ankylosing Spondylitis / Radiographic Axial Spondyloarthritis: M45.0, M45.1, M45.2, M45.9
Crohn's Disease: K50.00, K50.011, K50.012, K50.013, K50.014, K50.018, K50.019
Plaque Psoriasis: L40.0
Psoriatic Arthritis: L40.50, L40.51, L40.52, L40.53, L40.54, L40.59
Rheumatoid Arthritis: M05.00–M05.09, M05.10–M05.19, M05.20–M05.29, M05.711–M05.79, M06.00–M06.09
```

#### `initialAuthCriteria` — Core Extraction Challenge
The field structure in the spec is a flat array of criterion objects. Real documents have a TREE structure. Cigna's 3-level nesting (OR → AND → OR) cannot be represented as a flat array without losing the logical relationships.

**Current spec's flat structure:**
```json
[
  { "criterionText": "...", "criterionType": "step_therapy", ... },
  { "criterionText": "...", "criterionType": "prescriber_requirement", ... }
]
```

**What Cigna actually has:**
```
ONE of (A or B):
  A: BOTH of (i and ii and iii):
       i: diagnosis criterion
      ii: prescriber criterion
     iii: ONE of (a, b, or c):
            a: drug failure criterion
            b: drug failure criterion  
            c: drug failure criterion
  B: ALL of (i and ii):
       i: continuation criterion
      ii: documentation criterion
```

This tree structure cannot be losslessly flattened. See Section 6 for schema change recommendations.

#### `preferredProducts` — Cross-Document Dependency
For Cigna: `preferredProducts` data lives in PSM005, not IP0660. If only IP0660 is ingested, `preferredProducts` will be empty. The system needs a concept of "linked documents" that are merged before or during extraction.

For UHC: `preferredProducts` is in the Coverage Rationale section of the same document — this works fine.

For Aetna: CPBs do not use a product ranking hierarchy. Instead, they specify step therapy through specific biologic alternatives. There is no "preferred rank 1/rank 2" concept. Map Aetna step therapy biologics to `preferredProducts` with equal rank where applicable, but document this difference.

#### `dosingLimits` — Split Between Documents
UHC infliximab policy says: "Infliximab is dosed according to U.S. FDA labeled dosing for plaque psoriasis." This is NOT a dosing limit — it means "no special limit beyond FDA label." However, the separate Maximum Dosage and Frequency policy (2026D0034AT) contains HCPCS-level unit limits like:
```
J1745 (infliximab, 10 mg): maximum 100 units per claim for Crohn's disease
```

Aetna provides an EXPLICIT DOSING TABLE in the CPB:
```
| Indication                      | Dose                                           |
|---|---|
| Rheumatoid arthritis            | 3 mg/kg IV at 0, 2, 6 weeks, then every 8 wk  |
| Adult Crohn's disease           | 5 mg/kg IV at 0, 2, 6 weeks, then every 8 wk  |
| Pediatric Crohn's disease (≥6y) | 5 mg/kg IV at 0, 2, 6 weeks, then every 8 wk  |
| Plaque psoriasis                | 5 mg/kg IV at 0, 2, 6 weeks, then every 8 wk  |
```

Cigna says: "dosage, frequency, duration should be reasonable and clinically appropriate" — essentially no dosing limit, deferring to clinical judgment.

---

## 4. Critical Parsing Challenges & Failure Modes

### Challenge 1: Cross-Document Dependencies (UHC)
**Severity:** HIGH — Affects dosing data for all UHC drug policies

**Problem:** The UHC infliximab policy (2026D0004AR) references dosing as "dosed according to U.S. FDA labeled dosing." The actual unit-level dosing limits are in the separate Maximum Dosage and Frequency policy (2026D0034AT). The current pipeline has no mechanism to:
1. Detect that a cross-document reference exists
2. Look up the referenced document
3. Merge its data into the primary extraction record

**Specific example:**
- Drug-specific policy says: "Infliximab is dosed according to U.S. FDA labeled dosing for Crohn's disease"
- Maximum Dosage policy (34 pages) contains a table row: `J1745 | Crohn's disease | 100 units per claim`
- Without cross-reference, `dosingLimits` and `quantityLimits` will both be `null` for UHC infliximab

**Root cause in current prompt:** "If a criterion references another policy document, note this in criterionText but do not follow the reference." This instruction CORRECTLY avoids hallucination but means important data is lost.

**Recommendation:** Build a supplementary extraction step (Prompt D) specifically for the Maximum Dosage policy. After extracting the main drug policy, run Prompt D against the Max Dosage policy, then merge by `drugName` + `indicationName` + HCPCS code. This merge happens in State 3 or 4 of the Step Functions workflow.

---

### Challenge 2: Nested AND/OR Logic Depth (Cigna)
**Severity:** HIGH — Affects all Cigna drug-specific policies

**Problem:** Cigna IP0660 has 3–4 levels of nested AND/OR logic. The current prompt's instruction — "All of the following = AND, One of the following = OR" — correctly identifies the logic operators but does not handle the tree structure. Flattening the tree into a list loses the relationships.

**Example from Cigna rheumatoid arthritis criteria:**
```
1. Rheumatoid Arthritis. Approve for the duration noted if the patient meets ONE of the 
   following (A or B):
   
   A) Initial Therapy. Approve for 6 months if the patient meets BOTH of the following (i, ii, iii):
      i.   Patient age > 18 years; AND
      ii.  Medication prescribed by a rheumatologist; AND
      iii. Patient has inadequate response to ONE of the following (a, b, or c):
           a. Methotrexate (≥3 months, therapeutic dose)
           b. Leflunomide (≥3 months, therapeutic dose)
           c. Sulfasalazine (≥3 months, therapeutic dose)

   B) Patient is Currently Receiving. Approve for 12 months if BOTH (i and ii):
      i.  Established on infliximab with documented response
      ii. Physician attestation of ongoing need
```

**What the current flat schema represents:**
```json
[
  { "criterionText": "Patient age > 18 years", "criterionType": "age" },
  { "criterionText": "Prescribed by rheumatologist", "criterionType": "prescriber_requirement" },
  { "criterionText": "Failed methotrexate, leflunomide, or sulfasalazine", "criterionType": "step_therapy" }
]
```

**What was lost:** The fact that (i AND ii AND iii) is only required IF branch A applies, and branch B is an entirely separate path. The flat list implies ALL criteria must be met simultaneously, which is incorrect — branch B patients (continuation) meet different criteria.

**Recommendation:** See Section 6 for the proposed tree-structure schema change. The extraction prompt must output a tree, not a list.

---

### Challenge 3: Aetna's HTML vs. PDF Format
**Severity:** HIGH — Affects all Aetna primary clinical policies

**Problem:** Aetna Clinical Policy Bulletins (CPBs) are HTML pages hosted at `aetna.com/cpb/medical/data/`. The system architecture assumes PDF input via Textract. Textract cannot process HTML URLs.

**Specific URL pattern:**
```
https://www.aetna.com/cpb/medical/data/300_399/0341.html   (CPB 0341 — infliximab)
https://www.aetna.com/cpb/medical/data/400_499/0404.html   (CPB 0404 — adalimumab)
https://www.aetna.com/cpb/medical/data/500_599/0572.html   (CPB 0572 — ustekinumab)
```

**Two viable approaches:**
1. **HTML fetch + direct Bedrock input:** Fetch the HTML page, strip HTML tags, and send the text directly to Bedrock (bypassing Textract). This works because Aetna CPBs have clean, well-structured HTML — Textract adds no value over raw HTML parsing.
2. **Headless browser PDF rendering:** Use a headless Chrome/Puppeteer instance to render the page to PDF, then process via Textract. More complex, but keeps a unified pipeline.

**Recommendation:** Approach 1 (HTML fetch) is faster for the hackathon. Add a field to `PolicyDocuments`: `documentFormat: "pdf" | "html"`. The ingestion Lambda checks this flag and routes to the appropriate ingestion path before Step Functions State 1 (StartTextractJob).

---

### Challenge 4: Preferred Product Rules in a Separate Document (Cigna)
**Severity:** MEDIUM — Affects Cigna biosimilar coverage data completeness

**Problem:** Cigna's `preferredProducts` data lives in PSM005 (Preferred Specialty Management), not in IP0660 (the PA criteria policy). A complete Cigna infliximab picture requires BOTH documents. The current upload workflow is designed for single-document upload with no concept of document linking.

**What PSM005 contains that IP0660 lacks:**
- Explicit "Preferred" vs. "Non-Preferred" product designation (Inflectra, Avsola, Renflexis = preferred; Remicade = non-preferred)
- The 14-week trial duration for the preferred product before accessing the non-preferred product
- Physician attestation requirement for the non-preferred product

**What IP0660 contains that PSM005 lacks:**
- All indication-specific clinical criteria
- Step therapy requirements within indications
- Prescriber requirements
- Authorization durations

**Recommendation:** Add a `linkedDocuments` field to `PolicyDocuments`. Support uploading PSM as a companion document. During extraction, if a drug policy has a linked PSM document, run Prompt F on the PSM and merge `preferredProducts` into the main `DrugPolicyCriteria` record.

---

### Challenge 5: Authorization Duration Encoding Inconsistency
**Severity:** MEDIUM — Affects `maxAuthDurationMonths` field accuracy

**Problem:** All three payers encode initial authorization duration differently, and the current schema has the field in the wrong place.

| Payer | Initial Auth Duration Location | Example |
|---|---|---|
| UHC | Separate line at end of continuation criteria | "Initial authorization is for no more than 12 months" |
| Cigna | EMBEDDED in criteria approval statement | "Approve for **6 months** if the patient meets BOTH..." |
| Aetna | PREAMBLE before criteria list | "Authorization of **12 months** may be granted for..." |

**Schema gap:** The current `DrugPolicyCriteria` schema has `maxAuthDurationMonths` inside `reauthorizationCriteria`. But:
- Initial auth duration ≠ reauth duration in many cases (Cigna: 6 months initial, 12 months continuation)
- The current schema cannot store separate initial vs. reauth durations
- The current extraction prompt (10.1) does not mention extracting auth duration at all for initial criteria

**Recommendation:** Add `initialAuthDurationMonths: number` as a top-level field in `DrugPolicyCriteria` (parallel to `reauthorizationCriteria.maxAuthDurationMonths`). Update all extraction prompts to explicitly extract both values.

---

### Challenge 6: Policy Change Tracking — Different Document Format
**Severity:** MEDIUM — Affects temporal diff quality for Cigna

**Problem:** Cigna's December 2025 Policy Updates bulletin is a 33-page TABLE-format document listing changes across hundreds of policies in a month. This is a completely different document type than a clinical criteria document.

**Cigna update bulletin table format:**
```
| Coverage Policy Number | Policy Title | Summary of Changes | Effective Date |
|---|---|---|---|
| IP0660 | Infliximab Products | Step therapy biosimilar trial duration increased from 12 to 14 weeks | 03/15/2026 |
| IP0534 | Abilify MyCite | Removed coverage for off-label use in treatment-resistant depression | 03/01/2026 |
```

**UHC revision history table format (end of each policy):**
```
| Date | Summary of Changes |
|---|---|
| 01/01/2026 | Policy reformatted. Preferred product section moved to beginning. |
| 02/01/2026 | Criteria updated: Avsola and Inflectra now required first-line for all indications. |
```

The current extraction prompt (10.1) would attempt to extract `DrugPolicyCriteria` records from a Cigna update bulletin — but there are no criteria in this document, only change summaries. This would produce empty or erroneous output.

**Recommendation:** Build Prompt E specifically for change bulletin documents. It outputs `PolicyDiffs` records directly, without going through `DrugPolicyCriteria`. Document type classification (see Section 7) must identify these documents before routing to the extraction prompt.

---

### Challenge 7: Negative Coverage — "Conditions Not Covered" Documents
**Severity:** MEDIUM — Affects completeness of coverage mapping

**Problem:** Cigna IP0534 (Abilify Mycite) has ONLY negative criteria — a list of conditions that are NOT covered. It has no positive clinical criteria at all. The current extraction prompt would either return an empty array (no criteria found) or hallucinate criteria.

**Cigna IP0534 structure:**
```
Coverage Policy
Cigna does not cover [drug] as medically necessary for any indication because it is 
considered experimental, investigational, or unproven for all uses including:
  • Depression
  • Bipolar disorder
  • Treatment-resistant schizophrenia
  [etc.]
```

**Why this matters:** Consultants need to know when a drug is categorically excluded, not just when it has no policy. An empty `DrugPolicyCriteria` array can mean either "no policy found" or "all uses excluded" — these are very different clinical situations.

**Aetna also has this:** CPBs include an "Experimental, Investigational, or Unproven" section listing excluded conditions even for drugs that ARE covered for other indications.

**Recommendation:** Add `coveredStatus: "covered" | "excluded" | "experimental"` field to `DrugPolicyCriteria`. When `coveredStatus = "excluded"`, `initialAuthCriteria` should be empty and the exclusion reason should be captured in a new `exclusionReason` field.

---

### Challenge 8: The Boilerplate Problem
**Severity:** LOW-MEDIUM — Wastes tokens, can confuse extraction

**Problem:** Every Cigna document begins with an identical ~500-word "INSTRUCTIONS FOR USE" boilerplate. Every UHC document ends with a similar boilerplate. These waste Bedrock input tokens (Cigna's boilerplate is ~15% of a short 3-page document) and can cause the model to extract false positive criteria from the boilerplate text.

**Cigna boilerplate begins:**
```
INSTRUCTIONS FOR USE
This Coverage Policy addresses coverage determinations for all lines of Cigna business 
when a medical claim is submitted. Except for Medicare Advantage coverage determinations, 
Cigna companies follow the coverage standards applicable to their plan types...
```

**UHC boilerplate begins:**
```
Instructions for Use
This Medical Benefit Drug Policy applies to plans administered by UnitedHealthcare...
```

**Recommendation:** Pre-strip boilerplate before sending to Bedrock. Create payer-specific boilerplate signatures:
- Cigna: strip everything from beginning of document to the first occurrence of "OVERVIEW" or "Coverage Policy"
- UHC: strip everything from "Instructions for Use" to end of document

These are constant strings that can be detected with simple string matching.

---

## 5. Optimized Extraction Prompts

These prompts replace the single generic prompt in Section 10.1 of the spec. Each is tailored to one payer's document structure. They share the same output JSON format as the current prompt but contain payer-specific guidance.

**When to use each prompt:**

| Payer | Document Type | Prompt |
|---|---|---|
| UHC | Drug-specific medical benefit policy | **Prompt A** |
| Aetna | Clinical Policy Bulletin (CPB) HTML | **Prompt B** |
| Cigna | Coverage Policy (IP####) | **Prompt C** |
| UHC | Maximum Dosage and Frequency policy | **Prompt D** |
| UHC or Cigna | Revision history / policy update bulletin | **Prompt E** |
| Cigna | Preferred Specialty Management (PSM###) | **Prompt F** |

---

### Prompt A: UHC Drug-Specific Policy Extraction

```
You are extracting structured medical benefit drug policy criteria from a UnitedHealthcare 
Commercial Medical Benefit Drug Policy document. Your output feeds a clinical decision 
support system — accuracy is critical.

Document metadata:
- Payer: UnitedHealthcare
- Policy Number: {policyNumber}
- Document Title: {documentTitle}
- Effective Date: {effectiveDate}

DOCUMENT STRUCTURE — UHC policies follow this EXACT template. Use section names to navigate:

STEP 1 — BEFORE parsing clinical criteria, extract the ICD-10 mapping from the 
"Applicable Codes" section. This section appears BEFORE the Diagnosis-Specific Criteria 
section in the document. It contains statements like:
  "[Indication Name]: [ICD-10-1], [ICD-10-2], [ICD-10-3]"
Build a lookup map: { indicationName: [icd10codes] }.

STEP 2 — Extract preferred product information from the "Coverage Rationale" section, 
which comes BEFORE the Diagnosis-Specific Criteria. It contains a "Preferred Product" 
subsection listing biosimilars in preference order (rank 1 = most preferred).

STEP 3 — Parse the "Diagnosis-Specific Criteria" section. For each indication:

  INDICATION DETECTION: A new indication block begins with a bold statement matching the 
  pattern: "Infliximab is proven for the treatment of [INDICATION]."
  
  INITIAL CRITERIA: The block "For initial therapy, all of the following:" contains AND logic.
  Every bullet point under this block is a REQUIRED criterion (AND).
  
  CONTINUATION CRITERIA: The block "For continuation of therapy, all of the following:" 
  contains reauthorization criteria.
  
  LOGIC MARKERS:
  - "all of the following" = AND (every item must be met)
  - "one of the following" = OR (any one is sufficient)  
  - "History of failure to [N] of the following" = step therapy; N is the minimum number 
    of drugs that must have been tried. Extract N as the count.
  - Sub-bullets marked with "o" are alternatives within an OR block.
  
  AUTHORIZATION DURATION: Look for the phrase "Initial authorization is for no more than 
  [N] months" in the continuation criteria block. Extract N as initialAuthDurationMonths.
  
  PRESCRIBER: Look for "Prescribed by or in consultation with a [SPECIALIST TYPE]".
  
  DOSING:
  - If the text says "dosed according to U.S. FDA labeled dosing" — set dosingLimits to null 
    and note in rawExcerpt that dosing is per FDA label (see Max Dosage Policy).
  - If text specifies explicit mg/kg limits, extract them: maxDoseMgPerKg, maxFrequency.
  
  COMBINATION RESTRICTIONS: Look for "Patient is NOT receiving [drugName] in combination with" 
  followed by a list. Extract each listed drug as a combinationRestrictions entry.

STEP 4 — For each indication, merge the ICD-10 codes from Step 1 using the indication name 
as the key. If no match is found, set indicationICD10 to null.

BOILERPLATE: Ignore the "Instructions for Use" section at the end of the document. It is 
administrative boilerplate and contains no clinical criteria.

CROSS-REFERENCES: If the criteria text references another UHC policy (e.g., "see Maximum 
Dosage and Frequency Policy"), note this in criterionText but do not invent values for the 
referenced data.

OUTPUT FORMAT:
Return a valid JSON array where each element is a DrugPolicyCriteriaRecord:
{
  "drugName": string,                    // normalized generic name, lowercase
  "brandNames": [string],               // all brand names listed in document
  "indicationName": string,             // exact indication as written in the policy
  "indicationICD10": [string] | null,   // from Applicable Codes section
  "payerName": "UnitedHealthcare",
  "effectiveDate": string,              // ISO format: "YYYY-MM-DD"
  "policyNumber": string,
  "preferredProducts": [               // from Coverage Rationale section
    { "productName": string, "rank": number }
  ],
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | 
                       "dosing" | "combination_restriction" | "age" | "severity",
      "logicOperator": "AND" | "OR",    // how this criterion relates to sibling criteria
      "requiredDrugsTriedFirst": [string],  // only for step_therapy
      "stepTherapyMinCount": number,        // minimum number of drugs that must fail (N in "N of the following")
      "trialDurationWeeks": number | null,
      "prescriberType": string | null,
      "requiresDocumentation": string | null,
      "rawExcerpt": string              // exact quote from document
    }
  ],
  "reauthorizationCriteria": [
    {
      // same structure as initialAuthCriteria, plus:
      "maxAuthDurationMonths": number | null,
      "requiresDocumentation": string | null
    }
  ],
  "dosingLimits": {
    "maxDoseMg": number | null,
    "maxFrequency": string | null,       // e.g., "every 8 weeks"
    "weightBased": boolean,
    "maxDoseMgPerKg": number | null,
    "perFDALabel": boolean              // true if policy defers to FDA labeled dosing
  } | null,
  "combinationRestrictions": [
    { "restrictedWith": string, "restrictionType": "same_class" | "same_indication" | "absolute" }
  ],
  "quantityLimits": null,              // not in drug-specific policy; populated from Max Dosage Policy
  "benefitType": "medical",
  "selfAdminAllowed": null,            // not in drug-specific policy; see Self-Admin policy
  "coveredStatus": "covered" | "excluded" | "experimental",
  "confidence": number                 // 0.0-1.0; rate below 0.7 for complex nested logic
}

CRITICAL RULES:
- Each indication block is INDEPENDENT. Never merge criteria across indications.
- Preserve exact drug names from the document for requiredDrugsTriedFirst (e.g., "Inflectra" 
  not just "infliximab biosimilar").
- If a criterion says "History of failure to 1 of the following [list]", set 
  stepTherapyMinCount to 1 (not the count of drugs listed).
- For continuation criteria, if auth duration is stated, set maxAuthDurationMonths.
- Set confidence below 0.7 if: criteria text is ambiguous, contains cross-references to 
  other policies, or has complex conditional structures you cannot fully resolve.
- Do NOT invent values. Omit fields that are not stated in the document.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}
```

---

### Prompt B: Aetna CPB Extraction

```
You are extracting structured medical benefit drug policy criteria from an Aetna Clinical 
Policy Bulletin (CPB) web page. Your output feeds a clinical decision support system.

Document metadata:
- Payer: Aetna
- CPB Number: {cpbNumber}
- Document Title: {documentTitle}
- URL: {documentUrl}
- Date Last Reviewed: {reviewDate}

DOCUMENT STRUCTURE — Aetna CPBs follow this template. Navigate by section name:

STEP 1 — Extract prescriber requirements from the "Prescriber Specialties" section.
This section contains per-indication specialist mappings, e.g.:
  "Crohn's disease: gastroenterologist or colorectal surgeon"
  "Rheumatoid arthritis: rheumatologist"
Build a lookup: { indicationName: prescriberType }

STEP 2 — Extract initial criteria from "Criteria for Initial Approval" section.
Organized as numbered sections by indication.

  INDICATION DETECTION: "1. [Indication Name]" marks the beginning of each indication block.
  
  LOGIC MARKERS (use HTML italic rendering as signals):
  - "*all* of the following" → AND
  - "*any* of the following" → OR (3+ alternatives)
  - "*either* of the following" → OR (exactly 2 alternatives)
  
  AUTHORIZATION DURATION: Look for "Authorization of [N] months may be granted" — typically 
  appears as the first sentence within an indication block, before the criteria list.
  
  STEP THERAPY: Aetna specifies step therapy with dose AND duration together. Example:
  "3-month trial of methotrexate at maximum titrated dose of at least 15 mg per week"
  Extract: trialDurationWeeks (convert months to weeks: 3 months = ~12 weeks), 
  stepTherapyDoseMg (15 mg), stepTherapyDoseFrequency ("per week").

STEP 3 — Extract continuation criteria from the SEPARATE "Continuation of Therapy" section.
This section is NOT per-indication — it covers all indications with general response 
documentation requirements.

STEP 4 — Extract dosing from the "Dosing" TABLE (if present):
| Indication | Dose |
Capture: indicationName, doseMgPerKg, frequency, infusionSchedule (e.g., "at 0, 2, 6 weeks 
then every 8 weeks")

STEP 5 — Extract excluded indications from "Experimental, Investigational, or Unproven" 
section. Each listed condition should be extracted as a separate record with 
coveredStatus: "experimental".

STEP 6 — Extract ICD-10 codes from the "Coding" section tables. Match to indications.

OUTPUT FORMAT:
Return a valid JSON array of DrugPolicyCriteriaRecord objects:
{
  "drugName": string,                    // normalized generic name, lowercase
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,   // from Coding section
  "payerName": "Aetna",
  "effectiveDate": string,              // use "Date Last Reviewed" field
  "cpbNumber": string,
  "preferredProducts": [],              // Aetna CPBs do not use product ranking; leave empty
  "initialAuthDurationMonths": number | null,
  "initialAuthCriteria": [
    {
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "lab_value" | "prescriber_requirement" | 
                       "dosing" | "combination_restriction" | "age" | "severity",
      "logicOperator": "AND" | "OR",
      "requiredDrugsTriedFirst": [string],
      "trialDurationWeeks": number | null,       // convert months to weeks if needed
      "stepTherapyMinDoseMg": number | null,     // Aetna-specific: minimum required dose for prior drug
      "stepTherapyDoseFrequency": string | null,  // e.g., "per week"
      "prescriberType": string | null,            // from Prescriber Specialties lookup
      "rawExcerpt": string
    }
  ],
  "reauthorizationCriteria": [
    {
      "criterionText": string,
      "criterionType": string,
      "requiresDocumentation": string | null,
      "maxAuthDurationMonths": number | null
    }
  ],
  "dosingLimits": {
    "maxDoseMg": number | null,
    "maxDoseMgPerKg": number | null,
    "maxFrequency": string | null,
    "infusionSchedule": string | null,   // e.g., "weeks 0, 2, 6, then every 8 weeks"
    "weightBased": boolean,
    "perFDALabel": false                  // Aetna provides explicit dosing tables
  } | null,
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered" | "excluded" | "experimental",
  "exclusionReason": string | null,       // for excluded/experimental indications
  "confidence": number
}

CRITICAL RULES:
- The Prescriber Specialties section maps per indication — always check this section for 
  prescriberType, not just the indication criteria blocks.
- "either" = OR (binary choice). "any" = OR (multiple choices). Do not conflate these.
- Aetna's continuation section is GLOBAL, not per-indication. Apply it to all indications.
- For excluded indications (from "Experimental, Investigational, or Unproven"), create a 
  record with empty initialAuthCriteria and coveredStatus: "experimental".
- Do NOT invent values. Omit fields not present in the document.
- Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}
```

---

### Prompt C: Cigna Coverage Policy Extraction (IP####)

```
You are extracting structured medical benefit drug policy criteria from a Cigna Drug 
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
  "[NUMBER]. [Indication Name]. Approve for the duration noted if the patient meets ONE 
  of the following (A or B):"
  → TOP-LEVEL LOGIC IS ALWAYS "OR" between branches A and B
  → A = Initial Therapy branch
  → B = Continuation/Currently Receiving branch
  
  BRANCH A (Initial Therapy):
  "A) Initial Therapy. Approve for [N] months if the patient meets BOTH of the following 
  (i and ii):"
  → BRANCH A LOGIC IS "AND" — all sub-criteria (i, ii, iii...) must be met
  → Extract N as initialAuthDurationMonths
  
  BRANCH B (Continuation/Currently Receiving):
  "B) Patient is Currently Receiving. Approve for [N] months if the patient meets ALL 
  of the following (i and ii):"
  → BRANCH B LOGIC IS "AND"
  → Extract N as maxAuthDurationMonths for reauthorizationCriteria
  
  NESTED CRITERIA:
  Within Branch A, sub-criteria use roman numerals (i, ii, iii) and sometimes further 
  nesting with letters (a, b, c). Example nested OR:
  "iii. Patient has had inadequate response to ONE of the following (a, b, or c):
        a. Methotrexate
        b. Leflunomide
        c. Sulfasalazine"
  → This is an OR block nested INSIDE the AND block of Branch A.
  → For the step therapy criterion, set logicOperator: "OR" on the sub-items.
  
  PRESCRIBER: Look for "The medication is prescribed by or in consultation with a [SPECIALIST]"
  
  STEP THERAPY: 
  - Look for "inadequate response, intolerance, or contraindication to" — all three reasons 
    count as valid prior drug failure outcomes
  - "minimum [N]-month trial" → trialDurationWeeks = N * 4
  - "at therapeutic dose" → note in criterionText
  
  APPROVAL DURATIONS:
  - Initial (Branch A): "Approve for [N] months if..." → initialAuthDurationMonths
  - Continuation (Branch B): "Approve for [N] months if..." → maxAuthDurationMonths
  - These are DIFFERENT values — extract both separately

STEP 4 — From "Coding Information" section, extract ICD-10 codes per indication.
Usually in a table format. Map to indication names.

STEP 5 — From "Revision Details" table at the end, extract revision history:
| Type of Revision | Summary of Changes | Date |
This feeds temporal diff records (not DrugPolicyCriteria).

OUTPUT FORMAT:
Return a valid JSON array of DrugPolicyCriteriaRecord objects:
{
  "drugName": string,                    // normalized generic name, lowercase
  "brandNames": [string],
  "indicationName": string,
  "indicationICD10": [string] | null,   // from Coding Information section
  "payerName": "Cigna",
  "effectiveDate": string,
  "policyNumber": string,
  "preferredProducts": [],              // LEAVE EMPTY — populate from companion PSM document
  "initialAuthDurationMonths": number | null,   // from Branch A "Approve for N months"
  "initialAuthCriteria": [
    {
      "criterionText": string,
      "criterionType": "diagnosis" | "step_therapy" | "prescriber_requirement" | 
                       "age" | "severity" | "combination_restriction",
      "logicOperator": "AND" | "OR",    // within Branch A, most are AND; step therapy alternatives are OR
      "parentBranch": "A",              // always "A" for initial criteria
      "requiredDrugsTriedFirst": [string],
      "stepTherapyLogic": "any",        // Cigna typically requires ANY one drug failure ("ONE of the following")
      "stepTherapyMinCount": 1,         // usually 1 — one drug from the list must fail
      "trialDurationWeeks": number | null,
      "trialDurationNote": string | null,  // e.g., "at therapeutic dose"
      "prescriberType": string | null,
      "rawExcerpt": string
    }
  ],
  "reauthorizationCriteria": [
    {
      "criterionText": string,
      "criterionType": string,
      "parentBranch": "B",
      "maxAuthDurationMonths": number | null,   // from Branch B "Approve for N months"
      "requiresDocumentation": string | null,
      "rawExcerpt": string
    }
  ],
  "dosingLimits": null,                 // Cigna defers to clinical judgment; omit
  "combinationRestrictions": [],
  "benefitType": "medical",
  "coveredStatus": "covered",
  "confidence": number
}

CRITICAL RULES:
- The "ONE of the following (A or B)" at the top of each indication creates TWO SEPARATE 
  records: initialAuthCriteria (from Branch A) and reauthorizationCriteria (from Branch B).
  Never mix Branch A and Branch B criteria.
- preferredProducts MUST be left empty — this data comes from the companion PSM document.
- "Approve for [N] months" appears TWICE per indication — once in Branch A (initial), 
  once in Branch B (continuation). Extract BOTH.
- "ONE of the following (a, b, or c)" within Branch A = OR logic. "BOTH of the following" 
  within Branch A = AND logic. Preserve this in logicOperator.
- For step therapy, "inadequate response, intolerance, OR contraindication" — all three 
  are acceptable failure reasons; do not restrict to only "inadequate response".
- Ignore the "INSTRUCTIONS FOR USE" boilerplate. It starts with "This Coverage Policy 
  addresses coverage determinations..." and ends before "OVERVIEW".
- Do NOT invent values. Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}
```

---

### Prompt D: Supplementary Dosing Extraction (UHC Maximum Dosage Policy)

```
You are extracting dosing limit data from a UnitedHealthcare Maximum Dosage and Frequency 
policy document (Policy 2026D0034AT or similar). This data supplements drug-specific 
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

{
  "hcpcsCode": string,                  // e.g., "J1745"
  "drugName": string,                   // normalized generic name, lowercase
  "brandName": string | null,
  "indicationName": string | null,      // null if limit applies to all indications
  "maxUnits": number,                   // maximum units per claim/period
  "unitDefinition": string,             // e.g., "10 mg per unit"
  "periodDays": number,                 // e.g., 30 for monthly, 56 for 8 weeks
  "periodDescription": string,          // e.g., "per claim", "per 56-day period"
  "maxDoseMg": number | null,          // calculated: maxUnits × unitSize (in mg)
  "rawExcerpt": string                  // exact row text from table
}

Return a JSON array. These records will be merged into DrugPolicyCriteria records by 
matching on drugName + indicationName + hcpcsCode.

CRITICAL RULES:
- Extract ONLY drug dosing data. Ignore administrative and boilerplate sections.
- If a row specifies limits for a drug+indication pair already in the primary drug policy, 
  this row supersedes the "per FDA labeled dosing" placeholder in the drug policy.
- If HCPCS unit definition is ambiguous (e.g., "per 10 mg"), state it in unitDefinition.
- Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}
```

---

### Prompt E: Change Bulletin Extraction (Cigna Monthly Updates / UHC Revision History)

```
You are extracting policy change records from a payer policy update document. This may be 
a Cigna monthly policy update bulletin (listing changes across many policies in a table) 
or a UHC Policy History/Revision Information table (at the end of a single policy document).

Document metadata:
- Payer: {payerName}
- Document Type: {documentType}   // "monthly_update_bulletin" | "policy_revision_table"
- Period Covered: {period}
- Effective Date: {effectiveDate}

EXTRACTION TASK:
For each policy change entry, extract a PolicyDiff record:

{
  "payer": string,
  "policyNumber": string | null,
  "policyTitle": string | null,
  "drugName": string | null,         // normalize to generic name; null if unclear
  "indicationName": string | null,   // null if change applies to all indications
  "changeEffectiveDate": string,     // ISO format
  "changeType": "revision_summary",
  "rawChangeText": string,           // exact text from the source document
  "inferredSeverity": "breaking" | "restrictive" | "relaxed" | "neutral" | "unknown",
  "inferredSeverityReason": string   // one sentence explaining the severity classification
}

SEVERITY CLASSIFICATION GUIDE:
- "breaking" — coverage removed entirely, mandatory biosimilar step therapy added for the 
  first time, indication removed, trial duration increased (more restrictive baseline)
- "restrictive" — additional documentation required, auth period shortened, new combination 
  restriction added, prescriber requirement narrowed
- "relaxed" — new indication added, step therapy requirement removed, auth period extended, 
  biosimilar requirement loosened, trial duration reduced
- "neutral" — administrative language change only, formatting change, reference update, 
  no change to clinical criteria

CIGNA MONTHLY BULLETIN FORMAT:
The document contains tables with columns:
  Coverage Policy Number | Policy Title | Summary of Changes | Effective Date
Extract one record per table row.

UHC REVISION HISTORY FORMAT:
The table at the end of a policy document has columns:
  Date | Summary of Changes
Extract one record per table row. Use the parent policy's policy number and title.

Return a JSON array of PolicyDiffRecord objects as described above.

CRITICAL RULES:
- Do NOT infer or add clinical criteria — only extract what is stated in the change summary.
- If the change summary is too vague to classify severity (e.g., "Policy updated"), use 
  inferredSeverity: "unknown".
- Normalize drug names to generic: "REMICADE" → "infliximab", "HUMIRA" → "adalimumab".
- For Cigna bulletins, one policy may have multiple changes in one row — split into 
  separate records if the summary lists multiple distinct changes.
- Return ONLY the JSON array. No explanation, no markdown.

Document text:
{documentText}
```

---

### Prompt F: Preferred Product/PSM Extraction (Cigna PSM Documents)

```
You are extracting preferred product and non-preferred product exception criteria from a 
Cigna Preferred Specialty Management (PSM) document. This data supplements a companion 
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
Each exception criterion specifies what the patient must demonstrate to access the 
non-preferred product when preferred products have failed.

EXTRACTION OUTPUT:
{
  "psmPolicyNumber": string,
  "companionIpPolicyNumber": string,
  "drugName": string,                  // normalized generic name
  "preferredProducts": [
    {
      "productName": string,           // e.g., "Inflectra (infliximab-dyyb)"
      "genericSuffix": string | null,  // e.g., "infliximab-dyyb"
      "rank": 1,                       // all preferred products are rank 1
      "preferredStatus": "preferred"
    }
  ],
  "nonPreferredProducts": [
    {
      "productName": string,           // e.g., "Remicade (infliximab)"
      "preferredStatus": "non_preferred",
      "exceptionCriteria": [
        {
          "criterionText": string,
          "criterionType": "step_therapy" | "prescriber_attestation" | "diagnosis" | "other",
          "requiredTrialProduct": string | null,    // specific preferred product that must be tried
          "trialDurationWeeks": number | null,
          "trialOutcomeRequired": string | null,    // e.g., "inadequate response, intolerance, or hypersensitivity"
          "logicOperator": "AND" | "OR",
          "rawExcerpt": string
        }
      ]
    }
  ],
  "effectiveDate": string,
  "payerName": "Cigna"
}

Return a JSON object (not an array — this is one PSM document, not multiple records).

CRITICAL RULES:
- Preferred products typically include all approved biosimilars; non-preferred is typically 
  the reference (originator) product.
- "hypersensitivity reaction" is a distinct failure reason from "intolerance" — preserve all 
  three: inadequate response, intolerance, hypersensitivity.
- The trial duration in PSM documents refers to a trial of the PREFERRED product, not 
  prior conventional therapy.
- This output will be merged into DrugPolicyCriteria.preferredProducts for the companion 
  IP policy. The merge key is companionIpPolicyNumber + drugName.
- Return ONLY the JSON object. No explanation, no markdown.

Document text:
{documentText}
```

---

## 6. Recommended Schema Changes

Based on the real document analysis, the following changes to the `DrugPolicyCriteria` DynamoDB schema are recommended. All changes are backward-compatible additions — no existing fields are removed.

### 6.1 New Fields to Add to `DrugPolicyCriteria`

| New Field | Type | Description | Justification |
|---|---|---|---|
| `initialAuthDurationMonths` | Number | Duration in months for initial authorization | UHC states this separately from reauth; Cigna embeds it in initial criteria text; Aetna states it before criteria. Currently only reauth has this field. |
| `coveredStatus` | String | `"covered"` &#124; `"excluded"` &#124; `"experimental"` | Cigna IP0534 and Aetna CPBs list explicitly excluded indications. An empty criteria array does not distinguish "no policy found" from "all uses excluded." |
| `exclusionReason` | String | Text reason when `coveredStatus` is "excluded" or "experimental" | Needed for "Experimental, Investigational, or Unproven" sections |
| `documentFormat` | String | `"pdf"` &#124; `"html"` | Aetna CPBs are HTML. The pipeline must route differently for PDF vs. HTML ingestion. |
| `documentReferences` | List | `[{referencedPolicyNumber, referencedPolicyTitle, dataType}]` | UHC cross-references Maximum Dosage and Frequency Policy for dosing data. Tracking these enables supplementary extraction. |
| `linkedDocumentIds` | List | `[policyDocId]` | Links a Cigna IP document to its companion PSM document, or a UHC drug policy to its companion Max Dosage policy. |
| `extractionPromptVersion` | String | Which prompt variant was used | Enables reprocessing when prompts are updated. |

### 6.2 New Subfields on Existing Fields

#### `initialAuthCriteria` item — additional subfields:

| Subfield | Type | Description |
|---|---|---|
| `logicOperator` | String | `"AND"` &#124; `"OR"` — how this criterion relates to sibling criteria |
| `nestingLevel` | Number | 0 = top level; 1 = one level nested; 2 = two levels nested |
| `parentBranch` | String | For Cigna: `"A"` (initial) or `"B"` (continuation) |
| `stepTherapyMinCount` | Number | Minimum number of drugs from `requiredDrugsTriedFirst` that must have been tried (N in UHC's "N of the following") |
| `stepTherapyLogic` | String | `"any"` &#124; `"all"` &#124; `"sequential"` — whether any drug from the list must fail, all must fail, or they must fail in order |
| `stepTherapyMinDoseMg` | Number | Minimum required dose of prior drug (Aetna-specific) |
| `stepTherapyDoseFrequency` | String | Frequency qualifier for prior dose (e.g., "per week") |
| `trialDurationNote` | String | Qualitative note on trial (e.g., "at therapeutic dose," "at maximum titrated dose") |
| `indicationAgeRestriction` | String | Age restriction for this specific criterion (e.g., ">= 6 years", ">= 18 years") |

### 6.3 Major Structural Recommendation: Tree-Structure for Criteria

**Current structure (flat list):**
```json
"initialAuthCriteria": [
  { "criterionText": "diagnosis criterion", "logicOperator": "AND" },
  { "criterionText": "prescriber criterion", "logicOperator": "AND" },
  { "criterionText": "step therapy criterion", "logicOperator": "AND" }
]
```

**Problem:** Cigna's criteria are not a flat list — they are a tree. Branch A (initial) and Branch B (continuation) are alternatives (OR at the top), and within each branch, criteria are AND. A flat list merges all criteria together, losing the branch structure.

**Recommended tree structure:**
```json
"initialAuthCriteria": {
  "operator": "OR",
  "branches": [
    {
      "branchId": "A",
      "branchLabel": "Initial Therapy",
      "authDurationMonths": 6,
      "operator": "AND",
      "criteria": [
        {
          "criterionText": "Patient age >= 18 years",
          "criterionType": "age",
          "operator": "AND"
        },
        {
          "criterionText": "Prescribed by rheumatologist",
          "criterionType": "prescriber_requirement",
          "prescriberType": "rheumatologist",
          "operator": "AND"
        },
        {
          "criterionText": "Inadequate response to one of: methotrexate, leflunomide, sulfasalazine",
          "criterionType": "step_therapy",
          "operator": "OR",
          "requiredDrugsTriedFirst": ["methotrexate", "leflunomide", "sulfasalazine"],
          "stepTherapyMinCount": 1,
          "trialDurationWeeks": 12
        }
      ]
    },
    {
      "branchId": "B",
      "branchLabel": "Currently Receiving",
      "authDurationMonths": 12,
      "operator": "AND",
      "criteria": [
        {
          "criterionText": "Established on infliximab with documented clinical response",
          "criterionType": "continuation",
          "requiresDocumentation": "Chart notes documenting clinical response"
        }
      ]
    }
  ]
}
```

**Hackathon implementation note:** This is a larger change to DynamoDB schema and frontend rendering. If time is constrained, use a compromise: keep the flat list but add `branchId: "A" | "B"` to each criterion item. The Comparison Matrix can then filter by branch and the ApprovalPath scorer can correctly apply AND/OR logic per branch. This is not lossless but is implementable in hours rather than days.

### 6.4 New `PolicyDocuments` Fields

| Field | Type | Description |
|---|---|---|
| `documentFormat` | String | `"pdf"` &#124; `"html"` — routes to correct ingestion path |
| `documentClass` | String | `"drug_specific"` &#124; `"max_dosage"` &#124; `"self_admin"` &#124; `"site_of_care"` &#124; `"preferred_product"` &#124; `"formulary"` &#124; `"update_bulletin"` &#124; `"pa_framework"` |
| `extractionPromptId` | String | Which prompt variant (A, B, C, D, E, F) was used |
| `companionDocumentIds` | List | Links to associated documents (e.g., Cigna IP → PSM, UHC drug policy → Max Dosage) |
| `boilerplateStripped` | Boolean | Whether pre-processing removed boilerplate before extraction |

---

## 7. Pre-Processing Pipeline Recommendations

These recommendations modify the Step Functions ExtractionWorkflow between State 3 (AssembleStructuredText) and State 4 (BedrockSchemaExtraction). Some add new states; others modify existing states.

### 7.1 Document Classification (New State 3.0)

**Add a classification step BEFORE Textract.** When a document is uploaded, classify its type from metadata (file name, user-provided title, payer) to route it correctly.

**Classification logic:**
```python
def classify_document(payer_name: str, document_title: str, s3_key: str) -> str:
    title_lower = document_title.lower()
    
    # Payer-specific URL/filename patterns
    if "cpb" in title_lower or "clinical policy bulletin" in title_lower:
        return "drug_specific_html"  # Aetna CPB → HTML ingestion path
    if "maximum dosage" in title_lower or "max dosage" in title_lower:
        return "max_dosage"
    if "self-administered" in title_lower or "self administered" in title_lower:
        return "self_admin"
    if "site of care" in title_lower:
        return "site_of_care"
    if "preferred specialty management" in title_lower or s3_key.contains("PSM"):
        return "preferred_specialty_mgmt"
    if "formulary" in title_lower or "drug guide" in title_lower or "drug list" in title_lower:
        return "formulary"
    if "policy update" in title_lower or "policy changes" in title_lower:
        return "update_bulletin"
    if "formulary exception" in title_lower:
        return "pa_framework"
    
    # Default: assume drug-specific policy
    return "drug_specific"

PROMPT_ROUTING = {
    "drug_specific":        {"payer": {"UHC": "A", "Aetna": "B", "Cigna": "C"}},
    "drug_specific_html":   "B",        # Aetna HTML path
    "max_dosage":           "D",
    "update_bulletin":      "E",
    "preferred_specialty_mgmt": "F",
    "formulary":            None,       # Do not extract criteria
    "self_admin":           None,       # Index only
    "pa_framework":         None,       # Index only
    "site_of_care":         None,       # Index only
}
```

Documents classified as `None` are indexed in `PolicyDocuments` but do NOT proceed to Bedrock extraction. This prevents the extraction prompt from being called on formularies or administrative documents.

### 7.2 HTML Ingestion Path for Aetna CPBs (Replaces States 1–3 for HTML)

When `documentClass = "drug_specific_html"`, skip Textract entirely. Instead:

```python
import requests
from bs4 import BeautifulSoup

def ingest_aetna_cpb(url: str) -> str:
    """Fetch Aetna CPB HTML and extract clean text."""
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Remove navigation, header, footer, sidebar elements
    for element in soup.select("nav, header, footer, .sidebar, script, style"):
        element.decompose()
    
    # Preserve italic text as AND/OR markers using a placeholder
    for em in soup.find_all("em"):
        em.string = f"*{em.get_text()}*"
    
    # Extract main content div
    main_content = soup.find("div", {"class": "cpb-content"}) or soup.find("main") or soup.body
    
    # Get clean text preserving paragraph and table structure
    return main_content.get_text(separator="\n", strip=True)
```

The cleaned text then goes directly to Prompt B (Bedrock) without Textract processing.

**Important:** Preserve italic markers. Aetna uses `*all*`, `*any*`, `*either*` — these are the AND/OR signals. Standard HTML text extraction strips italics. The parser above must convert `<em>text</em>` to `*text*` before passing to Bedrock.

### 7.3 Boilerplate Stripping (Modify State 3)

Add a payer-specific boilerplate stripping step after Textract output assembly:

```python
BOILERPLATE_PATTERNS = {
    "Cigna": {
        "strip_before": "OVERVIEW",    # Strip everything from doc start to first "OVERVIEW"
        "strip_after": "References",   # Strip References section and everything after it
        "exceptions": ["Revision Details"]  # Do NOT strip Revision Details (needed for diff)
    },
    "UHC": {
        "strip_after": "Instructions for Use",  # Strip from this section to end of doc
    },
    "Aetna": {
        # No boilerplate in CPBs; pharmaceutical guides have formulary boilerplate
        "strip_after": None
    }
}

def strip_boilerplate(text: str, payer: str, doc_class: str) -> str:
    """Remove known boilerplate sections before sending to Bedrock."""
    pattern = BOILERPLATE_PATTERNS.get(payer, {})
    
    if pattern.get("strip_before"):
        marker = pattern["strip_before"]
        idx = text.find(marker)
        if idx > 0:
            text = text[idx:]
    
    if pattern.get("strip_after"):
        marker = pattern["strip_after"]
        idx = text.find(marker)
        if idx > 0 and doc_class != "update_bulletin":
            text = text[:idx]
    
    return text
```

**Token savings:** For Cigna IP0660 (22 pages), stripping "INSTRUCTIONS FOR USE" (~500 words) saves ~650 tokens per Bedrock call. For a 100-document ingest run, this is ~65,000 tokens saved.

### 7.4 ICD-10 Section Pre-Extraction Pass (Modify State 4)

Because ICD-10 codes live in a separate section from clinical criteria in ALL payers' documents, add a two-pass extraction strategy:

**Pass 1 — ICD-10 Extraction:**
```python
ICD10_EXTRACTION_PROMPT = """
Extract only the ICD-10 code mapping from this payer policy document.
Find the section titled "Applicable Codes" (UHC), "Coding Information" (Cigna), 
or "Coding" (Aetna). Extract only the indication-to-ICD10 mapping.

Return JSON: { "icd10Mapping": [{ "indicationName": string, "icd10Codes": [string] }] }

Document text:
{documentText}
"""
```

**Pass 2 — Criteria Extraction (Prompts A, B, or C):**
The criteria extraction prompt receives BOTH the full document text AND the ICD-10 mapping from Pass 1:
```
Pre-extracted ICD-10 mapping (use this to populate indicationICD10 fields):
{icd10Json}

Now extract the clinical criteria per the following instructions...
```

This eliminates the "ICD-10 code if stated" ambiguity in the current prompt and ensures high accuracy for `indicationICD10` without asking Bedrock to simultaneously parse criteria AND hunt for ICD-10 codes in a different section.

### 7.5 Table Structure Preservation (Modify State 3)

Textract's TABLES + FORMS mode detects tables. The current State 3 (AssembleStructuredText) must preserve table structure rather than flattening it to plain text. Tables that must be preserved:

| Document | Table | Data Captured |
|---|---|---|
| Aetna CPB | Dosing table | `dosingLimits` per indication |
| UHC Max Dosage | HCPCS dosing limits table | `quantityLimits` by HCPCS code |
| Cigna Coding Info | ICD-10 code table | `indicationICD10` |
| Cigna PSM | Non-preferred exception criteria | `preferredProducts` exception criteria |
| All payers | Revision history table | `PolicyDiffs` temporal records |

**Recommended table serialization format for Bedrock input:**
```
TABLE: Dosing by Indication
| Indication | Dose |
| Rheumatoid arthritis | 3 mg/kg IV at weeks 0, 2, 6, then every 8 weeks |
| Crohn's disease | 5 mg/kg IV at weeks 0, 2, 6, then every 8 weeks |
END TABLE
```

The `TABLE:` and `END TABLE:` markers help Bedrock correctly identify tabular data versus prose text.

### 7.6 Document Linking / Supplementary Extraction (New State 4.5)

After primary criteria extraction (State 4), check if any companion documents exist:

```python
def get_companion_docs(policy_doc_id: str, payer: str, drug_name: str) -> list:
    """Find companion documents that supplement the primary extraction."""
    companions = []
    
    # For Cigna drug-specific policies, find companion PSM document
    if payer == "Cigna":
        psm = query_dynamodb(
            table="PolicyDocuments",
            filter=f"payerName=Cigna AND documentClass=preferred_specialty_mgmt AND drugName={drug_name}"
        )
        if psm:
            companions.append({"docId": psm.policyDocId, "promptId": "F", "mergeField": "preferredProducts"})
    
    # For UHC drug-specific policies, find companion Max Dosage policy
    if payer == "UHC":
        max_dose = query_dynamodb(
            table="PolicyDocuments",
            filter=f"payerName=UHC AND documentClass=max_dosage AND effectiveDate >= {policy_date}"
        )
        if max_dose:
            companions.append({"docId": max_dose.policyDocId, "promptId": "D", "mergeField": "dosingLimits"})
    
    return companions
```

For each companion document, run its extraction prompt and merge the results into the primary `DrugPolicyCriteria` record before DynamoDB write (State 6).

### 7.7 Confidence Score Calibration

The current spec says "rate confidence below 0.7 if complex conditional logic." Based on real documents, here are payer-specific confidence targets:

| Scenario | Recommended Confidence |
|---|---|
| UHC simple indication (single-condition, flat criteria) | 0.90–0.95 |
| UHC complex indication with multiple step therapy options | 0.75–0.85 |
| UHC dosing = "per FDA labeled dosing" (incomplete data) | 0.65 |
| Aetna CPB with explicit dosing table (complete data) | 0.85–0.92 |
| Aetna CPB continuation criteria (global, not per-indication) | 0.70–0.80 |
| Cigna Branch A criteria (3-level nesting) | 0.72–0.82 |
| Cigna Branch B criteria (continuation) | 0.80–0.88 |
| Cigna IP + PSM not yet merged (preferredProducts empty) | 0.60 |
| Any document with cross-references to unretrieved policies | 0.65 |
| Formulary document (should not be extracted) | N/A — route away |

### 7.8 Section Detection and Splitting

For large documents (UHC: 29 pages, 10+ indications), consider splitting the document by indication BEFORE sending to Bedrock. This reduces per-call context size and allows parallel extraction:

```python
def split_by_indication(text: str, payer: str) -> list[dict]:
    """Split document into per-indication chunks for parallel extraction."""
    
    if payer == "UHC":
        # Split on "Infliximab is proven for the treatment of"
        pattern = r"Infliximab is proven for the treatment of .+?\."
    elif payer == "Cigna":
        # Split on numbered indication headers
        pattern = r"^\d+\. [A-Z][^.]+\. Approve for"
    elif payer == "Aetna":
        # Split on numbered CPB sections
        pattern = r"^\d+\. [A-Z]"
    
    chunks = split_by_regex(text, pattern)
    
    # Include preamble (preferred products, ICD-10 mapping) with each chunk
    preamble = extract_preamble(text, payer)
    return [{"indicationText": chunk, "preamble": preamble} for chunk in chunks]
```

For UHC's 29-page document with 10 indications, this produces 10 parallel Bedrock calls of ~2,500 tokens each instead of one serial call of ~25,000 tokens. Parallel execution reduces total extraction time from ~60 seconds to ~10 seconds.

**Caution:** The ICD-10 mapping section must be extracted FIRST and included as preamble with each chunk, or `indicationICD10` will be null in all chunks.

---

## 8. Appendix: Demo Data Seed Recommendations

Based on document analysis, these are the highest-quality records for pre-seeding DynamoDB before the hackathon demo:

### Priority 1: Comparison Matrix (Must Work)
Infliximab × Rheumatoid Arthritis × UHC, Aetna, Cigna

| Dimension | UHC (2026D0004AR) | Aetna (CPB 0341) | Cigna (IP0660) |
|---|---|---|---|
| Preferred product rank 1 | Inflectra or Avsola | No ranking (step therapy) | Inflectra, Avsola, Renflexis (PSM005) |
| Step therapy required | Yes — 1 biosimilar trial | Yes — DMARD + biologic | Yes — 1 preferred infliximab |
| Trial duration | 14 weeks | 12 weeks (3 months MTX) | 14 weeks |
| Prescriber requirement | Rheumatologist | Rheumatologist | Rheumatologist |
| Initial auth duration | 12 months | 12 months | 6 months |
| Continuation auth duration | Not separately stated | Not separately stated | 12 months |
| Explicit dosing limit | Per FDA label (see Max Dosage) | Explicit table (3 mg/kg) | Per clinical judgment |
| Combination restrictions | Yes (explicit list) | Embedded in criteria | Embedded in criteria |

### Priority 2: Temporal Diff (Must Work for Demo)
UHC infliximab: Infer from Policy History table that biosimilar-first requirement was added in Feb 2026. Seed two `PolicyDiffs` records:
- BREAKING: Biosimilar step therapy added (Jan 2025 had no biosimilar requirement)
- RESTRICTIVE: Trial duration increased from 12 to 14 weeks
- RELAXED: Sarcoidosis indication added

### Priority 3: Approval Path Generator
Patient: RA, failed Inflectra 14 weeks, rheumatologist prescriber
- Aetna: 92/100 — Meets all criteria (Inflectra qualifies as prior biologic trial; rheumatologist present)
- UHC: 61/100 — Gap: Remicade requires biosimilar failure documentation (patient has this, but UHC requires the specific chart note language)
- Cigna: 88/100 — Meets Branch A criteria; minor documentation gap on disease activity score

---

## 9. Implementation Priority Checklist for Mohith

Ordered by impact on demo quality:

**Day 1 (Critical Path):**
- [ ] Implement Prompt A (UHC) — highest-quality source document; powers the comparison matrix demo
- [ ] Add `initialAuthDurationMonths` to DynamoDB schema and extraction prompts
- [ ] Add two-pass ICD-10 extraction (pre-extraction pass before Prompt A/B/C)
- [ ] Add `documentClass` classification logic to route documents before Textract
- [ ] Pre-seed UHC infliximab data manually from spec document if extraction not ready

**Day 2 (Core Features):**
- [ ] Implement Prompt C (Cigna) — needed for 3-payer comparison matrix
- [ ] Implement Prompt B (Aetna) + HTML ingestion path — needed for Aetna comparison data
- [ ] Implement Prompt F (Cigna PSM) + document linking for `preferredProducts`
- [ ] Add `coveredStatus` field and handle negative-coverage documents
- [ ] Implement boilerplate stripping for Cigna and UHC

**Day 3 (Polish + Stretch):**
- [ ] Implement Prompt D (UHC Max Dosage) for dosing supplementation
- [ ] Implement Prompt E (change bulletins) for temporal diff quality
- [ ] Add document splitting for large UHC/Cigna documents
- [ ] Calibrate confidence scores per payer/scenario table in Section 7.7
- [ ] Gemini verification prompt (10.6) — add `stepTherapyMinCount` check to the verification criteria

---

*Report generated from analysis of 15+ real insurance policy documents: UHC 2026D0004AR (29pp), 2026D0034AT (34pp), 2025D0073J (3pp), 2026D0121T (13pp), 2025D0113D (3pp); Aetna CPB 0341 (HTML), 5606-A (7pp), MAR2024 drug guide (200+pp), 2025 Standard Plan drug guide (~150pp); Cigna IP0660 (22pp), PSM005 (3pp), IP0534 (2pp), CNF002 (2pp), Policy 1407 (8pp), December 2025 Policy Updates (33pp), National Preferred Formulary abridged, National Preferred 5-Tier abridged. Cross-referenced against PolicyDiff spec v1.0 (Sections 7, 8, 10).*
