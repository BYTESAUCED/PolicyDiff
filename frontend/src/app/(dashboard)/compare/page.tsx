"use client";

import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, TableProperties, AlertCircle, RefreshCw } from "lucide-react";
import { useCompare, usePolicies } from "@/hooks/use-api";
import { buildApiUrl } from "@/lib/api";
import { useSearchParams } from "next/navigation";

const SEV_CLASSES: Record<string, string> = {
    most_restrictive: "bg-destructive/15 text-destructive border-destructive/30",
    moderate: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    least_restrictive: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    equivalent: "bg-muted/20 text-muted-foreground border-border",
    not_specified: "bg-muted/20 text-muted-foreground border-border",
};

export default function ComparisonMatrixPage() {
    const searchParams = useSearchParams();
    const initialDrug = searchParams.get("drug") ?? "";

    const [selectedDrug, setSelectedDrug] = useState(initialDrug);
    const [selectedIndication, setSelectedIndication] = useState("");

    const { data: policiesData, isLoading: loadingPolicies } = usePolicies({ limit: 100 });
    const { data: compareData, isLoading: loadingMatrix, error, refetch } = useCompare(
        selectedDrug,
        selectedIndication || undefined
    );

    const drugList = useMemo(() => {
        if (!policiesData?.items?.length) return [];
        const drugs = new Set<string>();
        policiesData.items.forEach(p => { if (p.drugName) drugs.add(p.drugName); });
        return Array.from(drugs).sort();
    }, [policiesData]);

    const payers = compareData?.payers ?? [];
    const dimensions = compareData?.dimensions ?? [];

    const handleExport = () => {
        if (!selectedDrug) return;
        const url = buildApiUrl("/api/compare/export", { drug: selectedDrug });
        window.open(url, "_blank");
    };

    return (
        <div className="h-full flex flex-col p-6 space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 shrink-0">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Comparison Matrix</h2>
                    <p className="text-muted-foreground mt-1">Cross-payer evaluation of policy criteria restrictiveness.</p>
                </div>
                <div className="flex items-center gap-3 bg-card p-2 px-4 rounded-lg border border-border text-xs">
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-destructive inline-block" />Most Restrictive</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block" />Moderate</span>
                    <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />Least Restrictive</span>
                </div>
            </div>

            {/* Controls */}
            <div className="flex gap-4 shrink-0 flex-wrap items-end">
                <div className="w-64 space-y-2">
                    <Label>Select Drug</Label>
                    {loadingPolicies ? <Skeleton className="h-10 w-full" /> : (
                        <select
                            className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm font-mono"
                            value={selectedDrug}
                            onChange={e => setSelectedDrug(e.target.value)}
                        >
                            <option value="">— pick a drug —</option>
                            {drugList.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                    )}
                </div>
                <div className="w-64 space-y-2">
                    <Label>Indication (optional)</Label>
                    <input
                        className="flex h-10 w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
                        placeholder="e.g. Rheumatoid Arthritis"
                        value={selectedIndication}
                        onChange={e => setSelectedIndication(e.target.value)}
                    />
                </div>
                <div className="flex gap-2 ml-auto">
                    <Button variant="outline" className="bg-card" onClick={() => refetch()} disabled={loadingMatrix || !selectedDrug}>
                        <RefreshCw className={`mr-2 h-4 w-4 ${loadingMatrix ? "animate-spin" : ""}`} />
                        {loadingMatrix ? "Loading..." : "Compare"}
                    </Button>
                    <Button variant="outline" className="bg-card" onClick={handleExport} disabled={!payers.length}>
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

            {/* Matrix */}
            {loadingMatrix ? (
                <div className="flex-1 space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
                </div>
            ) : dimensions.length > 0 ? (
                <div className="flex-1 overflow-auto rounded-lg border border-border">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border bg-muted/30">
                                <th className="px-5 py-3 text-left font-semibold text-xs uppercase tracking-wider w-48 sticky left-0 bg-muted/30">Dimension</th>
                                {payers.map(p => (
                                    <th key={p} className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider min-w-[200px]">{p}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {dimensions.map(dim => {
                                const byPayer = Object.fromEntries(dim.values.map(v => [v.payerName, v]));
                                return (
                                    <tr key={dim.key} className="hover:bg-muted/20">
                                        <td className="px-5 py-3 font-medium text-xs sticky left-0 bg-card border-r border-border">{dim.label || dim.key}</td>
                                        {payers.map(p => {
                                            const v = byPayer[p];
                                            const cls = SEV_CLASSES[v?.severity] ?? SEV_CLASSES.not_specified;
                                            return (
                                                <td key={p} className="px-4 py-3">
                                                    {v ? (
                                                        <span className={`inline-block px-2.5 py-1 rounded-md border text-xs font-medium ${cls}`}>
                                                            {v.value || "—"}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted-foreground/40 text-xs">—</span>
                                                    )}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center space-y-2">
                        <TableProperties className="h-10 w-10 text-muted-foreground/30 mx-auto" />
                        <p className="text-sm text-muted-foreground">
                            {compareData?.message ?? "Select a drug and click Compare to load the matrix."}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
