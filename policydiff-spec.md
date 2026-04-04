
# PolicyDiff — Kiro Spec
**Version:** 1.0  
**Last Updated:** April 2026  
**Hackathon Track:** Anton RX — Medical Benefit Drug Policy Tracker  
**Gemini API Note:** Gemini API integration is included as a separate judging track requirement. All core features use AWS Bedrock (Claude Sonnet). Gemini is used exclusively for the cross-model comparison layer described in Section 9.

---

## 1. Problem Statement

Health plans govern coverage of medical benefit drugs through individual medical policies that vary by payer and change frequently. There is no centralized, standardized source for tracking which drugs are covered under which policies, what clinical criteria apply, or how those policies differ across plans.

Anton RX consultants manually read PDFs from UnitedHealthcare, Aetna, Cigna, and others — comparing step therapy rules, spotting coverage changes, and building spreadsheets by hand. This takes days per analysis cycle and misses changes that happen mid-quarter.

**PolicyDiff solves this directly.** Not a generic document parser — a purpose-built medical benefit drug policy intelligence engine that understands the specific structure of these documents and turns them into structured, comparable, queryable, and actionable data.

---

## 2. Solution Overview

PolicyDiff is a four-layer system:

1. **Ingest** — Upload payer PDFs. AWS Textract extracts structure-aware text. Bedrock Claude parses into a normalized schema.
2. **Compare** — Cross-payer comparison matrix with red/yellow/green severity coding. Temporal diffs between policy versions. Medical vs. pharmacy benefit discordance detection.
3. **Query** — Natural language interface. Ask anything. Get cited answers from extracted policy data.
4. **Act** — Approval Path Generator: given a patient clinical profile, score coverage likelihood per payer and generate a prior auth justification memo in that payer's own criteria language.

**Stretch Feature (post-core):** Policy Simulator — what-if editor where a consultant modifies a hypothetical policy and sees how it repositions against real ingested payers on a restrictiveness scale.

---

## 3. Unique Differentiators

| Feature | PolicyDiff | Generic RAG tools | Surescripts RTPB | CoverMyMeds |
|---|---|---|---|---|
| Domain-specific schema extraction | ✅ | ❌ | ❌ | ❌ |
| Cross-payer comparison matrix | ✅ | ❌ | ❌ | ❌ |
| Temporal policy diffs | ✅ | ❌ | ❌ | ❌ |
| Medical vs. pharmacy discordance | ✅ | ❌ | ❌ | ❌ |
| Approval Path Generator | ✅ | ❌ | Partial | Partial |
| Policy Simulator (what-if) | ✅ | ❌ | ❌ | ❌ |
| Works on medical benefit (not just pharmacy) | ✅ | ❌ | ❌ | Partial |

---

## 4. Team Assignments

| Member | Role | Primary Ownership |
|---|---|---|
| **Atharva (AZ)** | Backend + Cloud Infrastructure + Embedding Layer | CDK stacks, S3, DynamoDB, S3 Vectors bucket + index, Step Functions wiring, API Gateway, Lambda CRUD, ingestion pipeline infrastructure (States 1–2, 6.5, 7), `embed_and_index.py` (chunking + Titan Embeddings + S3 Vectors write) |
| **Mohith** | AI/ML Core + Extraction | Extraction logic (States 3–6: assemble_text, bedrock_extract, confidence_score, write_criteria), query classifier, diff engine, comparison matrix normalization, discordance detection, approval path generator, vector-based query retrieval (query.py) |
| **Om** | Frontend Lead | All 8 screens, comparison matrix component, query interface, change feed, design system |
| **Dominic** | Frontend Support | PDF upload component, drug explorer, discordance alerts view, API integration wiring on frontend |

---

## 5. Tech Stack

### Backend
- **Runtime:** Python 3.12 (Lambda)
- **IaC:** AWS CDK v2 (Python)
- **API:** API Gateway REST + Lambda (per-route functions)
- **Orchestration:** AWS Step Functions (Express Workflows)
- **Storage:** S3 (raw PDFs, Textract output), DynamoDB (all structured data), S3 Vectors (semantic search index for query interface)
- **OCR:** AWS Textract (TABLES + FORMS mode)
<<<<<<< HEAD
- **AI — Primary:** AWS Bedrock, Claude Sonnet `anthropic.claude-sonnet-4-5` (us-east-1)
- **AI — Embeddings:** AWS Bedrock, Titan Embeddings v2 `amazon.titan-embed-text-v2:0` (us-east-1) — used for S3 Vectors indexing
- **Hosting:** AWS Amplify (Next.js app, connected manually via console)
- **Region:** us-east-1

### Frontend
- Next.js 14 (App Router, static export via `output: 'export'`)
- TanStack Query v5 (data fetching + polling)
- Tailwind CSS
- Recharts (trend charts)
- AG Grid Community (comparison matrix — sorting, filtering, column pinning)
- shadcn/ui (base components)

### External Data Sources (pre-hackathon prep)
- UHC Commercial Medical Benefit Drug Policies: `uhcprovider.com/en/policies-protocols/commercial-policies/commercial-medical-drug-policies`
- Aetna Clinical Policy Bulletins: `aetna.com/health-care-professionals/clinical-policy-bulletins`
- Cigna Coverage Policies: `static.cigna.com/assets/chcp/pdf/coveragePolicies/medical/`
- Demo drug: **Infliximab** (Remicade, Inflectra, Avsola, Renflexis) — covers 10+ indications across all three payers

---

## 6. Architecture

```
User (Browser)
    └── Amplify Hosting (Next.js static export)
            └── API Gateway (REST, HTTPS, us-east-1)
                    ├── POST /api/policies/upload-url      → UploadUrlLambda
                    ├── POST /api/policies                 → PolicyCrudLambda
                    ├── GET  /api/policies/:id             → PolicyCrudLambda
                    ├── GET  /api/policies/:id/status      → PolicyCrudLambda
                    ├── GET  /api/policies/:id/criteria    → PolicyCrudLambda
                    ├── GET  /api/policies                 → PolicyCrudLambda
                    ├── DELETE /api/policies/:id           → PolicyCrudLambda
                    ├── POST /api/query                    → QueryLambda
                    ├── GET  /api/query/:queryId           → QueryLambda
                    ├── GET  /api/queries                  → QueryLambda
                    ├── GET  /api/compare                  → CompareLambda
                    ├── GET  /api/compare/export           → CompareLambda
                    ├── GET  /api/diffs                    → DiffLambda
                    ├── GET  /api/diffs/:diffId            → DiffLambda
                    ├── GET  /api/diffs/feed               → DiffLambda
                    ├── GET  /api/discordance              → DiscordanceLambda
                    ├── GET  /api/discordance/:drug/:payer → DiscordanceLambda
                    ├── POST /api/approval-path            → ApprovalPathLambda
                    └── POST /api/simulate                 → SimulatorLambda (stretch)

S3 Upload Event
    └── Step Functions (Express Workflow) — ExtractionWorkflow
            ├── State 1: StartTextractJob
            ├── State 2: PollTextractJob (wait + retry)
            ├── State 3: AssembleStructuredText
            ├── State 4: BedrockSchemaExtraction
            ├── State 5: ConfidenceScoring
            ├── State 6: WriteToDynamoDB
            └── State 7: TriggerDiffIfVersionExists
```

