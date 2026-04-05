"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { AgGridReact } from "ag-grid-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, TableProperties, AlertCircle, RefreshCw } from "lucide-react";
import { apiFetch, buildApiUrl, ApiError } from "@/lib/api";
import { useSearchParams } from "next/navigation";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PolicyItem {
    policyDocId: string;
    drugName?: string;
    payerName?: string;
    documentTitle?: string;
}

interface DimensionValue {
    payerName: string;
    value: string;
    severity: string;
}

interface Dimension {
    key: string;
    label: string;
    values: DimensionValue[];
}

interface CompareResponse {
    drug: string;
    indication: string;
    payers: string[];
    dimensions: Dimension[];
    message?: string;
    error?: string;
}

// ── Cell renderer ─────────────────────────────────────────────────────────────

const SeverityCellRenderer = (params: { value?: DimensionValue }) => {
    const data = params.value;
    if (!data) return null;

    let bgClass = "bg-muted/20 text-muted-foreground";
    let borderClass = "border-border";

    if (data.severity === "most_restrictive") {
        bgClass = "bg-destructive/20 text-destructive";
        borderClass = "border-destructive/30";
    } else if (data.severity === "moderate") {
        bgClass = "bg-warning/20 text-warning";
        borderClass = "border-warning/30";
    } else if (data.severity === "least_restrictive") {
        bgClass = "bg-success/20 text-success";
        borderClass = "border-success/30";
    }

    return (
        <div className="flex items-center h-full w-full py-1">
            <div className={`px-3 py-1.5 min-h-[32px] flex items-center rounded-md border ${bgClass} ${borderClass} w-full text-xs font-semibold leading-tight shadow-sm`}>
                {data.value || "—"}
            </div>
        </div>
    );
};

// ── Unique drug names from policies ──────────────────────────────────────────

function extractDrugs(policies: PolicyItem[]): string[] {
    const drugs = new Set<string>();
    policies.forEach(p => { if (p.drugName) drugs.add(p.drugName); });
    return Array.from(drugs).sort();
}

