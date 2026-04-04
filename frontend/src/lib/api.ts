// Owner: Om / Dominic
// Typed API client — all 21 routes. Read base URL from Vite env var.
// TODO: add request/response interceptors (auth headers, error normalization)
// TODO: add retry logic with exponential backoff for transient errors

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

// ── Policies ──────────────────────────────────────────────────────────────────

export interface UploadUrlResponse {
  uploadUrl: string;
  policyDocId: string;
  s3Key: string;
}

export interface PolicyRecord {
  policyDocId: string;
  payerName: string;
  fileName: string;
  status: "PENDING" | "PROCESSING" | "COMPLETE" | "FAILED" | "DELETED";
  createdAt: string;
  planType?: string;
  drugName?: string;
  documentTitle?: string;
  effectiveDate?: string;
  extractionStatus?: string;
  s3Key?: string;
  previousVersionId?: string;
}

export interface DrugCriteria {
  drugName: string;
  stepTherapy: string[];
  paRequired: boolean;
  quantityLimit: string | null;
  notes: string;
}

/** POST /api/policies/upload-url */
export async function getUploadUrl(body: {
  fileName: string;
  contentType: string;
}): Promise<UploadUrlResponse> {
  const res = await fetch(`${BASE_URL}/api/policies/upload-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`getUploadUrl failed: ${res.status}`);
  return res.json();
}

/** POST /api/policies */
export async function createPolicy(
  body: {
    policyDocId: string;
    payerName: string;
    planType?: string;
    drugName?: string;
    documentTitle?: string;
    effectiveDate?: string;
    s3Key?: string;
  },
  authToken?: string
): Promise<PolicyRecord> {
  const token = authToken ?? localStorage.getItem("auth_token") ?? "";
  const res = await fetch(`${BASE_URL}/api/policies`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`createPolicy failed: ${res.status}`);
  return res.json();
}

/** GET /api/policies/:id */
export async function getPolicy(_id: string): Promise<PolicyRecord> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/policies/:id/status */
export async function getPolicyStatus(
  id: string
): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/api/policies/${id}/status`);
  if (!res.ok) throw new Error(`getPolicyStatus failed: ${res.status}`);
  const data = await res.json();
  return { status: data.extractionStatus };
}

/** GET /api/policies/:id/criteria */
export async function getPolicyCriteria(
  _id: string
): Promise<{ items: DrugCriteria[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/policies */
export async function listPolicies(_params?: {
  payer?: string;
  drug?: string;
  status?: string;
}): Promise<{ items: PolicyRecord[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** DELETE /api/policies/:id */
export async function deletePolicy(_id: string): Promise<{ success: boolean }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Query ─────────────────────────────────────────────────────────────────────

export interface QueryResult {
  queryId: string;
  status: "PENDING" | "COMPLETE" | "FAILED";
  question: string;
  answer: string;
  citations: { policyDocId: string; excerpt: string }[];
}

/** POST /api/query */
export async function submitQuery(_body: {
  question: string;
  policyIds?: string[];
}): Promise<{ queryId: string }> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/query/:queryId */
export async function getQuery(_queryId: string): Promise<QueryResult> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/queries */
export async function listQueries(): Promise<{ items: QueryResult[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Compare ───────────────────────────────────────────────────────────────────

export interface ComparisonMatrix {
  drug: string;
  matrix: { payer: string; criteria: DrugCriteria }[];
}

/** GET /api/compare */
export async function getComparison(_params: {
  drug: string;
  policyIds?: string[];
}): Promise<ComparisonMatrix> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/compare/export */
export async function exportComparison(_params: {
  drug: string;
  format: "csv" | "pdf";
}): Promise<{ downloadUrl: string }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Diffs ─────────────────────────────────────────────────────────────────────

export interface PolicyDiff {
  diffId: string;
  policyId: string;
  drug: string;
  timestamp: string;
  changes: { field: string; before: unknown; after: unknown }[];
}

/** GET /api/diffs */
export async function listDiffs(_params?: {
  policyId?: string;
  drug?: string;
}): Promise<{ items: PolicyDiff[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/diffs/:diffId */
export async function getDiff(_diffId: string): Promise<PolicyDiff> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/diffs/feed */
export async function getDiffFeed(): Promise<{ items: PolicyDiff[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Discordance ───────────────────────────────────────────────────────────────

export interface DiscordanceSummary {
  drug: string;
  payer: string;
  discordanceScore: number;
  summary: string;
}

/** GET /api/discordance */
export async function listDiscordances(): Promise<{
  items: DiscordanceSummary[];
}> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** GET /api/discordance/:drug/:payer */
export async function getDiscordance(
  _drug: string,
  _payer: string
): Promise<DiscordanceSummary & { industryBaseline: DrugCriteria; gaps: string[] }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Approval Path ─────────────────────────────────────────────────────────────

export interface ApprovalPath {
  requestId: string;
  paths: { payer: string; score: number; steps: string[] }[];
}

/** POST /api/approval-path */
export async function generateApprovalPath(_body: {
  drug: string;
  patientProfile: { diagnosis: string; priorTreatments: string[] };
}): Promise<ApprovalPath> {
  // TODO: implement
  throw new Error("Not implemented");
}

/** POST /api/approval-path/:id/memo */
export async function generateMemo(
  _id: string,
  _body: { payerId: string }
): Promise<{ memoText: string; downloadUrl: string }> {
  // TODO: implement
  throw new Error("Not implemented");
}

// ── Simulator (stretch) ───────────────────────────────────────────────────────

export interface SimulationResult {
  simulationId: string;
  outcome: "APPROVED" | "DENIED" | "STEP_THERAPY";
  confidence: number;
  reasoning: string;
}

/** POST /api/simulate */
export async function simulate(_body: {
  drug: string;
  payerId: string;
  patientProfile: { diagnosis: string; priorTreatments: string[] };
}): Promise<SimulationResult> {
  // TODO: implement
  throw new Error("Not implemented");
}

// keep BASE_URL referenced to avoid unused-var lint error
export { BASE_URL };
