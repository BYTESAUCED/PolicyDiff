# PolicyDiff — Backend API Documentation

**Version:** 1.0  
**Base URL:** `https://{api-id}.execute-api.us-east-1.amazonaws.com/prod`  
**Owner:** Mohith (AI/ML Core)  
**Last Updated:** April 2026

---

## Overview

PolicyDiff exposes a REST API through AWS API Gateway, backed by Lambda functions. This document covers the endpoints — the AI/ML core: extraction pipeline, natural language queries, cross-payer comparison, temporal diffs, discordance detection, and the approval path generator.

All responses include CORS headers. All request/response bodies are JSON unless otherwise noted.

### Common Response Headers

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type,Authorization
Content-Type: application/json
```

### Error Response Format

```json
{
  "error": "Human-readable error message",
  "detail": "Optional technical detail (only in 500 errors)"
}
```

---

## 1. Policy Ingestion Pipeline (Extraction Lambdas)

The extraction pipeline runs as an **AWS Step Functions** workflow triggered by S3 upload events. It is not directly called via API Gateway — it executes automatically. The states below describe each Lambda in the workflow.

### Pipeline States

| State | Lambda | Description |
|---|---|---|
| 3.0 | `extraction/classify_document.py` | Classifies document type (drug_specific, max_dosage, PSM, etc.) and routes to correct prompt (A–F) |
| 3 | `extraction/assemble_text.py` | Assembles Textract output with boilerplate stripping, table preservation, indication splitting |
| 4 | `extraction/bedrock_extract.py` | Two-pass extraction: ICD-10 pre-extraction → payer-specific prompt (A/B/C/D/E/F) |
| 4.5 | `extraction/gemini_verify.py` | Cross-model verification with Gemini 1.5 Pro (non-blocking) |
| 5 | `extraction/confidence_score.py` | Payer-calibrated confidence scoring with `needsReview` flagging |
| 6 | `extraction/write_criteria.py` | Batch writes records to DynamoDB, updates policy status |
| 7 | `extraction/trigger_diff.py` | Auto-triggers temporal diff if `previousVersionId` exists |

### Extraction Prompt Routing

| Prompt | Payer/Type | Description |
|---|---|---|
| **A** | UHC drug-specific | Rigid template parsing: Coverage Rationale → Applicable Codes → Diagnosis-Specific Criteria |
| **B** | Aetna CPB (PDF) | Textract-based extraction, italic AND/OR markers, explicit dosing tables |
| **C** | Cigna IP#### | 3-level nested AND/OR logic (Branch A/B), embedded auth durations |
| **D** | UHC Max Dosage | Supplementary HCPCS dosing table extraction |
| **E** | Change bulletins | Revision history / monthly update extraction → PolicyDiffs |
| **F** | Cigna PSM#### | Preferred/non-preferred product extraction with exception criteria |

### Step Functions I/O Contract

Every state receives the full event from the previous state and adds its own fields. The initial event (from States 1–2, owned by AZ) must include:

```json
{
  "policyDocId": "uuid",
  "s3Bucket": "policydiff-documents-...",
  "s3Key": "{policyDocId}/document.pdf",
  "textractOutputKey": "{policyDocId}/textract-output.json",
  "payerName": "UnitedHealthcare",
  "planType": "Commercial",
  "documentTitle": "Infliximab Medical Benefit Drug Policy",
  "effectiveDate": "2026-02-01"
}
```

### State 3.0 Output (classify_document)

```json
{
  "...all input fields...",
  "documentClass": "drug_specific",
  "documentFormat": "pdf",
  "extractionPromptId": "A",
  "skipExtraction": false
}
```

### State 3 Output (assemble_text)

```json
{
  "...all input fields...",
  "structuredTextS3Key": "{policyDocId}/structured-text.json",
  "pageCount": 29,
  "sectionCount": 15,
  "tableCount": 4,
  "boilerplateStripped": true,
  "hasIndicationChunks": true
}
```

### State 4 Output (bedrock_extract)

```json
{
  "...all input fields...",
  "extractedCriteria": [{ "...DrugPolicyCriteria schema..." }],
  "extractionCount": 10,
  "extractedCriteriaS3Key": "{policyDocId}/extracted-criteria.json",
  "extractionPromptUsed": "A"
}
```

### State 4.5 Output (gemini_verify)

```json
{
  "...all input fields...",
  "verificationResult": {
    "issues": [
      {
        "field": "criterionType",
        "extractedValue": "diagnosis",
        "correctValue": "step_therapy",
        "confidence": 0.9
      }
    ],
    "overallVerificationConfidence": 0.85,
    "status": "complete"
  }
}
```

### State 5 Output (confidence_score)

```json
{
  "...all input fields...",
  "extractedCriteria": [{ "...with confidence + needsReview fields..." }],
  "reviewCount": 2,
  "confidenceSummary": {
    "totalRecords": 10,
    "reviewCount": 2,
    "avgConfidence": 0.82,
    "minConfidence": 0.55,
    "maxConfidence": 0.95,
    "geminiIssuesCount": 1,
    "geminiVerificationStatus": "complete"
  }
}
```

### State 6 Output (write_criteria)

```json
{
  "...all input fields...",
  "writeStatus": "complete",
  "recordsWritten": 10
}
```

### State 7 Output (trigger_diff)

```json
{
  "...all input fields...",
  "diffTriggered": true,
  "diffTargetPolicyId": "previous-version-uuid"
}
```

---

## 2. Natural Language Query

### `POST /api/query`

Submit a natural language question about drug coverage policies. Returns an instant answer with citations.

**Request Body:**

```json
{
  "queryText": "Which plans cover infliximab for Crohn's disease?"
}
```

**Response (200):**

```json
{
  "queryId": "uuid",
  "queryType": "coverage_check",
  "answer": "Based on ingested policies, infliximab for Crohn's disease is covered by...",
  "citations": [
    {
      "payer": "UnitedHealthcare",
      "documentTitle": "Infliximab Medical Benefit Drug Policy",
      "effectiveDate": "2026-02-01",
      "excerpt": "Coverage is provided for infliximab..."
    }
  ],
  "dataCompleteness": "partial",
  "responseTimeMs": 3450
}
```

**Query Types:**

| Type | Example Questions |
|---|---|
| `coverage_check` | "Which plans cover infliximab for Crohn's disease?" |
| `criteria_lookup` | "What does UHC require for Remicade in rheumatoid arthritis?" |
| `cross_payer_compare` | "Compare step therapy for adalimumab across payers" |
| `change_tracking` | "What changed in UHC's infliximab policy?" |
| `discordance_check` | "Does Aetna's medical policy for rituximab differ from pharmacy?" |

---

### `GET /api/query/{queryId}`

Retrieve a past query result.

**Response (200):**

```json
{
  "queryId": "uuid",
  "queryText": "...",
  "queryType": "...",
  "resultSummary": "...",
  "citations": [...],
  "responseTimeMs": 3450,
  "createdAt": "2026-04-03T12:00:00Z"
}
```

---

### `GET /api/queries`

List the most recent 20 queries.

**Response (200):**

```json
{
  "queries": [
    { "queryId": "...", "queryText": "...", "queryType": "...", "createdAt": "..." }
  ],
  "count": 15
}
```

---

## 3. Cross-Payer Comparison Matrix

### `GET /api/compare`

Generate a color-coded comparison matrix for a drug across payers.

**Query Parameters:**

| Param | Required | Description |
|---|---|---|
| `drug` | ✅ | Drug generic name (e.g., `infliximab`) |
| `indication` | ❌ | Indication to compare (auto-detected if omitted) |
| `payers` | ❌ | Comma-separated payer filter (e.g., `UnitedHealthcare,Aetna`) |

**Response (200):**

```json
{
  "drug": "infliximab",
  "indication": "rheumatoid arthritis",
  "payers": ["UnitedHealthcare", "Aetna", "Cigna"],
  "dimensions": [
    {
      "key": "preferred_products",
      "label": "Preferred Products",
      "values": [
        { "payerName": "UnitedHealthcare", "value": "Inflectra/Avsola rank 1", "severity": "most_restrictive" },
        { "payerName": "Aetna", "value": "Inflectra rank 1", "severity": "moderate" },
        { "payerName": "Cigna", "value": "Any infliximab", "severity": "least_restrictive" }
      ]
    },
    {
      "key": "step_therapy_count",
      "label": "Step Therapy Requirements",
      "values": [...]
    }
  ]
}
```

**Severity Values:**

| Value | Color | Meaning |
|---|---|---|
| `most_restrictive` | 🔴 `#ef4444` | Most restrictive among compared payers |
| `moderate` | 🟡 `#eab308` | Moderate |
| `least_restrictive` | 🟢 `#22c55e` | Least restrictive |
| `equivalent` | ⬜ `#6b7280` | All payers the same |
| `not_specified` | ⬜ `#6b7280` | Not addressed in policy |

