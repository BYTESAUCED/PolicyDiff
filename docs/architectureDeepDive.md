# PolicyDiff — Architecture Deep Dive

## Overview

PolicyDiff is a serverless, event-driven system on AWS (us-east-1). Four layers: Ingest → Compare → Query → Act.

## Services

| Service | Purpose |
|---|---|
| S3 | Raw PDFs, Textract output, structured text |
| DynamoDB | All structured data (5 tables) |
| Step Functions | Extraction workflow orchestration |
| Lambda | All compute (Python 3.12) |
| API Gateway | REST API |
| Textract | PDF OCR (TABLES + FORMS mode) |
| Bedrock (Claude Sonnet) | Schema extraction, query synthesis, diff generation |
| Gemini 1.5 Pro | Cross-model verification (Gemini track) |
| Secrets Manager | Gemini API key |
| Amplify | Frontend hosting |

## Data Flow

```
Upload PDF → S3 → EventBridge → Step Functions
  → ClassifyDocument (identifies payer, generates payerStructureNote)
  → StartTextract → PollTextract
  → AssembleText (pre-processes payer structures, adds chunkMetadata)
  → BedrockExtraction (uses 6+ payer-specific templates, receives payerStructureNote)
  → GeminiVerification → ConfidenceScoring
  → WriteDynamoDB (routes payload by documentClass to DrugPolicyCriteria or FormularyEntries)
  → TriggerDiff (if version exists)
```

## DynamoDB Tables

- `PolicyDocuments` — PK: policyDocId
- `DrugPolicyCriteria` — PK: policyDocId, SK: drugIndicationId
- `FormularyEntries` — PK: hcpcsCode, SK: drugName
- `PolicyDiffs` — PK: diffId
- `QueryLog` — PK: queryId
- `ApprovalPaths` — PK: approvalPathId

## Architectural Decisions

<!-- ADRs documented here as they are made -->

### ADR-001: Step Functions Express Workflow for extraction
Context: Extraction pipeline has multiple async states (Textract polling).
Decision: Express Workflow with retry/wait on PollTextract state.
Rationale: Express Workflows are cost-effective for short-lived, high-volume executions. Built-in retry eliminates custom polling logic.

### ADR-002: Per-route Lambda functions
Context: API has 20+ endpoints across 8 domains.
Decision: One Lambda per logical domain (not per route).
Rationale: Reduces cold start surface while keeping IAM scopes narrow per domain.

### ADR-003: Presigned S3 URLs for upload
Context: PDFs can be 10–50MB.
Decision: Frontend uploads directly to S3 via presigned URL; Lambda never proxies file bytes.
Rationale: Avoids API Gateway 10MB payload limit, reduces Lambda cost.
