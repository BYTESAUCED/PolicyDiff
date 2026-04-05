# PolicyDiff

**PolicyDiff turns payer PDF policies into structured, searchable, comparable data — so pharmacy consultants stop reading 200-page documents by hand.**

Upload a medical benefit drug policy PDF from UnitedHealthcare, Aetna, Cigna, or any other payer. PolicyDiff extracts every prior authorization criterion, step therapy requirement, biosimilar preference, and dosing limit — then lets you compare them side by side, track what changed between versions, and ask plain-English questions like *"Which plans cover infliximab for Crohn's disease and what do they require?"* and make Approval Path for a payer in seconds given a patient's treatment history.

Built for specialty pharmacy consultants and market access teams at companies like Anton RX.

---

## What it does

| Feature | Description |
|---|---|
| **PDF Ingestion** | Upload any payer policy PDF — Textract extracts text, Nova Pro extracts structured criteria |
| **Drug Explorer** | Browse all extracted drugs, indications, and criteria across every ingested policy |
| **Comparison Matrix** | Color-coded cross-payer grid — red = most restrictive, green = least restrictive |
| **Query Interface** | Chat-style natural language search backed by semantic vector search (S3 Vectors + Titan Embeddings) |
| **Approval Path** | Score a patient profile against all payer criteria, identify gaps, generate PA memos |
| **Policy Diffs** | Automatic field-by-field diff when a new version of a policy is uploaded |

---

## Tech Stack

**Frontend**
- Next.js 15 (App Router, SSR) · TypeScript · Tailwind CSS
- Auth0 v4 SDK · TanStack Query · ReactMarkdown + remark-gfm
- Hosted on AWS Amplify

**Backend**
- AWS CDK (Python) — infrastructure as code
- AWS Lambda (Python 3.12) — all business logic
- AWS Step Functions (Express) — extraction pipeline orchestration
- Amazon Textract — PDF text + table extraction
- Amazon Bedrock Nova Pro (`us.amazon.nova-pro-v1:0`) — criteria extraction + query synthesis
- Amazon Titan Embeddings v2 — semantic vector embeddings
- Amazon S3 Vectors — vector index for semantic search
- Amazon DynamoDB — all structured data
- Amazon API Gateway (HTTP API v2) — REST API
- Amazon EventBridge — S3 upload → pipeline trigger

---

## Project Structure

```
policydiff/
├── frontend/                        # Next.js app
│   ├── src/
│   │   ├── app/(dashboard)/         # All pages (compare, explorer, query, upload, approval-path)
│   │   ├── components/              # Shared UI components + shadcn/ui
│   │   ├── hooks/                   # useApi, useAuth, useMobile
│   │   └── lib/                     # API client, Auth0 config, utils
│   ├── .env.local.example           # Frontend env template
│   └── package.json
│
├── backend/                         # CDK + Lambda
│   ├── lib/
│   │   ├── storage_stack.py         # S3, DynamoDB, S3 Vectors bucket
│   │   ├── compute_stack.py         # All Lambdas, Step Functions, EventBridge
│   │   └── api_stack.py             # API Gateway routes + Auth0 JWT authorizer
│   ├── lambda/
│   │   ├── upload_url.py            # Presigned S3 URL generation
│   │   ├── policy_crud.py           # Policy CRUD + download URL
│   │   ├── query.py                 # NL query + vector search
│   │   ├── compare.py               # Cross-payer comparison matrix
│   │   ├── diff.py                  # Temporal policy diffs
│   │   ├── approval_path.py         # PA scoring + memo generation
│   │   ├── embed_and_index.py       # Titan embeddings → S3 Vectors
│   │   └── extraction/
│   │       ├── classify_document.py # Document type routing
│   │       ├── assemble_text.py     # Textract → structured text
│   │       ├── bedrock_extract.py   # Nova Pro criteria extraction
│   │       ├── confidence_score.py  # Payer-calibrated scoring
│   │       ├── write_criteria.py    # DynamoDB write + excerpt files
│   │       ├── trigger_diff.py      # Auto-trigger diff on new version
│   │       └── prompts.py           # All extraction prompt templates (A–H)
│   ├── bin/app.py                   # CDK app entry point
│   ├── .env.example                 # Backend env template
│   └── requirements.txt
│
└── docs/
    ├── deploymentGuide.md           # Full AWS deployment walkthrough
    └── architectureDeepDive.md      # Architecture decisions + data flow
```