---

### `GET /api/compare/export`

Download comparison matrix as CSV.

**Query Parameters:** Same as `GET /api/compare`

**Response (200):** CSV file download

```
Content-Type: text/csv
Content-Disposition: attachment; filename=infliximab_matrix.csv
```

---

## 4. Temporal Policy Diffs

### `GET /api/diffs`

List diffs with optional filters.

**Query Parameters:**

| Param | Required | Description |
|---|---|---|
| `drug` | ❌ | Filter by drug name |
| `payer` | ❌ | Filter by payer name |
| `severity` | ❌ | Filter by change severity (`breaking`, `restrictive`, `relaxed`, `neutral`) |
| `limit` | ❌ | Max results (default: 50) |

**Response (200):**

```json
{
  "items": [
    {
      "diffId": "uuid",
      "diffType": "temporal",
      "drugName": "infliximab",
      "payerName": "UnitedHealthcare",
      "changes": [
        {
          "indication": "rheumatoid arthritis",
          "field": "step_therapy",
          "oldValue": "Must fail one DMARD",
          "newValue": "Must fail one biosimilar infliximab",
          "severity": "breaking",
          "humanSummary": "Biosimilar-first requirement added — patients on Remicade now need documented biosimilar failure"
        }
      ],
      "generatedAt": "2026-04-03T12:00:00Z"
    }
  ],
  "count": 3
}
```

