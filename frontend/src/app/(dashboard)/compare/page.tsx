"use client";

import React, { useState, useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, TableProperties, AlertCircle, RefreshCw } from "lucide-react";
import { useCompare, usePolicies } from "@/hooks/use-api";
import { buildApiUrl } from "@/lib/api";
import { useSearchParams } from "next/navigation";

const backendSevMap: Record<string, string> = {
    most_restrictive: "destructive",
    moderate: "warning",
    least_restrictive: "success",
    equivalent: "neutral",
    not_specified: "neutral",
};

const SeverityCellRenderer = (params: { value?: { val: string; sev: string } }) => {
    const data = params.value;
    if (!data) return null;

    let bgClass = "bg-muted/20 text-muted-foreground";
    let borderClass = "border-border";

    if (data.sev === "destructive") {
        bgClass = "bg-destructive/20 text-destructive";
        borderClass = "border-destructive/30";
    } else if (data.sev === "warning") {
        bgClass = "bg-warning/20 text-warning";
        borderClass = "border-warning/30";
    } else if (data.sev === "success") {
        bgClass = "bg-success/20 text-success";
        borderClass = "border-success/30";
    }

    return (
        <div className="flex items-center h-full w-full py-1">
            <div className={`px-3 py-1.5 min-h-[32px] flex items-center rounded-md border ${bgClass} ${borderClass} w-full text-xs font-semibold leading-tight shadow-sm`}>
                {data.val || "—"}
            </div>
        </div>
    );
};

export default function ComparisonMatrixPage() {
    const searchParams = useSearchParams();
    const initialDrug = searchParams.get("drug") ?? "infliximab";

    const [selectedDrug, setSelectedDrug] = useState(initialDrug);
    const [selectedIndication, setSelectedIndication] = useState("");

    const { data: policiesData, isLoading: loadingPolicies } = usePolicies({ limit: 100 });
    const { data: compareData, isLoading: loadingMatrix, error, refetch } = useCompare(
        selectedDrug,
        selectedIndication || undefined
    );

    // Extract unique drug names from policies for the dropdown
    const drugList = useMemo(() => {
        if (!policiesData?.items?.length) return [];
        const drugs = new Set<string>();
        policiesData.items.forEach(p => { if (p.drugName) drugs.add(p.drugName); });
        return Array.from(drugs).sort();
    }, [policiesData]);

    // Map API response to AG Grid shape
    const rowData = useMemo(() => {
        if (!compareData?.dimensions?.length) return [];
        return compareData.dimensions.map((dim) => {
            const row: Record<string, unknown> = { dimension: dim.label || dim.key };
            for (const v of dim.values) {
                row[v.payerName] = {
                    val: v.value,
                    sev: backendSevMap[v.severity] || "neutral",
                };
            }
            return row;
        });
    }, [compareData]);

    const columnDefs = useMemo(() => {
        if (!compareData?.payers?.length) return null;
        return [
            {
                field: "dimension",
                headerName: "Dimension",
                pinned: "left" as const,
                width: 200,
                cellClass: "font-semibold text-primary-text bg-card",
            },
            ...compareData.payers.map((payer) => ({
                field: payer,
                headerName: payer,
                width: 250,
                cellRenderer: SeverityCellRenderer,
            })),
        ];
    }, [compareData]);

    // Fallback static columns when no API data
    const fallbackCols = useMemo(() => [
        { field: "dimension", headerName: "Dimension", pinned: "left" as const, width: 200, cellClass: "font-semibold text-primary-text bg-card" },
        { field: "uhc", headerName: "UnitedHealthcare", width: 250, cellRenderer: SeverityCellRenderer },
        { field: "aetna", headerName: "Aetna", width: 250, cellRenderer: SeverityCellRenderer },
        { field: "cigna", headerName: "Cigna", width: 250, cellRenderer: SeverityCellRenderer },
    ], []);

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
                            onChange={(e) => setSelectedDrug(e.target.value)}
                        >
                            {drugList.length > 0 ? (
                                drugList.map(d => <option key={d} value={d}>{d}</option>)
                            ) : (
                                <>
                                    <option value="infliximab">Infliximab</option>
                                    <option value="adalimumab">Adalimumab</option>
                                    <option value="ustekinumab">Ustekinumab</option>
                                </>
                            )}
                        </select>
                    )}
                </div>
                <div className="w-64 space-y-2">
                    <Label>Select Indication</Label>
                    <select
                        className="flex h-10 w-full items-center rounded-md border border-input bg-card px-3 py-2 text-sm text-primary-text"
                        value={selectedIndication}
                        onChange={(e) => setSelectedIndication(e.target.value)}
                    >
                        <option value="">All Indications</option>
                        <option value="Rheumatoid Arthritis">Rheumatoid Arthritis</option>
                        <option value="Crohn's Disease">Crohn&apos;s Disease</option>
                        <option value="Psoriatic Arthritis">Psoriatic Arthritis</option>
                        <option value="Plaque Psoriasis">Plaque Psoriasis</option>
                        <option value="Ulcerative Colitis">Ulcerative Colitis</option>
                    </select>
                </div>
                <div className="flex items-end gap-2 ml-auto">
                    <Button
                        variant="outline"
                        className="bg-card"
                        onClick={() => refetch()}
                        disabled={loadingMatrix}
                    >
                        <RefreshCw className={`mr-2 h-4 w-4 ${loadingMatrix ? "animate-spin" : ""}`} />
                        {loadingMatrix ? "Loading..." : "Compare"}
                    </Button>
                    <Button variant="outline" className="bg-card" onClick={handleExport} disabled={!compareData?.payers?.length}>
                        <Download className="mr-2 h-4 w-4" /> Export CSV
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive shrink-0">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error instanceof Error ? error.message : "Failed to load comparison matrix"}
                </div>
            )}

            {loadingMatrix ? (
                <div className="flex-1 space-y-3">
                    {[0, 1, 2, 3, 4].map(i => (
                        <Skeleton key={i} className="h-14 w-full" />
                    ))}
                </div>
            ) : compareData?.message && rowData.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center space-y-2">
                        <TableProperties className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm text-muted-foreground">{compareData.message}</p>
                        <p className="text-xs text-muted-foreground/60">Upload payer policies to generate a comparison matrix.</p>
                    </div>
                </div>
            ) : rowData.length > 0 ? (
                <div className="ag-theme-alpine-dark flex-1 w-full rounded-md border border-border overflow-hidden custom-ag-grid">
                    <AgGridReact
                        rowData={rowData}
                        columnDefs={columnDefs || fallbackCols}
                        defaultColDef={defaultColDef}
                        rowHeight={60}
                        suppressMovableColumns={true}
                        domLayout="normal"
                    />
                </div>
            ) : (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center space-y-2">
                        <TableProperties className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm text-muted-foreground">Select a drug and click Compare to load the matrix.</p>
                    </div>
                </div>
            )}

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