---

## Quick Start (Local Dev)

### Prerequisites

- Node.js 20+
- Python 3.12+
- AWS CLI configured (`aws sts get-caller-identity` should succeed)
- AWS CDK CLI: `npm install -g aws-cdk`

### 1. Clone

```bash
git clone https://github.com/opatel04/PolicyDiff.git
cd PolicyDiff
```

### 2. Backend — deploy to AWS

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env — set AWS_REGION, CDK_DEFAULT_ACCOUNT, AUTH0_DOMAIN, AUTH0_AUDIENCE

# Bootstrap CDK (first time only, per account/region)
cdk bootstrap

# Validate (runs cdk-nag security checks)
cdk synth

# Deploy all stacks
cdk deploy --all
```

After deploy, note the API Gateway URL from the CDK output — you'll need it for the frontend.

> For a full deployment walkthrough including Amplify setup, see [docs/deploymentGuide.md](docs/deploymentGuide.md).

### 3. Frontend — run locally

```bash
cd frontend

# Install dependencies
npm install

# Copy and fill in environment variables
cp .env.local.example .env.local
# Edit .env.local — set NEXT_PUBLIC_API_URL to your API Gateway URL from step 2

# Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Environment Variables

### Backend (`backend/.env`)

```env
# AWS
AWS_REGION=us-east-1
CDK_DEFAULT_ACCOUNT=your-aws-account-id

# Auth0 — leave blank to run unauthenticated (dev mode)
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.your-project.com

# Bedrock — Nova Pro inference profile ARN
BEDROCK_MODEL_ARN=arn:aws:bedrock:us-east-1:YOUR_ACCOUNT:inference-profile/us.amazon.nova-pro-v1:0

# CORS — set to your Amplify URL in production, * for local dev
CORS_ORIGIN=*
```

### Frontend (`frontend/.env.local`)

```env
# Auth0
AUTH0_SECRET=                        # openssl rand -hex 32
APP_BASE_URL=http://localhost:3000
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=https://api.your-project.com

# API Gateway URL from CDK output
NEXT_PUBLIC_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
```

---

## How the Extraction Pipeline Works

When you upload a PDF:

```
Browser → S3 (presigned URL)
              ↓
         EventBridge (S3 ObjectCreated)
              ↓
         Step Functions: ExtractionWorkflow
              ↓
    1. Textract — extract text + tables from PDF
    2. ClassifyDocument — detect payer/document type, select prompt (A–H)
    3. AssembleText — reconstruct structure, strip boilerplate
    4. BedrockExtract — Nova Pro extracts structured criteria per indication
    5. ConfidenceScore — payer-calibrated scoring, flag low-confidence records
    6. WriteCriteria — write to DynamoDB, save excerpt .txt files to S3
    6.5 EmbedAndIndex — Titan Embeddings → S3 Vectors (non-blocking)
    7. TriggerDiff — if previous version exists, auto-compute temporal diff
```

---

## How Queries Work

```
POST /api/query { queryText: "..." }
    ↓
1. Embed query via Titan Embeddings v2
2. Semantic search against S3 Vectors index (top 15 hits)
3. Fetch full DynamoDB records for matched policy docs
4. Nova Pro synthesizes answer with citations
5. Returns { answer, citations, queryType, dataCompleteness }
```

---

## Deployment

See **[docs/deploymentGuide.md](docs/deploymentGuide.md)** for:
- CDK stack deployment order
- Amplify GitHub connection setup
- Auth0 configuration
- Troubleshooting common errors

---

## Contributing

This project follows conventional commits. See [docs/commit-message.md](docs/commit-message.md) for the format.