---

### `GET /api/diffs/{diffId}`

Get full diff detail by ID.

**Response (200):** Full `PolicyDiff` record (same schema as list items).

---

### `GET /api/diffs/feed`

Chronological change feed, most recent first. Flattens individual changes from all diffs into a unified feed sorted by timestamp and severity.

**Query Parameters:**

| Param | Required | Description |
|---|---|---|
| `limit` | ❌ | Max feed entries (default: 20) |

**Response (200):**

```json
{
  "feed": [
    {
      "diffId": "uuid",
      "diffType": "temporal",
      "drugName": "infliximab",
      "payerName": "UnitedHealthcare",
      "indication": "rheumatoid arthritis",
      "field": "step_therapy",
      "severity": "breaking",
      "humanSummary": "Biosimilar-first requirement added...",
      "oldValue": "...",
      "newValue": "...",
      "generatedAt": "2026-04-03T12:00:00Z"
    }
  ],
  "totalChanges": 8
}
```

**Change Severity Values:**

| Severity | Badge | Meaning |
|---|---|---|
| `breaking` | 🔴 | Coverage removed, new barrier added, dosing limit reduced |
| `restrictive` | 🟡 | Additional documentation required, auth period shortened |
| `relaxed` | 🟢 | Step therapy removed, indication added |
| `neutral` | ⬜ | Rewording only, no functional change |

---

## 5. Discordance Detection

### `GET /api/discordance`

List all medical vs. pharmacy benefit discordance summaries.

**Response (200):**