---

## 7. Database Schema (DynamoDB)

### Table: `PolicyDocuments`

| Attribute | Type | Description |
|---|---|---|
| `policyDocId` | String (PK) | UUID |
| `payerName` | String | "UnitedHealthcare" \| "Aetna" \| "Cigna" \| "Anthem" |
| `planType` | String | "Commercial" \| "Medicare Advantage" \| "Medicaid" |
| `documentTitle` | String | e.g. "Infliximab Medical Benefit Drug Policy" |
| `effectiveDate` | String | ISO date |
| `s3Key` | String | Path to raw PDF |
| `extractionStatus` | String | "pending" \| "extracting" \| "complete" \| "failed" |
| `extractionJobId` | String | Step Functions execution ARN |
| `rawTextS3Key` | String | Textract output location |
| `version` | Number | Incremented on re-upload of same policy |
| `previousVersionId` | String | Links to prior version |
| `createdAt` | String | ISO datetime |
| `updatedAt` | String | ISO datetime |

**GSIs:**
- `payerName-effectiveDate-index` — list all policies per payer sorted by date

---

### Table: `DrugPolicyCriteria`

| Attribute | Type | Description |
|---|---|---|
| `policyDocId` | String (PK) | |
| `drugIndicationId` | String (SK) | `{drugName}#{indicationCode}` |
| `drugName` | String | Normalized generic name e.g. "infliximab" |
| `brandNames` | List | ["Remicade", "Inflectra", "Avsola"] |
| `indicationName` | String | "rheumatoid arthritis" |
| `indicationICD10` | String | ICD-10 code |
| `payerName` | String | Denormalized for GSI query |
| `effectiveDate` | String | Denormalized from parent policy |
| `preferredProducts` | List | `[{productName, rank}]` |
| `initialAuthCriteria` | List | See schema below |
| `reauthorizationCriteria` | List | See schema below |
| `dosingLimits` | Map | `{maxDoseMg, maxFrequency, weightBased, maxDoseMgPerKg}` |
| `combinationRestrictions` | List | `[{restrictedWith, restrictionType}]` |
| `quantityLimits` | Map | `{maxUnitsPerPeriod, periodDays}` |
| `benefitType` | String | "medical" \| "pharmacy" \| "both" |
| `selfAdminAllowed` | Boolean | |
| `rawExcerpt` | String | Original policy text for citations |
| `confidence` | Number | 0–1 extraction confidence score |
| `extractedAt` | String | ISO datetime |

**Criteria item schema (used in `initialAuthCriteria` and `reauthorizationCriteria`):**
```json
{
  "criterionText": "Patient must have failed at least one biosimilar infliximab product",
  "criterionType": "step_therapy",
  "requiredDrugsTriedFirst": ["Inflectra", "Avsola"],
  "trialDurationWeeks": 14,
  "prescriberType": "rheumatologist",
  "requiresDocumentation": "Chart notes documenting inadequate response"
}
```

**GSIs:**
- `drugName-payerName-index` — lookup all policies for a drug across payers
- `drugName-effectiveDate-index` — lookup policy history for a drug

---

### Table: `PolicyDiffs`

| Attribute | Type | Description |
|---|---|---|
| `diffId` | String (PK) | UUID |
| `diffType` | String | "cross_payer" \| "temporal" \| "benefit_discordance" |
| `drugName` | String | |
| `indicationName` | String | |
| `payerA` | String | For cross_payer diffs |
| `payerB` | String | For cross_payer diffs |
| `payerName` | String | For temporal diffs |
| `policyDocIdOld` | String | |
| `policyDocIdNew` | String | |
| `changes` | List | `[{field, oldValue, newValue, severity, humanSummary}]` |
| `generatedAt` | String | ISO datetime |

**Change severity values:** `"breaking"` \| `"restrictive"` \| `"relaxed"` \| `"neutral"`

**GSIs:**
- `drugName-diffType-index` — all diffs for a drug

---

### Table: `QueryLog`

| Attribute | Type | Description |
|---|---|---|
| `queryId` | String (PK) | UUID |
| `queryText` | String | Raw natural language question |
| `queryType` | String | "coverage_check" \| "criteria_lookup" \| "cross_payer_compare" \| "change_tracking" |
| `resultSummary` | String | Answer text |
| `citations` | List | `[{payer, documentTitle, effectiveDate, excerpt}]` |
| `responseTimeMs` | Number | |
| `createdAt` | String | ISO datetime |

---

### Table: `ApprovalPaths`

| Attribute | Type | Description |
|---|---|---|
| `approvalPathId` | String (PK) | UUID |
| `drugName` | String | |
| `indicationName` | String | |
| `patientProfile` | Map | Clinical profile inputs |
| `payerScores` | List | `[{payerName, score, gaps, meetsCriteria}]` |
| `generatedMemos` | Map | `{payerName: memoText}` |
| `createdAt` | String | ISO datetime |

---

## 8. Feature Specifications

### Feature 1: Policy Document Ingestion Pipeline
**Owner:** AZ (infrastructure + embedding/indexing layer) + Mohith (extraction logic, States 3–6)

**What it does:**
User uploads a medical benefit drug policy PDF. Mohith's extraction pipeline (Textract + Claude) pulls structured criteria out of the messy PDFs. AZ's embedding layer then chunks the raw excerpts, embeds them via Titan, and writes vectors to S3 Vectors for semantic search. Structured data lands in DynamoDB. Vectors land in S3 Vectors. Both are used downstream.

