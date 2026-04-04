# PolicyDiff — Project Overview

A plain-English walkthrough of what the app does, every screen, and how the backend pipeline works end to end.

---

## What is PolicyDiff?

Health insurance payers (UnitedHealthcare, Aetna, Cigna, Anthem) publish medical benefit drug policies as PDFs. These documents define which drugs are covered, what clinical criteria a patient must meet, how long they must try cheaper drugs first, and who can prescribe them. Every payer formats these differently, they change multiple times a year, and there is no standardized source.

Anton RX consultants currently read these PDFs manually and build comparison spreadsheets by hand. PolicyDiff automates that entire process — ingest a PDF, get structured data, compare across payers, track changes over time, and generate prior authorization memos for specific patients.

---

## The 8 Screens

### 1. Dashboard (`/`)
The home screen. Shows four stat tiles (total policies, drugs tracked, payers covered, quarterly changes), a "Watched Drugs" section that shows recent policy changes for drugs the user cares about, a "What changed this quarter?" feed, and a recent activity log. Admins see an Upload Policy button; consultants see a personalized view.

**Status:** UI is built with hardcoded mock data. Needs API integration.

---

### 2. Policy Upload (`/upload`)
Two-panel layout. Left side is a drag-and-drop PDF zone with a live extraction progress tracker (Uploading → Extracting text via Textract → Normalizing policy criteria → Complete). Right side is a metadata form: payer name, plan type, document title, effective date.

When you submit, the frontend will:
1. Call `POST /api/policies/upload-url` to get a presigned S3 URL
2. Upload the PDF directly to S3 from the browser
3. Call `POST /api/policies` to register the document metadata
4. Poll `GET /api/policies/{id}/status` every 3 seconds to show extraction progress

**Status:** UI is built. Upload flow is simulated with `setTimeout`. Needs real API wiring.

---

### 3. Drug Explorer (`/explorer`)
A searchable, filterable table of all drugs that have been extracted from ingested policies. Each row shows the drug name, brand names, which payers have policies for it, how many indications are covered, and when it was last updated. Rows expand to show a card per payer with a "View criteria" link. Has fuzzy search across drug name and brand names.

**Status:** UI is built with hardcoded mock data. Needs API integration against `GET /api/policies`.

---

### 4. Comparison Matrix (`/compare`)
The hero screen. Select a drug and indication, get a color-coded grid comparing every payer side by side across dimensions like preferred product ranking, step therapy requirements, trial duration, prescriber requirements, dosing limits, and authorization duration.

Color coding: red = most restrictive, yellow = moderate, green = least restrictive.

Built on AG Grid Community for sorting, filtering, and column pinning. Has a CSV export button.

**Status:** UI is built with hardcoded Infliximab/RA data. Needs API integration against `GET /api/compare`.

---

### 5. Change Feed (`/diffs`)
A chronological timeline of policy changes. Each entry shows the payer, drug, indication, severity badge (breaking / restrictive / relaxed), a plain-English summary of what changed, and a "View technical diff" toggle that shows the old vs. new values field by field with red strikethrough and green new value.

**Status:** UI is built with hardcoded mock data. Needs API integration against `GET /api/diffs/feed`.

---

### 6. Discordance Alerts (`/discordance`)
A table showing cases where the same payer has different criteria for the same drug depending on whether it's covered under the medical benefit vs. the pharmacy benefit. Shows which benefit is more restrictive per criterion. Based on published JMCP research showing ~14% of same-drug policies are discordant.

**Status:** UI is built with hardcoded mock data. Needs API integration against `GET /api/discordance`.

---

### 7. Query Interface (`/query`)
A chat interface styled like Gemini. Empty state shows a centered input with suggested query chips. After the first message, it switches to a chat thread layout with a bottom input bar. Responses are rendered as markdown with a collapsible citations accordion showing which policy documents were used to generate the answer.

**Status:** UI is built. Response is a hardcoded mock. Needs API integration against `POST /api/query`.

---

### 8. Approval Path Generator (`/approval-path`)
Two-panel layout. Left panel is a patient profile form: drug, indication, ICD-10 code, prior drugs tried (with duration and outcome), prescriber specialty, and checkboxes for diagnosis and disease activity documentation. Right panel shows coverage likelihood scores per payer (0–100) with a status badge (Likely Approved / Gap Detected / Likely Denied), a progress bar, and a checklist of which criteria are met or missing. For payers that pass, a "Generate PA Memo" button produces a formal prior authorization justification letter written in that payer's own policy language.

**Status:** UI is built. Evaluation is simulated. Needs API integration against `POST /api/approval-path` and `POST /api/approval-path/{id}/memo`.

---

## The Backend Pipeline

This is what happens when someone uploads a PDF.