```json
{
  "items": [
    {
      "diffId": "uuid",
      "drugName": "ustekinumab",
      "payerName": "Aetna",
      "discordanceScore": 0.65,
      "summary": "Medical benefit requires 4 prior DMARD failures; pharmacy requires 2. Prescriber requirement differs.",
      "changesCount": 3,
      "generatedAt": "2026-04-03T12:00:00Z"
    }
  ],
  "count": 2
}
```

---

### `GET /api/discordance/{drug}/{payer}`

Full discordance analysis for a specific drug + payer pair. Runs Bedrock analysis on-demand.

**Response (200):**

```json
{
  "diffId": "uuid",
  "drugName": "ustekinumab",
  "payerName": "Aetna",
  "discordances": [
    {
      "dimension": "Step therapy requirements",
      "medicalValue": "4 prior DMARD failures required",
      "pharmacyValue": "2 prior DMARD failures required",
      "moreRestrictive": "medical",
      "clinicalImpact": "Patients accessing ustekinumab via medical benefit face twice the step therapy barrier",
      "severity": "high"
    }
  ],
  "overallDiscordanceScore": 0.65,
  "summary": "Significant discordance detected between medical and pharmacy benefit policies..."
}
```

---

## 6. Approval Path Generator ⭐

### `POST /api/approval-path`

Score a patient's clinical profile against all ingested payer criteria. Returns per-payer likelihood scores and identifies gaps.

**Request Body:**

```json
{
  "drugName": "infliximab",
  "indicationName": "rheumatoid arthritis",
  "icd10Code": "M05.79",
  "patientProfile": {
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
}
```

**Response (200):**

```json
{
  "approvalPathId": "uuid",
  "payerScores": [
    {
      "payerName": "Aetna",
      "score": 92,
      "status": "likely_approved",
      "gaps": [],
      "meetsCriteria": true,
      "policyTitle": "Aetna Clinical Policy Bulletin — Infliximab",
      "effectiveDate": "2026-02-01"
    },
    {
      "payerName": "UnitedHealthcare",
      "score": 61,
      "status": "gap_detected",
      "gaps": [
        "Remicade not covered until biosimilar failure documented with chart notes"
      ],
      "meetsCriteria": false,
      "policyTitle": "UHC Infliximab Medical Benefit Drug Policy",
      "effectiveDate": "2026-02-01"
    }
  ],
  "recommendedPayer": "Aetna"
}
```

**Score Statuses:**

| Status | Score Range | Meaning |
|---|---|---|
| `likely_approved` | 80–100 | Patient meets most/all criteria |
| `gap_detected` | 50–79 | Patient meets some criteria but has gaps |
| `likely_denied` | 0–49 | Patient missing critical criteria |

---

### `POST /api/approval-path/{id}/memo`

Generate or retrieve a prior authorization justification memo for a specific payer.

**Request Body:**

```json
{
  "payerName": "Aetna"
}
```

**Response (200):**

```json
{
  "memoText": "Per Aetna's Clinical Policy Bulletin for Infliximab (Effective February 1, 2026), the patient meets initial authorization criteria as follows: (1) Confirmed diagnosis of rheumatoid arthritis (ICD-10: M05.79) with documented high disease activity; (2) Completed 14-week trial of Inflectra (biosimilar infliximab) with documented inadequate response...",
  "citations": [],
  "policyTitle": "Aetna Clinical Policy Bulletin — Infliximab",
  "effectiveDate": "2026-02-01"
}
```

---

## 7. Environment Variables

Each Lambda requires the following environment variables (set by CDK Compute Stack):