export default function ComparisonMatrixPage() {
    const searchParams = useSearchParams();
    const initialDrug = searchParams.get("drug") ?? "";

    const [policies, setPolicies] = useState<PolicyItem[]>([]);
    const [drugList, setDrugList] = useState<string[]>([]);
    const [selectedDrug, setSelectedDrug] = useState(initialDrug);
    const [matrixData, setMatrixData] = useState<CompareResponse | null>(null);
    const [loadingPolicies, setLoadingPolicies] = useState(true);
    const [loadingMatrix, setLoadingMatrix] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Load available policies to populate drug dropdown
    const loadPolicies = useCallback(async () => {
        setLoadingPolicies(true);
        try {
            const data = await apiFetch<{ items: PolicyItem[] }>("/api/policies");
            setPolicies(data.items ?? []);
            const drugs = extractDrugs(data.items ?? []);
            setDrugList(drugs);
            if (!selectedDrug && drugs.length > 0) {
                setSelectedDrug(drugs[0]);
            }
        } catch {
            // Non-critical — user can still type a drug name
        } finally {
            setLoadingPolicies(false);
        }
    }, [selectedDrug]);

    useEffect(() => {
        loadPolicies();
    }, [loadPolicies]);

    // Fetch comparison matrix when drug changes
    const fetchMatrix = useCallback(async (drug: string) => {
        if (!drug) return;
        setLoadingMatrix(true);
        setError(null);
        try {
            const data = await apiFetch<CompareResponse>("/api/compare", undefined, { drug });
            setMatrixData(data);
        } catch (e) {
            setError(e instanceof ApiError ? e.message : "Failed to load comparison matrix");
            setMatrixData(null);
        } finally {
            setLoadingMatrix(false);
        }
    }, []);

    useEffect(() => {
        if (selectedDrug) fetchMatrix(selectedDrug);
    }, [selectedDrug, fetchMatrix]);

    // Build AG Grid column defs from payers in response
    const columnDefs = useMemo(() => {
        if (!matrixData?.payers?.length) return [];
        const cols: object[] = [
            {
                field: "dimension",
                headerName: "Dimension",
                pinned: "left",
                width: 200,
                cellClass: "font-semibold text-primary-text bg-card",
            },
        ];
        matrixData.payers.forEach(payer => {
            cols.push({
                field: payer,
                headerName: payer,
                width: 250,
                cellRenderer: SeverityCellRenderer,
            });
        });
        return cols;
    }, [matrixData]);

    // Transform dimensions into row data keyed by payer
    const rowData = useMemo(() => {
        if (!matrixData?.dimensions) return [];
        return matrixData.dimensions.map(dim => {
            const row: Record<string, unknown> = { dimension: dim.label || dim.key };
            dim.values.forEach(v => {
                row[v.payerName] = { value: v.value, severity: v.severity };
            });
            return row;
        });
    }, [matrixData]);

    const defaultColDef = useMemo(() => ({
        resizable: true,
        sortable: true,
        filter: true,
        flex: 1,
        minWidth: 150,
    }), []);

    const handleExport = () => {
        if (!selectedDrug) return;
        const url = buildApiUrl("/api/compare/export", { drug: selectedDrug });
        window.open(url, "_blank");
    };

    return (
        <div className="h-full flex flex-col p-6 space-y-6">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 shrink-0">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Comparison Matrix</h2>
                    <p className="text-muted-text mt-1">
                        Cross-payer evaluation of policy criteria restrictiveness.
                    </p>
                </div>

                <div className="flex items-center gap-3 bg-card p-2 px-4 rounded-lg border border-border">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-destructive"></div>
                        <span className="text-xs text-muted-text">Most Restrictive</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-warning"></div>
                        <span className="text-xs text-muted-text">Moderate</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-success"></div>
                        <span className="text-xs text-muted-text">Least Restrictive</span>
                    </div>
                </div>
            </div>

            <div className="flex gap-4 shrink-0 flex-wrap">
                <div className="w-64 space-y-2">
                    <Label>Select Drug</Label>
                    {loadingPolicies ? (
                        <Skeleton className="h-10 w-full" />
                    ) : (
                        <select
                            className="flex h-10 w-full items-center rounded-md border border-input bg-card px-3 py-2 text-sm text-primary-text font-mono"
                            value={selectedDrug}
                            onChange={e => setSelectedDrug(e.target.value)}
                        >
                            {drugList.length > 0 ? (
                                drugList.map(d => <option key={d} value={d}>{d}</option>)
                            ) : (
                                // Fallback static list if no policies uploaded yet
                                <>
                                    <option value="infliximab">Infliximab</option>
                                    <option value="adalimumab">Adalimumab</option>
                                    <option value="ustekinumab">Ustekinumab</option>
                                </>
                            )}
                        </select>
                    )}
                </div>
                <div className="flex items-end gap-2 ml-auto">
                    <Button
                        variant="outline"
                        className="bg-card"
                        onClick={() => selectedDrug && fetchMatrix(selectedDrug)}
                        disabled={loadingMatrix}
                    >
                        <RefreshCw className={`mr-2 h-4 w-4 ${loadingMatrix ? "animate-spin" : ""}`} />
                        {loadingMatrix ? "Loading..." : "Compare"}
                    </Button>
                    <Button variant="outline" className="bg-card" onClick={handleExport} disabled={!matrixData?.payers?.length}>
                        <Download className="mr-2 h-4 w-4" /> Export CSV
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive shrink-0">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            {loadingMatrix ? (
                <div className="flex-1 space-y-3">
                    {[0, 1, 2, 3, 4].map(i => (
                        <Skeleton key={i} className="h-14 w-full" />
                    ))}
                </div>
            ) : matrixData?.message && rowData.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center space-y-2">
                        <TableProperties className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm text-muted-foreground">{matrixData.message}</p>
                        <p className="text-xs text-muted-foreground/60">Upload payer policies to generate a comparison matrix.</p>
                    </div>
                </div>
            ) : rowData.length > 0 ? (
                <div className="ag-theme-alpine-dark flex-1 w-full rounded-md border border-border overflow-hidden custom-ag-grid">
                    <AgGridReact
                        rowData={rowData}
                        columnDefs={columnDefs}
                        defaultColDef={defaultColDef}
                        rowHeight={60}
                        suppressMovableColumns={true}
                        domLayout="normal"
                    />
                </div>
            ) : !loadingMatrix && !error ? (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center space-y-2">
                        <TableProperties className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm text-muted-foreground">Select a drug and click Compare to load the matrix.</p>
                    </div>
                </div>
            ) : null}

            <style jsx global>{`
                .custom-ag-grid {
                    --ag-background-color: var(--card);
                    --ag-header-background-color: #0f0f0f;
                    --ag-border-color: var(--border);
                    --ag-row-border-color: var(--border);
                    --ag-odd-row-background-color: var(--background);
                    --ag-font-family: inherit;
                    --ag-font-size: 14px;
                    --ag-header-foreground-color: #f1f5f9;
                    --ag-secondary-foreground-color: #94a3b8;
                    --ag-data-color: #f1f5f9;
                    --ag-pinned-column-shadow: none;
                }
                .custom-ag-grid .ag-header-cell {
                    font-weight: 600;
                    border-bottom: 2px solid var(--border);
                }
                .custom-ag-grid .ag-cell {
                    display: flex;
                    align-items: center;
                }
                .custom-ag-grid .ag-row-hover,
                .custom-ag-grid .ag-row-focus {
                    background-color: inherit !important;
                }
                .custom-ag-grid .ag-root-wrapper {
                    border: none;
                }
            `}</style>
        </div>
    );
}