```
Browser
  │
  ├─ 1. GET presigned S3 URL  →  UploadUrlLambda
  ├─ 2. PUT PDF directly to S3 (browser → S3, no Lambda involved)
  └─ 3. POST /api/policies    →  PolicyCrudLambda (registers metadata in DynamoDB)

S3 (raw/ prefix)
  │
  └─ EventBridge (Object Created event)
        │
        └─ Step Functions: ExtractionWorkflow (Express, 5 min timeout)
              │
              ├─ State 1: StartTextractJob
              │     Calls textract:StartDocumentAnalysis with TABLES + FORMS mode
              │     Returns a JobId
              │
              ├─ State 2: PollTextractJob (polls every 10s, up to 30 retries)
              │     Calls textract:GetDocumentAnalysis
              │     Waits until JobStatus = SUCCEEDED
              │
              ├─ State 3: AssembleStructuredText  (assemble_text.py)
              │     Reconstructs Textract blocks into a hierarchical structure:
              │     headers → sub-headers → bullets → nested conditions
              │     Preserves table row/cell relationships
              │     Writes structured-text.json to S3
              │
              ├─ State 3.5: ClassifyDocument  (classify_document.py)
              │     Determines document type (drug_specific, formulary, etc.)
              │     Used to select the right extraction prompt downstream
              │
              ├─ State 4: BedrockSchemaExtraction  (bedrock_extract.py)
              │     Sends each indication section separately to Claude Sonnet
              │     (not the whole document — chunked at logical boundaries)
              │     Extracts structured JSON per drug-indication pair:
              │       drugName, indicationName, initialAuthCriteria,
              │       reauthorizationCriteria, dosingLimits, preferredProducts,
              │       combinationRestrictions, benefitType, rawExcerpt, confidence
              │
              ├─ State 5: ConfidenceScoring  (confidence_score.py)
              │     Applies payer-specific calibration rules:
              │       - UHC: penalizes "per FDA labeled dosing" (incomplete data)
              │       - UHC: penalizes cross-document references
              │       - Cigna: penalizes missing PSM companion doc
              │       - Cigna: penalizes 3-level nested AND/OR logic
              │       - Aetna: penalizes missing reauth criteria (global section)
              │     Any record with confidence < 0.7 gets needsReview: true
              │
              ├─ State 6: WriteToDynamoDB  (write_criteria.py)
              │     Batch writes all DrugPolicyCriteria records to DynamoDB
              │     Updates PolicyDocuments.extractionStatus:
              │       "complete" if all records high confidence
              │       "review_required" if any records need review
              │     Also writes rawExcerpt text to S3:
              │       {policyDocId}/excerpts/{drugIndicationId}.txt
              │     (these .txt files are what the embedding step reads)
              │
              ├─ State 6.5: EmbedAndIndex  (embed_and_index.py)
              │     Reads each rawExcerpt .txt file from S3
              │     Chunks text at sentence boundaries if > 2048 chars
              │     Calls Titan Embeddings v2 → 1536-dimensional float32 vector
              │     Writes each vector to S3 Vectors:
              │       bucket: policydiff-vectors-{account}-{region}
              │       index:  policy-criteria-index
              │       key:    {policyDocId}#{drugIndicationId}#{chunkIndex}
              │       metadata: policyDocId, drugName, indicationName,
              │                 payerName, effectiveDate, chunkText (256 chars)
              │     Non-blocking: if this fails, pipeline continues
              │
              └─ State 7: TriggerDiffIfVersionExists  (trigger_diff.py)
                    Checks if PolicyDocuments has a previousVersionId
                    If yes: asynchronously invokes DiffLambda (fire and forget)
                    DiffLambda computes field-by-field temporal diff between
                    old and new DrugPolicyCriteria records using Claude
                    Writes PolicyDiffs records to DynamoDB
```

---

## How Queries Work

When a user asks a question in the Query Interface:

```
POST /api/query  →  QueryLambda

1. Claude classifies the query type:
     coverage_check | criteria_lookup | cross_payer_compare |
     change_tracking | discordance_check

2. Retrieval — two paths:

   Structured queries (criteria_lookup, change_tracking, discordance_check):
     → Query DynamoDB directly by payer + drug + indication
     → You know exactly what you need, no semantic search required

   Open-ended queries (coverage_check, cross_payer_compare):
     → Embed the query text via Titan Embeddings v2 (same model used at index time)
     → Query S3 Vectors index for top-5 most semantically similar rawExcerpt chunks
     → Returns ~3k tokens of relevant text instead of 40k tokens of all criteria

3. Retrieved data + original question → Claude synthesis prompt
4. Response: { answer, citations: [{payer, documentTitle, effectiveDate, excerpt}] }
5. Written to QueryLog table
```

---

## Storage

| Store | What lives there |
|---|---|
| S3 `raw/` prefix | Original uploaded PDFs |
| S3 `{policyDocId}/excerpts/` | rawExcerpt .txt files (one per drug-indication pair) |
| S3 Vectors `policy-criteria-index` | 1536-dim embeddings of rawExcerpts for semantic search |
| DynamoDB `PolicyDocuments` | One record per uploaded PDF, tracks extraction status |
| DynamoDB `DrugPolicyCriteria` | One record per drug-indication pair per policy |
| DynamoDB `PolicyDiffs` | Temporal and cross-payer diffs |
| DynamoDB `QueryLog` | Every query and its answer |
| DynamoDB `ApprovalPaths` | Saved patient profile evaluations and memos |
| DynamoDB `UserPreferences` | Per-user watched drugs, settings |

---

## Auth

Auth0 JWT authorizer on the HTTP API V2. API Gateway validates the token at the edge before any Lambda is invoked — the Lambdas themselves don't touch auth. The authorizer is only activated when `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` are set in `.env`. Without them, the API runs unauthenticated (dev mode).

---

## What's Hardcoded vs. Real

| Screen | Status |
|---|---|
| Dashboard | UI done, data hardcoded |
| Upload | UI done, flow simulated with setTimeout |
| Drug Explorer | UI done, data hardcoded |
| Comparison Matrix | UI done, data hardcoded (Infliximab/RA) |
| Change Feed | UI done, data hardcoded |
| Discordance Alerts | UI done, data hardcoded |
| Query Interface | UI done, response hardcoded |
| Approval Path | UI done, evaluation simulated |
| Backend pipeline | Fully implemented in CDK + Lambda |
| API routes | Defined in CDK, Lambda handlers exist |
| Frontend → API wiring | Not yet done |