| Variable | Used By | Description |
|---|---|---|
| `POLICY_BUCKET_NAME` | extraction/* | S3 bucket for PDFs + structured text |
| `POLICY_DOCUMENTS_TABLE` | write_criteria, trigger_diff, query, approval_path | DynamoDB table name |
| `DRUG_POLICY_CRITERIA_TABLE` | write_criteria, query, compare, discordance, approval_path | DynamoDB table name |
| `POLICY_DIFFS_TABLE` | diff, discordance | DynamoDB table name |
| `QUERY_LOG_TABLE` | query | DynamoDB table name |
| `APPROVAL_PATHS_TABLE` | approval_path | DynamoDB table name |
| `BEDROCK_MODEL_ID` | bedrock_extract, query, compare, diff, discordance, approval_path | Default: `anthropic.claude-sonnet-4-5-20250514` |
| `GEMINI_SECRET_NAME` | gemini_verify | Secrets Manager secret name |
| `DIFF_FUNCTION_NAME` | trigger_diff | DiffLambda function name for async invoke |
| `CORS_ORIGIN` | all API lambdas | Allowed origin for CORS |
| `AWS_REGION` | all | AWS region (default: `us-east-1`) |

---

## 8. DrugPolicyCriteria Schema Reference

Each extracted record follows this schema (enhanced per policy-pdf-analysis.md):

```json
{
  "policyDocId": "uuid (PK)",
  "drugIndicationId": "infliximab#rheumatoid arthritis (SK)",
  "drugName": "infliximab",
  "brandNames": ["Remicade", "Inflectra", "Avsola"],
  "indicationName": "rheumatoid arthritis",
  "indicationICD10": ["M05.79", "M06.00"],
  "payerName": "UnitedHealthcare",
  "effectiveDate": "2026-02-01",
  "policyNumber": "2026D0004AR",
  "preferredProducts": [
    { "productName": "Inflectra", "rank": 1 },
    { "productName": "Avsola", "rank": 2 }
  ],
  "initialAuthDurationMonths": 12,
  "initialAuthCriteria": [
    {
      "criterionText": "Patient must have failed at least one biosimilar infliximab product",
      "criterionType": "step_therapy",
      "logicOperator": "AND",
      "requiredDrugsTriedFirst": ["Inflectra", "Avsola"],
      "stepTherapyMinCount": 1,
      "trialDurationWeeks": 14,
      "rawExcerpt": "History of failure to 1 of the following..."
    }
  ],
  "reauthorizationCriteria": [
    {
      "criterionText": "Patient demonstrated clinical response",
      "criterionType": "continuation",
      "maxAuthDurationMonths": 12,
      "requiresDocumentation": "Chart notes documenting response"
    }
  ],
  "dosingLimits": {
    "maxDoseMg": 500,
    "maxFrequency": "every 8 weeks",
    "weightBased": true,
    "maxDoseMgPerKg": 10,
    "perFDALabel": false
  },
  "combinationRestrictions": [
    { "restrictedWith": "adalimumab", "restrictionType": "same_class" }
  ],
  "quantityLimits": { "maxUnitsPerPeriod": 6, "periodDays": 180 },
  "benefitType": "medical",
  "selfAdminAllowed": false,
  "coveredStatus": "covered",
  "rawExcerpt": "Original policy text excerpt...",
  "confidence": 0.92,
  "needsReview": false,
  "reviewReasons": [],
  "extractionPromptVersion": "A",
  "extractedAt": "2026-04-03T12:00:00Z"
}
```

---

## 9. Integration Notes for Frontend (Om / Dominic)

### Polling Extraction Status

After upload, poll `GET /api/policies/{id}/status` every 3 seconds. Status values:

| Status | UI Message |
|---|---|
| `pending` | "Waiting to start..." |
| `extracting` | "Extracting text from PDF..." |
| `complete` | "Extraction complete — {indicationsFound} indications found" |
| `failed` | "Extraction failed — please retry" |
| `deleted` | (should not appear — record soft-deleted) |

### Severity Color Map

```javascript
const SEVERITY_COLORS = {
  most_restrictive: '#ef4444', // red
  moderate:         '#eab308', // yellow
  least_restrictive:'#22c55e', // green
  equivalent:       '#6b7280', // gray
  not_specified:    '#6b7280', // gray
  breaking:         '#ef4444', // red
  restrictive:      '#eab308', // yellow
  relaxed:          '#22c55e', // green
  neutral:          '#6b7280', // gray
};
```

### Approval Path Score Colors

```javascript
const SCORE_COLORS = {
  likely_approved: '#22c55e', // green
  gap_detected:    '#eab308', // yellow
  likely_denied:   '#ef4444', // red
};
```
