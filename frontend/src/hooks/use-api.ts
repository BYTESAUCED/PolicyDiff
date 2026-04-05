"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";

// Don't retry on 4xx errors (auth failures, bad requests)
const shouldRetry = (_count: number, error: Error) =>
  !(error instanceof ApiError && error.status >= 400 && error.status < 500);

// ── Shared types ─────────────────────────────────────────────────────────────

export interface PolicyDocument {
  policyDocId: string;
  payerName: string;
  planType: string;
  documentTitle: string;
  effectiveDate: string;
  extractionStatus: string;
  drugName?: string;
  s3Key?: string;
  createdAt?: string;
  indicationsFound?: number;
  extractionProgress?: string;
  confidenceSummary?: {
    averageConfidence?: number;
    reviewCount?: number;
  };
  previousVersionId?: string;
}

export interface FeedEntry {
  diffId: string;
  diffType: string;
  drugName: string;
  payerName: string;
  indication: string;
  field: string;
  severity: string;
  humanSummary: string;
  oldValue: string;
  newValue: string;
  generatedAt: string;
}

export interface DiffRecord {
  diffId: string;
  diffType: string;
  drugName: string;
  payerName: string;
  indicationName?: string;
  changes: {
    indication?: string;
    field: string;
    severity: string;
    humanSummary: string;
    oldValue: string;
    newValue: string;
  }[];
  generatedAt: string;
}

export interface ComparisonMatrix {
  drug: string;
  indication: string;
  payers: string[];
  dimensions: {
    key: string;
    label: string;
    values: { payerName: string; value: string; severity: string }[];
  }[];
  message?: string;
}

export interface QueryResult {
  queryId: string;
  queryType: string;
  answer: string;
  citations: {
    payer: string;
    documentTitle: string;
    effectiveDate: string;
    excerpt: string;
  }[];
  dataCompleteness: string;
  responseTimeMs: number;
}

export interface PayerScore {
  payerName: string;
  score: number;
  status: string;
  gaps: string[];
  meetsCriteria: boolean;
  policyTitle: string;
  effectiveDate: string;
}

export interface ApprovalPathResult {
  approvalPathId: string;
  payerScores: PayerScore[];
  recommendedPayer: string;
}

// ── Queries ──────────────────────────────────────��───────────────────────────

export interface RecentQuery {
  queryId: string;
  queryText: string;
  queryType: string;
  createdAt: string;
}

export function useRecentQueries(limit = 5) {
  return useQuery({
    queryKey: ["recent-queries", limit],
    queryFn: () =>
      apiFetch<{ queries: RecentQuery[] }>(
        "api/queries",
        undefined,
        { limit }
      ),
    retry: shouldRetry,
    staleTime: 30_000,
  });
}

export function usePolicies(params?: {
  payerName?: string;
  drugName?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["policies", params],
    queryFn: () =>
      apiFetch<{ items: PolicyDocument[]; nextToken?: string }>(
        "api/policies",
        undefined,
        params as Record<string, string>
      ),
    retry: shouldRetry,
    staleTime: 30_000,
  });
}

export function usePolicyStatus(policyDocId: string | null) {
  return useQuery({
    queryKey: ["policy-status", policyDocId],
    queryFn: () =>
      apiFetch<{ extractionStatus: string; extractionJobId?: string }>(
        `api/policies/${policyDocId}/status`
      ),
    enabled: !!policyDocId,
    refetchInterval: (query) => {
      const status = query.state.data?.extractionStatus;
      if (status === "PENDING" || status === "IN_PROGRESS") return 3000;
      return false;
    },
  });
}

export function useDiffsFeed(limit = 20) {
  return useQuery({
    queryKey: ["diffs-feed", limit],
    queryFn: () =>
      apiFetch<{ feed: FeedEntry[]; totalChanges: number }>(
        "api/diffs/feed",
        undefined,
        { limit }
      ),
    retry: shouldRetry,
    staleTime: 30_000,
  });
}

export function useDiffs(params?: {
  drug?: string;
  payer?: string;
  severity?: string;
}) {
  return useQuery({
    queryKey: ["diffs", params],
    queryFn: () =>
      apiFetch<{ items: DiffRecord[]; count: number }>(
        "api/diffs",
        undefined,
        params as Record<string, string>
      ),
    retry: shouldRetry,
    staleTime: 30_000,
  });
}

export function useCompare(
  drug: string,
  indication?: string,
  payers?: string
) {
  return useQuery({
    queryKey: ["compare", drug, indication, payers],
    queryFn: () =>
      apiFetch<ComparisonMatrix>("api/compare", undefined, {
        drug,
        indication,
        payers,
      }),
    enabled: !!drug,
    retry: shouldRetry,
    staleTime: 60_000,
  });
}

export function useUserPreferences() {
  return useQuery({
    queryKey: ["user-preferences"],
    queryFn: () =>
      apiFetch<{
        userId: string;
        watchedDrugs: string[];
        watchedPayers: string[];
      }>("api/users/me/preferences"),
    retry: shouldRetry,
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: { watchedDrugs: string[]; watchedPayers: string[] }) =>
      apiFetch("api/users/me/preferences", {
        method: "PUT",
        body: JSON.stringify(prefs),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user-preferences"] });
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useSubmitQuery() {
  return useMutation({
    mutationFn: (queryText: string) =>
      apiFetch<QueryResult>("api/query", {
        method: "POST",
        body: JSON.stringify({ queryText }),
      }),
  });
}

export function useUploadUrl() {
  return useMutation({
    mutationFn: (metadata?: Record<string, string>) =>
      apiFetch<{ uploadUrl: string; policyDocId: string; s3Key: string }>(
        "api/policies/upload-url",
        {
          method: "POST",
          body: JSON.stringify(metadata ?? {}),
        }
      ),
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (policy: Record<string, string>) =>
      apiFetch<PolicyDocument>("api/policies", {
        method: "POST",
        body: JSON.stringify(policy),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (policyDocId: string) =>
      apiFetch<{ deleted: boolean }>(`api/policies/${policyDocId}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useScoreApprovalPath() {
  return useMutation({
    mutationFn: (body: {
      drugName: string;
      indicationName: string;
      icd10Code?: string;
      patientProfile: Record<string, unknown>;
    }) =>
      apiFetch<ApprovalPathResult>("api/approval-path", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useGenerateMemo() {
  return useMutation({
    mutationFn: ({
      approvalPathId,
      payerName,
    }: {
      approvalPathId: string;
      payerName: string;
    }) =>
      apiFetch<{
        memoText: string;
        citations: unknown[];
        policyTitle: string;
        effectiveDate: string;
      }>(`api/approval-path/${approvalPathId}/memo`, {
        method: "POST",
        body: JSON.stringify({ payerName }),
      }),
  });
}

export interface DiscordanceSummary {
  drugName: string;
  payerName: string;
  discordanceScore: number | null;
  summary: string;
  changesCount?: number;
  status?: string;
  generatedAt?: string;
}

export function useDiscordances() {
  return useQuery({
    queryKey: ["discordances"],
    queryFn: () =>
      apiFetch<{ items: DiscordanceSummary[]; count: number }>(
        "api/discordance"
      ),
    retry: shouldRetry,
    staleTime: 30_000,
  });
}