**Why extraction is hard (Mohith's problem):**
Every payer formats their PDFs differently. UHC uses numbered sections with nested bullets. Aetna uses clinical policy bulletin format with tables. Cigna uses a different header hierarchy. A single UHC infliximab policy is 29 pages covering 10+ indications, each with different step therapy, dosing, preferred product rules, and reauthorization criteria. The challenges:
- **Tables**: Textract returns table cells as disconnected blocks — row/column relationships must be reconstructed
- **Nested conditions**: "One of the following" = OR logic. "All of the following" = AND logic. Claude must parse this correctly
- **Indication isolation**: Each indication (RA, Crohn's, psoriasis...) has completely independent criteria — merging them is a critical error
- **Brand vs generic**: Policy says "Remicade" but normalized name is "infliximab"
- **Chunking**: 29-page PDF exceeds Claude's context — must chunk by indication section, not arbitrary character count

**Mohith's extraction approach (States 3–6):**

**State 3 — AssembleStructuredText** (`backend/lambda/extraction/assemble_text.py`):
- Reconstruct Textract blocks into hierarchical structure: headers → sub-headers → bullets → nested conditions
- Preserve table structure: reconstruct rows and cells from TABLE/CELL blocks
- Output: `structured-text.json` with sections array

**State 4 — BedrockSchemaExtraction** (`backend/lambda/extraction/bedrock_extract.py`):
- Send each indication section separately to Claude Sonnet (not the whole document)
- Use extraction prompt (Section 10.1) with strict JSON output
- Handle chunking at logical boundaries (sub-headers), not character count
- Enrich each record: add `policyDocId`, `payerName`, `effectiveDate`, `drugIndicationId`

**State 5 — ConfidenceScoring** (`backend/lambda/extraction/confidence_score.py`):
- Flag records where `confidence < 0.7` with `needsReview: true`
- Additional flags: empty `initialAuthCriteria`, brand name in `drugName`, missing `indicationICD10`

**State 6 — WriteToDynamoDB** (`backend/lambda/extraction/write_criteria.py`):
- Batch write all DrugPolicyCriteria records to DynamoDB
- Update PolicyDocuments `extractionStatus` to `"complete"` and `indicationsFound` count
- Write `rawExcerpt` text to S3 at `{policyDocId}/excerpts/{drugIndicationId}.txt` for AZ's embedding step

**AZ's embedding + indexing layer (State 6.5 — `backend/lambda/embed_and_index.py`):**

Triggered after `write_criteria.py` completes (Step Functions chain or EventBridge on DynamoDB stream):
- Read `rawExcerpt` text files from S3 (`{policyDocId}/excerpts/`)
- For each excerpt:
  - Chunk if > 512 tokens (split at sentence boundaries, not character count)
  - Call Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`) → 1536-dim vector
  - Write to S3 Vectors with metadata: `{ policyDocId, drugName, indicationName, payerName, effectiveDate, benefitType, rawExcerpt (truncated 500 chars) }`
- IAM needed: `bedrock:InvokeModel` on Titan Embeddings ARN + `s3vectors:PutVectors`

**Full pipeline flow:**
1. Frontend requests presigned S3 URL via `POST /api/policies/upload-url`
2. Frontend uploads PDF to `s3://policydiff-docs/{policyDocId}/raw.pdf`
3. S3 event → EventBridge → Step Functions ExtractionWorkflow
4. **State 1 — StartTextractJob:** `textract:StartDocumentAnalysis` with `TABLES + FORMS`
5. **State 2 — PollTextractJob:** Poll every 10s, timeout 5 min
6. **State 3 — AssembleStructuredText** (Mohith)
7. **State 4 — BedrockSchemaExtraction** (Mohith)
8. **State 5 — ConfidenceScoring** (Mohith)
9. **State 6 — WriteToDynamoDB** (Mohith) — also writes rawExcerpts to S3
10. **State 6.5 — EmbedAndIndex** (AZ) — chunks + embeds + writes to S3 Vectors
11. **State 7 — TriggerDiffIfVersionExists** (AZ) — async DiffLambda if new version

**Frontend polling:**  
Frontend polls `GET /api/policies/{policyDocId}/status` every 3 seconds. Show Step Functions state machine progress: "Extracting text... Parsing structure... Found N indications... Writing records... Complete."

**Supported document types (demo):**
- UHC Commercial Medical Benefit Drug Policies
- Aetna Clinical Policy Bulletins  
- Cigna Coverage Policies

**API endpoints:**
```
POST /api/policies/upload-url
  Response: { uploadUrl, policyDocId, s3Key }

POST /api/policies
  Body: { payerName, planType, documentTitle, effectiveDate, policyDocId, previousVersionId? }
  Response: { policyDocId, extractionStatus }

GET /api/policies/:id
  Response: PolicyDocuments record

GET /api/policies/:id/status
  Response: { extractionStatus, extractionProgress, indicationsFound }

GET /api/policies/:id/criteria
  Response: [DrugPolicyCriteria]

GET /api/policies
  Query: ?payerName=&drugName=&page=&limit=
  Response: { items: [PolicyDocuments], nextToken }

DELETE /api/policies/:id
  Response: { deleted: true }
```

---

### Feature 2: Natural Language Query Interface
**Owner:** Mohith (AI logic) + Dominic (frontend query component)

**What it does:**  
User types a plain English question. System classifies query type, retrieves relevant DynamoDB data, and synthesizes an answer with citations back to source policy text.

**Query types the demo must handle:**
1. "Which plans cover infliximab for Crohn's disease?" → coverage table across payers
2. "What prior auth criteria does UnitedHealthcare require for Remicade in rheumatoid arthritis?" → specific step therapy, dosing, preferred products
3. "Compare step therapy requirements for adalimumab across Aetna and UHC" → side-by-side comparison
4. "What changed in UHC's infliximab policy between Jan 2025 and Feb 2026?" → temporal diff with severity
5. "Which payers require a rheumatologist to prescribe ustekinumab?" → prescriber requirement comparison
6. "Does Aetna's medical policy for rituximab differ from their pharmacy policy?" → discordance check

**Backend flow:**
1. `POST /api/query` with `{ queryText }`
2. Bedrock classifies query type: `coverage_check | criteria_lookup | cross_payer_compare | change_tracking | discordance_check`
3. **Retrieval — two paths based on query type:**
   - **Structured queries** (`criteria_lookup`, `change_tracking`, `discordance_check`): query DynamoDB directly by exact payer + drug + indication — you know exactly what you need
   - **Open-ended semantic queries** (`coverage_check`, `cross_payer_compare`): embed the query text via Titan Embeddings v2 → query S3 Vectors index → retrieve top-5 most semantically relevant `rawExcerpt` chunks with metadata (payer, drug, indication, effectiveDate) — ~3k tokens instead of 40k
4. Retrieved excerpts/records + original question → Bedrock Claude synthesis prompt
5. Response includes: `{ queryType, answer, citations: [{payer, documentTitle, effectiveDate, excerpt}] }`
6. Write to QueryLog table

**Token impact:** Open-ended queries drop from ~20-40k tokens (full criteria JSON for all matching records) to ~3k tokens (top-5 relevant excerpts from S3 Vectors).

**S3 Vectors index:** `policy-criteria-index` inside bucket `policydiff-vectors-{account}-{region}`. Each vector entry:
```json
{
  "key": "{policyDocId}#{drugIndicationId}",
  "data": { "float32": [/* 1536-dim Titan embedding of rawExcerpt */] },
  "metadata": {
    "policyDocId": "...",
    "drugName": "infliximab",
    "indicationName": "rheumatoid arthritis",
    "payerName": "UnitedHealthcare",
    "effectiveDate": "2026-02-01",
    "benefitType": "medical",
    "rawExcerpt": "Patient must have failed at least one biosimilar..."
  }
}
```
Vectors are written during extraction (Step 6 — `write_criteria.py`) immediately after DynamoDB write.

**API endpoints:**
```
POST /api/query
  Body: { queryText }
  Response: { queryId, queryType, answer, citations, responseTimeMs }

GET /api/queries
  Response: [QueryLog] (recent 20)
```

---

### Feature 3: Cross-Payer Comparison Matrix
**Owner:** Mohith (normalization logic) + Om (matrix component — hero screen)

**What it does:**  
Select drug + indication → color-coded comparison table across all ingested payers. This is the demo's visual anchor. Judges understand the value in 10 seconds.

**Comparison dimensions:**
1. Preferred product ranking (which biosimilar is rank 1)
2. Step therapy — how many prior drug failures required + which specific drugs
3. Trial duration — minimum weeks of prior therapy
4. Prescriber specialty requirement (rheumatologist / dermatologist / any)
5. Maximum dosing (mg, frequency, weight-based)
6. Authorization duration (months per approval)
7. Reauthorization documentation required
8. Combination therapy restrictions
9. Self-administration allowed

**Severity color coding:**
- 🟢 Green (`#22c55e`) — least restrictive among compared payers
- 🟡 Yellow (`#eab308`) — moderate
- 🔴 Red (`#ef4444`) — most restrictive
- ⬜ Gray (`#6b7280`) — equivalent across payers / not specified

**Backend flow:**
1. `GET /api/compare?drug=infliximab&indication=rheumatoid_arthritis`
2. Query `drugName-payerName-index` GSI for all matching DrugPolicyCriteria
3. Pass to Bedrock cross-payer comparison prompt (Section 10.3) which normalizes terminology differences and assigns severity per dimension per payer
4. Return structured comparison matrix JSON

**Demo example output:**

| Dimension | UHC | Aetna | Cigna |
|---|---|---|---|
| Preferred product | 🔴 Inflectra/Avsola rank 1 | 🟡 Inflectra rank 1 | 🟢 Any infliximab |
| Step therapy drugs | 🔴 Must fail biosimilar first | 🟡 Must fail one DMARD | 🟢 No step therapy |
| Trial duration | 🔴 14 weeks | 🟡 12 weeks | 🟢 Not specified |
| Prescriber req | 🟢 None | 🔴 Rheumatologist | 🟡 Specialist preferred |

**API endpoints:**
```
GET /api/compare?drug=&indication=&payers=
  Response: { drug, indication, payers: [string], matrix: [{dimension, values: [{payerName, value, severity}]}] }

GET /api/compare/export?drug=&indication=&format=csv|pdf
  Response: file download
```

---

### Feature 4: Temporal Policy Diff Engine
**Owner:** Mohith (diff logic) + Om (change feed UI)

**What it does:**  
When a new version of a previously ingested policy is uploaded, the system field-by-field compares old vs. new DrugPolicyCriteria records and generates a human-readable change report with severity ratings.

**Real demo example:**  
UHC infliximab Jan 2025 → Feb 2026:
- 🔴 BREAKING: Avsola and Inflectra now mandatory first-line. Remicade requires biosimilar failure. (NEW)
- 🔴 RESTRICTIVE: 14-week trial duration requirement added (was 12 weeks)
- 🟢 RELAXED: Sarcoidosis indication added to coverage

**Backend flow:**
1. On new policy upload, if `previousVersionId` set, Step Functions State 7 invokes DiffLambda
2. DiffLambda fetches old and new DrugPolicyCriteria for matching drug/indication pairs
3. Bedrock temporal diff prompt (Section 10.4) performs field-by-field comparison
4. Each change classified: `breaking | restrictive | relaxed | neutral`
5. Human-readable summary generated per change
6. PolicyDiffs records written to DynamoDB

**API endpoints:**
```
GET /api/diffs?drug=&payer=&severity=&page=
  Response: [PolicyDiff]

GET /api/diffs/:diffId
  Response: PolicyDiff (full detail with all changes)

GET /api/diffs/feed
  Response: chronological change feed, most recent first
```

---

### Feature 5: Medical vs. Pharmacy Benefit Discordance Detector
**Owner:** Mohith (detection logic) + Dominic (discordance UI)

**What it does:**  
When both a medical and pharmacy benefit policy exist for the same drug + payer, the system auto-flags discordances. Based on published JMCP research: 14% of same-drug policies are discordant, most often in step therapy (80% of discordant pairs), prescriber requirements (22%), and patient subgroup restrictions (10%).

**Demo example (pre-computed, from real research):**  
"Aetna's medical policy for ustekinumab requires trial of 4 conventional therapies for the subcutaneous form (pharmacy benefit) but only 2 for the IV form (medical benefit). Medical benefit is more restrictive on prescriber requirement."

**Backend flow:**
1. When medical + pharmacy policies exist for same drug + payer, auto-trigger discordance check
2. Compare step therapy protocols, prescriber requirements, patient subgroup criteria
3. Flag which benefit is more restrictive per criterion
4. Generate discordance report, write to PolicyDiffs with `diffType: "benefit_discordance"`

**API endpoints:**
```
GET /api/discordance
  Response: [DiscordanceSummary]

GET /api/discordance/:drugName/:payer
  Response: full discordance detail
```

---

### Feature 6: Approval Path Generator ⭐ PRIMARY DIFFERENTIATOR
**Owner:** Mohith (core logic + Bedrock prompt) + Om (patient profile form + memo display)

**What it does:**  
This is where PolicyDiff goes from intelligence tool to action tool. A consultant inputs a patient's clinical profile. The system scores coverage likelihood per payer against extracted criteria, then generates a prior auth justification memo written in that specific payer's own language — using the exact criteria language extracted from their policy document.

This is the only feature that produces a document someone can submit tomorrow morning.

**Patient profile inputs:**
```json
{
  "drugName": "infliximab",
  "indicationName": "rheumatoid arthritis",
  "icd10Code": "M05.79",
  "patientAge": 52,
  "priorDrugsTried": [
    { "drugName": "methotrexate", "durationWeeks": 16, "outcome": "inadequate_response" },
    { "drugName": "Inflectra", "durationWeeks": 14, "outcome": "inadequate_response" }
  ],
  "labValues": { "ccp": "positive", "rf": "positive" },
  "prescriberSpecialty": "rheumatologist",
  "diagnosisDocumented": true,
  "diseaseActivityScore": "high"
}
```

**Coverage likelihood scoring:**  
For each ingested payer, compare patient profile against DrugPolicyCriteria fields:
- Met criteria → contribute to approval score
- Gap in criteria → flag as barrier with specific explanation
- Output: `{ payerName, score: 0-100, status: "likely_approved|gap_detected|likely_denied", gaps: [string] }`

**Example score output:**
```
Aetna:     92/100 — Likely Approved (all step therapy met, prescriber match)
UHC:       61/100 — Gap Detected (Remicade not covered until biosimilar failure documented)
Cigna:     88/100 — Likely Approved (minor documentation gap on disease activity)
```

**PA Memo generation:**  
One-click per payer. Memo is NOT generic — it references the payer's own policy document, by title, by effective date, and maps each patient criterion to each payer criterion by name.

**Example UHC memo excerpt:**  
"Per UHC's Medical Benefit Drug Policy for Infliximab Products (Effective February 1, 2026), the patient meets initial authorization criteria as follows: (1) Confirmed diagnosis of rheumatoid arthritis (ICD-10: M05.79) with documented high disease activity; (2) Completed 14-week trial of Inflectra (biosimilar infliximab) with documented inadequate response per chart notes dated [date]; (3) Prescribing physician is a board-certified rheumatologist. The patient therefore qualifies for Remicade (reference infliximab) under the biosimilar-failure exception criteria outlined in Section 3.2 of the above policy."

**API endpoints:**
```
POST /api/approval-path
  Body: { drugName, indicationName, icd10Code, patientProfile }
  Response: {
    approvalPathId,
    payerScores: [{ payerName, score, status, gaps }],
    recommendedPayer: string
  }

POST /api/approval-path/:id/memo
  Body: { payerName }
  Response: { memoText, citations, policyTitle, effectiveDate }
```

---

### Feature 7: Policy Simulator (Stretch — Post-Core)
**Owner:** Mohith (simulation logic) + Om (editor UI)

**What it does:**  
A consultant selects a real payer's policy, edits one or more fields in a side-by-side editor (change trial duration, add a step therapy requirement, remove a prescriber requirement), and the system re-runs the comparison matrix with the hypothetical policy as a new column — showing where the modified policy sits relative to all real ingested payers on a restrictiveness scale.

**Scope constraints (do not exceed):**
- No patient population data — no "X patients affected" claims (fabricated data kills credibility)
- No cost shift estimates — no real claims data available publicly
- Output only: Restrictiveness Score (1-10 relative to ingested payers) + updated comparison matrix with hypothetical column

**Editable fields:**
- Trial duration (weeks)
- Number of step therapy failures required
- Which specific drugs must fail first
- Prescriber specialty requirement
- Auth duration (months)
- Self-admin allowed (toggle)

**UI behavior:** Changes reflect instantly in the comparison matrix (optimistic update client-side, no API call needed for re-render — the matrix data is already in state).

**API endpoint:**
```
POST /api/simulate
  Body: { basePolicyDocId, modifications: [{field, newValue}], drug, indication }
  Response: { simulatedCriteria, restrictivenesScore, matrixColumn }
```

---

## 9. Gemini API Integration (Separate Track)

**Owner:** Mohith

**Context:** Gemini API is a separate hackathon track requirement. It is NOT a replacement for Bedrock — all production features use Bedrock Claude. Gemini is used as a secondary AI layer for a specific feature to satisfy the track requirement.

**Use case: Cross-Model Policy Verification**  
After Bedrock extracts a DrugPolicyCriteria record, a secondary verification step calls Gemini 1.5 Pro with the same policy text and asks it to validate the extraction — specifically flagging any criteria that Bedrock may have misclassified (e.g., a step therapy requirement classified as a diagnosis requirement). The two model outputs are compared. Discrepancies above a threshold trigger a `needsReview: true` flag on that record.

This serves a real purpose: it increases extraction reliability for a task where errors have clinical consequences. Judges for the Gemini track will see it as a genuine use of Gemini, not a bolted-on demo.

**Implementation:**
- Gemini API key stored in AWS Secrets Manager as `policydiff/gemini-api-key`
- Lambda retrieves key at runtime via `secretsmanager:GetSecretValue`
- Called only during extraction pipeline (Step Functions State 4.5 — between extraction and confidence scoring)
- Model: `gemini-1.5-pro` via `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent`
- If Gemini call fails (rate limit, quota), log error and continue — extraction does not fail

**Lambda code pattern:**
```python
import boto3, json, requests

def get_gemini_key():
    sm = boto3.client("secretsmanager", region_name="us-east-1")
    return json.loads(sm.get_secret_value(SecretId="policydiff/gemini-api-key")["SecretString"])["key"]

def call_gemini_verification(extracted_criteria: dict, raw_text: str) -> dict:
    key = get_gemini_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={key}"
    payload = {
        "contents": [{
            "parts": [{"text": GEMINI_VERIFICATION_PROMPT.format(
                extracted=json.dumps(extracted_criteria),
                raw_text=raw_text[:8000]
            )}]
        }],
        "generationConfig": { "temperature": 0.1, "maxOutputTokens": 2000 }
    }
    resp = requests.post(url, json=payload, timeout=30)
    return resp.json()
```

---

## 10. Bedrock Prompts

### 10.1 Policy Document Extraction Prompt
**Model:** `anthropic.claude-sonnet-4-5`  
**Called from:** Step Functions State 4

```
You are extracting structured medical benefit drug policy criteria from a payer policy document. Your output will be used directly in a clinical decision support system — accuracy is critical.

Document metadata:
- Payer: {payerName}
- Plan type: {planType}
- Document title: {documentTitle}
- Effective date: {effectiveDate}

The document covers one or more drugs across one or more indications. For EACH drug-indication pair, extract:

1. drugName: normalized generic name (e.g., "infliximab", never "Remicade")
2. brandNames: all brand names mentioned in this section
3. indicationName: exact medical condition (e.g., "rheumatoid arthritis", "Crohn's disease")
4. indicationICD10: ICD-10 code if stated
5. preferredProducts: ordered list [{productName, rank}], 1 = most preferred
6. initialAuthCriteria: array of individual requirements, each with:
   - criterionText: human-readable statement
   - criterionType: "diagnosis"|"step_therapy"|"lab_value"|"prescriber_requirement"|"dosing"|"combination_restriction"|"age"|"severity"
   - requiredDrugsTriedFirst: [drug names] — only for step_therapy
   - trialDurationWeeks: number — only if explicitly stated
   - prescriberType: "rheumatologist"|"dermatologist"|"gastroenterologist"|"any" — only for prescriber_requirement
7. reauthorizationCriteria: same structure as initialAuthCriteria, plus:
   - maxAuthDurationMonths: number
   - requiresDocumentation: string describing required clinical evidence
8. dosingLimits: {maxDoseMg, maxFrequency, weightBased: bool, maxDoseMgPerKg}
9. combinationRestrictions: [{restrictedWith, restrictionType: "same_class"|"same_indication"}]
10. quantityLimits: {maxUnitsPerPeriod, periodDays}
11. benefitType: "medical"|"pharmacy" based on document context
12. selfAdminAllowed: boolean
13. rawExcerpt: the exact text passage you extracted this from (for citation)
14. confidence: 0.0-1.0 — your confidence in the accuracy of this extraction

CRITICAL RULES:
- Parse conditional logic precisely. "All of the following" = AND (all must be met). "One of the following" = OR (any one sufficient). Track this in criterionText.
- Each indication section is INDEPENDENT. Never merge criteria across indications.
- If a criterion references another policy document, note this in criterionText but do not follow the reference.
- Normalized drug names only: "infliximab" not "REMICADE®"
- If a field is not specified in the document, omit it entirely. Do not invent values.
- Rate confidence below 0.7 if: the section is ambiguous, uses complex conditional logic, or references external policies.

Return a valid JSON array of DrugPolicyCriteriaRecord objects. Return ONLY the JSON array. No explanation, no markdown fences, no preamble.

Document text:
{documentText}
```

---

### 10.2 Query Classification and Answer Synthesis Prompt
**Model:** `anthropic.claude-sonnet-4-5`  
**Called from:** QueryLambda

```
You are answering questions about medical benefit drug coverage policies for pharmacy consultants at Anton RX.

Available payers in database: {payerList}
Available drugs: {drugList}

User question: {queryText}

Step 1 — Classify the query:
- coverage_check: "Which plans cover Drug X?"
- criteria_lookup: "What does Payer Z require for Drug X?"
- cross_payer_compare: "Compare X across payers" or "differences between..."
- change_tracking: "What changed..." or "how did policy evolve..."
- discordance_check: "Does medical differ from pharmacy for..."

Step 2 — Synthesize an answer from the retrieved data below.

RULES:
- Cite specific payer, document title, and effective date for every factual claim.
- If data is incomplete (e.g., only 2 of 5 payers have been ingested), state this explicitly.
- Never speculate about policies not present in the retrieved data.
- For comparison queries, structure the answer as a markdown table.
- Highlight the most clinically significant differences: step therapy count differences, biosimilar preference switches, prescriber requirement discrepancies.
- Keep answer under 400 words unless the query requires a full table.

Retrieved policy data:
{policyData}

Return JSON:
{
  "queryType": string,
  "answer": string (markdown formatted),
  "citations": [{ "payer": string, "documentTitle": string, "effectiveDate": string, "excerpt": string }],
  "dataCompleteness": "complete|partial|insufficient"
}
```

---

### 10.3 Cross-Payer Comparison Prompt
**Model:** `anthropic.claude-sonnet-4-5`  
**Called from:** CompareLambda

```
You are comparing medical benefit drug policy criteria across multiple payers for the same drug and indication. Your output feeds a color-coded comparison matrix for pharmacy consultants.

Drug: {drugName}
Indication: {indicationName}
Payers being compared: {payerList}

Policy data from each payer:
{policiesJson}

For each of the following dimensions, determine which payer is most restrictive and least restrictive:

1. preferred_products — list each payer's preference hierarchy
2. step_therapy_count — how many prior drug failures required
3. step_therapy_drugs — which specific drugs must fail
4. trial_duration — minimum weeks of prior therapy
5. prescriber_requirement — specialist type required
6. max_dosing — maximum dose and frequency
7. auth_duration — months per authorization period
8. reauth_documentation — what clinical evidence required for renewal
9. combination_restrictions — co-prescribing prohibitions
10. self_admin — whether self-administration is permitted

For each dimension, assign severity per payer:
- "most_restrictive" → red cell
- "moderate" → yellow cell  
- "least_restrictive" → green cell
- "equivalent" → gray cell (all payers the same)
- "not_specified" → gray cell (not addressed in this payer's policy)

Return structured JSON only:
{
  "drug": string,
  "indication": string,
  "dimensions": [
    {
      "key": string,
      "label": string,
      "values": [
        { "payerName": string, "value": string, "severity": string }
      ]
    }
  ]
}
```

---

### 10.4 Temporal Diff Prompt
**Model:** `anthropic.claude-sonnet-4-5`  
**Called from:** DiffLambda

```
You are comparing two versions of the same payer's medical benefit drug policy to identify what changed and how significant those changes are for patients and pharmacy consultants.

Payer: {payerName}
Drug: {drugName}
Old policy effective: {oldDate}
New policy effective: {newDate}

OLD policy criteria:
{oldPolicyJson}

NEW policy criteria:
{newPolicyJson}

For each indication covered, identify ALL changes. For each change:
- field: which field changed ("step_therapy"|"preferred_products"|"dosing"|"auth_duration"|"prescriber_requirement"|"combination_restrictions"|"indication_added"|"indication_removed")
- oldValue: previous value (string representation)
- newValue: new value
- severity:
  - "breaking" — coverage removed, new step therapy barrier added, dosing limit reduced, indication removed
  - "restrictive" — additional documentation required, auth period shortened, new combination restriction
  - "relaxed" — step therapy removed, dosing expanded, indication added, fewer prior failures required
  - "neutral" — rewording only, administrative change, no functional clinical impact
- humanSummary: one sentence in plain English, written for a pharmacy consultant. Be specific about what changed and what it means.

If there are NO functional changes between versions, return an empty changes array.

Return JSON only:
{
  "changes": [
    {
      "indication": string,
      "field": string,
      "oldValue": string,
      "newValue": string,
      "severity": string,
      "humanSummary": string
    }
  ]
}
```

---

### 10.5 Approval Path Scoring + Memo Generation Prompt
**Model:** `anthropic.claude-sonnet-4-5`  
**Called from:** ApprovalPathLambda

```
You are a prior authorization specialist helping a pharmacy consultant assess whether a patient meets coverage criteria for a specific drug under a specific payer's policy.

Drug: {drugName}
Indication: {indicationName}
Payer: {payerName}
Policy title: {policyTitle}
Policy effective date: {policyEffectiveDate}

Payer's extracted criteria:
{payerCriteriaJson}

Patient clinical profile:
{patientProfileJson}

Step 1 — Score coverage likelihood (0-100):
- Start at 100
- For each required criterion the patient does NOT meet: deduct points based on barrier severity
  - Missing step therapy drug trial: -25 points each
  - Wrong prescriber specialty: -20 points
  - Missing diagnosis documentation: -30 points
  - Missing lab values: -10 points
  - Missing reauth documentation: -15 points
- For each criterion met with documentation: no deduction
- If a criterion cannot be determined from the profile: -5 points and flag as "unknown"

Step 2 — Identify gaps:
List each criterion the patient does not clearly meet, with a plain English explanation of what is missing.

Step 3 — Generate PA memo (only if score >= 50):
Write a formal prior authorization justification memo. Requirements:
- Reference the payer's policy by exact title and effective date
- For each criterion the patient meets, state it explicitly using the payer's own language
- Map patient data directly to policy language (e.g., "per Section 3.2 of the policy, patient must have failed one biosimilar infliximab product — patient completed a 14-week trial of Inflectra with documented inadequate response")
- Professional clinical tone
- 300-500 words
- Do NOT mention criteria the patient does not meet

Return JSON:
{
  "score": number,
  "status": "likely_approved|gap_detected|likely_denied",
  "gaps": [string],
  "memo": string or null
}
```

---

### 10.6 Gemini Verification Prompt
**Model:** `gemini-1.5-pro`  
**Called from:** Step Functions State 4.5

```
You are verifying the accuracy of an AI extraction of medical benefit drug policy criteria. Another AI model extracted the following structured data from the policy text. Your job is to identify any errors or misclassifications.

Extracted data:
{extracted}

Original policy text (excerpt):
{raw_text}

Check specifically for:
1. Incorrectly classified criterionType (e.g., a step_therapy requirement labeled as "diagnosis")
2. Missing required drugs in requiredDrugsTriedFirst
3. Incorrect trial duration numbers
4. Missing indications (a drug-indication pair present in the text but not extracted)
5. Incorrect benefitType classification

For each issue found, specify: field, extractedValue, correctValue, confidence (0-1).
If no issues found, return empty issues array.

Return JSON only:
{
  "issues": [
    { "field": string, "extractedValue": string, "correctValue": string, "confidence": number }
  ],
  "overallVerificationConfidence": number
}
```

---

## 11. Frontend Specifications

### 11.1 Design System
- **Color palette:**
  - Restrictive/breaking: `#ef4444` (red-500)
  - Moderate: `#eab308` (yellow-500)
  - Relaxed/least restrictive: `#22c55e` (green-500)
  - Neutral/unchanged: `#6b7280` (gray-500)
  - Background: `#0f172a` (slate-950) — dark, professional B2B aesthetic
  - Card surface: `#1e293b` (slate-800)
  - Border: `#334155` (slate-700)
  - Primary text: `#f1f5f9` (slate-100)
  - Muted text: `#94a3b8` (slate-400)
- **Typography:**
  - Body: Inter
  - Drug names + dosing values: `font-mono` (prevents visual confusion between similar names)
  - Headers: Inter, font-semibold
- **Spacing:** Dense data display. This is B2B for consultants, not a consumer app. Minimize whitespace between data rows.

---

### 11.2 Screen Specifications

#### Screen 1: Dashboard
**Owner:** Om

Displays on initial load. Shows:
- Stats row: Total policies ingested | Drugs tracked | Payers covered | Changes detected this quarter
- **Personalized "Your Watched Drugs" section** — reads `watched_drugs` from the Auth0 JWT claims (`https://policydiff.com/watched_drugs`). If the user has watched drugs set, shows a filtered change feed: "Here are the latest policy changes for infliximab, adalimumab." Each card links directly to the relevant diff or comparison. If no watched drugs are set, shows a prompt: "Watch drugs to get personalized updates → Settings."
- "What changed this quarter?" summary card — top 3 most severe diffs, red badge for breaking changes
- Recent activity feed (last 5 uploads + extractions)
- Quick action: "Upload new policy" button → navigates to Upload screen (admin role only — hide for consultant role)
- Quick action: "Run comparison" → navigates to Comparison Matrix

**Auth0 JWT claims available on the frontend (injected by Auth0 Action):**
- `https://policydiff.com/role` — `"admin"` or `"consultant"`
- `https://policydiff.com/watched_drugs` — array of drug names e.g. `["infliximab", "adalimumab"]`
- `https://policydiff.com/watched_payers` — array of payer names e.g. `["UnitedHealthcare", "Aetna"]`

**Role-based UI behavior:**
- `admin` role: sees Upload button, can delete policies, sees full admin controls
- `consultant` role: read-only, no upload/delete, sees personalized watched-drug dashboard

**Watched drugs management:** Add a "Settings" or gear icon on the dashboard that opens a modal/drawer where the user can add/remove drugs and payers from their watch list. This calls `PUT /api/users/me/preferences` and the next login will re-inject the updated list into the JWT via the Auth0 Action.

**How watched_drugs gets into the JWT:**
An Auth0 Action runs on every login. It reads the user's `UserPreferences` record from DynamoDB (via the backend API or direct AWS SDK call) and injects `watched_drugs`, `watched_payers`, and `role` as custom claims. The frontend reads these directly from the decoded JWT — no extra API call needed on page load.

---

#### Screen 2: Policy Upload
**Owner:** Dominic

- Drag-and-drop PDF upload area with dashed border
- Paste URL alternative input
- Form fields: Payer Name (dropdown: UHC, Aetna, Cigna, Anthem, other), Plan Type (dropdown), Document Title (text), Effective Date (date picker), Previous Version (optional dropdown of existing policies for same payer/drug)
- On upload:
  - Show animated Step Functions progress: Extracting text → Parsing structure → Found N indications → Writing records → Complete
  - Poll `GET /api/policies/:id/status` every 3 seconds
  - On complete: show summary card "Extracted N drug-indication pairs. X needed review (confidence < 0.7)."
  - Button: "View extracted criteria" → navigate to Drug Explorer filtered to this policy

---

#### Screen 3: Drug Explorer
**Owner:** Dominic

- Search bar: type drug name or brand name
- Filterable table: Drug Name | Payers Covered | Indications | Last Updated | Actions
- Click a drug → expanded view showing:
  - All payers that have a policy for this drug
  - Per payer: coverage status, number of indications, effective date
  - Quick link: "Compare this drug" → Comparison Matrix

---

#### Screen 4: Comparison Matrix (Hero Screen)
**Owner:** Om

This is the primary demo screen. Must be visually undeniable.

- Drug selector (typeahead autocomplete from ingested drugs)
- Indication selector (populates based on selected drug)
- Payer filter (multi-select checkboxes)
- AG Grid table:
  - Row = comparison dimension
  - Column = payer
  - Cell = value + color background
  - Column pinning: Dimension column always visible
  - Sorting: click column header to sort payers by restrictiveness
  - Cell click: opens detail popover with raw policy excerpt + citation
- Export button: download as CSV

**Performance requirement:** Matrix renders within 500ms of API response for ≤5 payers.

---

#### Screen 5: Change Feed
**Owner:** Om

- Chronological list of all detected policy changes
- Filters: Severity (all/breaking/restrictive/relaxed), Payer (multi-select), Drug (text search), Date range
- Each change card shows:
  - Severity badge (red/yellow/green)
  - Payer name + drug + indication
  - Human-readable summary
  - Old value → New value (expandable)
  - Policy version info (old effective date → new effective date)
- "What changed this quarter?" aggregate view: group by payer, show count of breaking/restrictive/relaxed changes

---

#### Screen 6: Query Interface
**Owner:** Dominic

- Full-width search bar with placeholder: "Ask anything about drug coverage policies..."
- Suggested queries (clickable chips):
  - "Which plans cover infliximab for Crohn's disease?"
  - "Compare step therapy for adalimumab across payers"
  - "What changed in UHC's infliximab policy?"
- Response panel:
  - Answer text (markdown rendered)
  - Citations expandable accordion: payer | document title | effective date | raw excerpt
  - Query type badge (coverage check / criteria lookup / etc.)
  - Query history sidebar (last 10 queries, click to reload)

---

#### Screen 7: Discordance Alerts
**Owner:** Dominic

- List of all detected medical vs. pharmacy benefit discordances
- Each alert card:
  - Drug name + payer
  - Which benefit is more restrictive per criterion
  - Specific discordance: "Medical requires 4 prior DMARD failures; pharmacy requires 2"
  - Link to full policy documents for both benefits
- Filter: by payer, by drug, by criterion type

---

#### Screen 8: Approval Path Generator
**Owner:** Om (UI) + Mohith (logic)

- **Left panel — Patient Profile Form:**
  - Drug name (dropdown from ingested drugs)
  - Indication (dropdown based on drug)
  - ICD-10 code (auto-suggested based on indication)
  - Prior drugs tried (repeatable row: drug name, duration in weeks, outcome dropdown: inadequate_response / intolerance / contraindication)
  - Lab values (key-value pairs, add/remove rows)
  - Prescriber specialty (dropdown)
  - Checkboxes: Diagnosis documented, Disease activity documented

- **Right panel — Results:**
  - Per-payer score cards in a horizontal row:
    - Score circle (0-100, color coded)
    - Status badge: "Likely Approved" (green) / "Gap Detected" (yellow) / "Likely Denied" (red)
    - Collapsible gaps list
    - "Generate PA Letter" button (enabled if score ≥ 50)
  - Recommended payer highlight (highest score)

- **PA Memo Modal:**
  - Full memo text (scrollable)
  - Header: payer name, policy title, effective date
  - Copy to clipboard button
  - Download as PDF button (client-side, using browser print)

---

## 12. CDK Infrastructure Spec

**Owner:** AZ

### Stacks:

#### `PolicyDiffStorageStack`
```python
# S3 bucket: policydiff-documents-{account}-{region}
# - Versioning enabled
# - Lifecycle rule: transition to S3-IA after 30 days
# - Block all public access

# S3 Vectors bucket: policydiff-vectors-{account}-{region}  [AZ]
# - Vector index: policy-criteria-index
# - Dimension: 1536 (Titan Embeddings v2)
# - Distance metric: cosine
# - IAM: s3vectors:PutVectors for write_criteria Lambda
#         s3vectors:QueryVectors for QueryLambda

# DynamoDB tables (all with PAY_PER_REQUEST billing):
# - PolicyDocuments (PK: policyDocId)
# - DrugPolicyCriteria (PK: policyDocId, SK: drugIndicationId) + 2 GSIs
# - PolicyDiffs (PK: diffId) + 1 GSI
# - QueryLog (PK: queryId)
# - ApprovalPaths (PK: approvalPathId)
# - UserPreferences (PK: userId) — Auth0 sub claim, stores watched drugs/payers
```

#### `PolicyDiffComputeStack`
```python
# Lambda functions (Python 3.12, 512MB default, 256MB for CRUD):
# - UploadUrlLambda (timeout: 10s)
# - PolicyCrudLambda (timeout: 30s)
# - QueryLambda (timeout: 60s)
# - CompareLambda (timeout: 60s)
# - DiffLambda (timeout: 120s)
# - DiscordanceLambda (timeout: 60s)
# - ApprovalPathLambda (timeout: 90s)
# - PolicyMonitorLambda (timeout: 60s) — S3 inbox auto-ingestion, daily schedule
# - SimulatorLambda (timeout: 60s, stretch)

# Step Functions Express Workflow: ExtractionWorkflow (7 states, no Gemini)
# EventBridge rule: S3 raw/ prefix → Step Functions trigger
# EventBridge Scheduler: daily → PolicyMonitorLambda

# IAM roles per Lambda (least privilege):
# - S3: GetObject, PutObject on policydiff-documents bucket
# - DynamoDB: specific table ARNs only
# - Bedrock Claude Sonnet: InvokeModel on anthropic.claude-sonnet-4-5 ARN
#   → QueryLambda, CompareLambda, DiffLambda, ApprovalPathLambda, ExtractionWorkflow role
# - Bedrock Titan Embeddings: InvokeModel on amazon.titan-embed-text-v2:0 ARN  [NEW]
#   → write_criteria Lambda (Step 6) — generates embeddings for S3 Vectors
#   → QueryLambda — embeds user query for vector similarity search
# - S3 Vectors: PutVectors on policydiff-vectors bucket  [NEW]
#   → write_criteria Lambda (Step 6)
# - S3 Vectors: QueryVectors on policydiff-vectors bucket  [NEW]
#   → QueryLambda
# - Textract: StartDocumentAnalysis, GetDocumentAnalysis
# - Step Functions: StartExecution (for ExtractionWorkflow trigger)
# - Auth0 JWT authorizer: all routes protected, role claim checked in Lambda
```

#### `PolicyDiffApiStack`
```python
# API Gateway REST API: PolicyDiffAPI
# - All routes with Lambda proxy integration
# - CORS: allow origin * for hackathon (restrict post-demo)
# - Request logging enabled
# - Throttling: 100 req/s, burst 200
```

#### `PolicyDiffFrontendStack`
```python
# NOTE: FrontendStack is NOT deployed via CDK — Amplify is connected manually
# through the AWS Console (GitHub OAuth connection, build settings, env vars).
# The CDK stack exists for IaC documentation purposes only.
#
# Amplify App: connected to github.com/opatel04/PolicyDiff, main branch
# Build settings: cd frontend && npm ci && npm run build, output frontend/.next/
# Environment variables (set in Amplify console):
#   NEXT_PUBLIC_API_BASE_URL — from ApiStack CfnOutput ApiInvokeUrl
#   NEXT_PUBLIC_AUTH0_DOMAIN — Auth0 tenant domain
#   NEXT_PUBLIC_AUTH0_CLIENT_ID — Auth0 SPA client ID
```

---

## 13. Implementation Order

### Phase 1 — Foundation (Hours 0–6)
**AZ:**
1. CDK deployed: S3 bucket, all DynamoDB tables with GSIs, API Gateway skeleton
2. UploadUrlLambda working — presigned URL generation
3. S3 event → Step Functions trigger wired
4. PolicyCrudLambda: create + get + list endpoints

**Om:**
5. Next.js app scaffolded: App Router + Tailwind + TanStack Query + shadcn/ui init
6. Routing setup: all 8 screens stubbed as route files under `app/` with placeholder content
7. Dashboard shell with hardcoded stats

**Dominic:**
8. Upload screen: drag-and-drop UI, form fields, progress indicator (UI only, no API yet)

**Mohith:**
9. Textract integration tested against one real UHC PDF — confirm structured text output
10. Bedrock extraction prompt iterated until it correctly parses at least 3 infliximab indications

---

### Phase 2 — Extraction Core (Hours 6–14)
**AZ:**
11. Step Functions full workflow: all 7 states wired
12. Textract text assembly Lambda — hierarchical structure preserved
13. Policy status polling endpoint working

**Mohith:**
14. BedrockExtractionLambda: full extraction prompt + JSON parsing + error handling
15. Confidence scoring logic
16. DrugPolicyCriteria DynamoDB write (batch)
17. Manual verification: extracted data matches source PDF for 3+ indications

**Dominic:**
18. Upload screen wired to API: presigned URL → S3 upload → poll status → show result summary

**Om:**
19. Drug Explorer screen: search + table + expanded drug view
20. Design system tokens applied globally

---

### Phase 3 — Query + Comparison (Hours 14–22)
**Mohith:**
21. QueryLambda: classification + DynamoDB lookup + Bedrock synthesis
22. CompareLambda: multi-payer fetch + Bedrock normalization + severity assignment

**Om:**
23. Comparison Matrix: AG Grid with color-coded cells — this is the priority frontend task
24. Query Interface: search bar + response panel + citation accordion

**AZ:**
25. All remaining API routes wired: /api/query, /api/compare
26. DynamoDB GSI queries tested for cross-payer lookup

**Dominic:**
27. Query Interface: example query chips, query history sidebar

---

### Phase 4 — Diffs + Discordance + Approval Path (Hours 22–30)
**Mohith:**
28. DiffLambda: temporal diff prompt + PolicyDiffs write
29. DiscordanceLambda: medical vs. pharmacy comparison logic
30. ApprovalPathLambda: patient profile scoring + memo generation prompt

**Om:**
31. Change Feed: filter UI + severity badges + change cards
32. Approval Path Generator: patient form + score cards + memo modal

**AZ:**
33. Step Functions State 7: auto-trigger diff on new version upload
34. All Lambda IAM roles finalized
35. Amplify deployment configured

**Dominic:**
36. Discordance Alerts screen
37. Approval Path frontend API integration

---

### Phase 5 — Polish + Demo Data (Hours 30–36)
**All:**
38. Pre-load 3 real policy documents with validated DynamoDB seed data (extract offline — have clean data ready regardless of live extraction)
39. Dashboard stats populated from real data
40. Fallback data: pre-computed quer... (7 KB left)
