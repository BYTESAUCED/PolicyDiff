"use client";

import React, { useState, useMemo, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
    Download, TableProperties, AlertCircle, RefreshCw,
    Shield, ShieldAlert, ShieldCheck, ChevronDown,
    ArrowUpDown, Info, X, CheckCircle2, Minus,
    TrendingUp, BarChart3, Layers
} from "lucide-react";
import { useCompare, usePolicies } from "@/hooks/use-api";
import { buildApiUrl } from "@/lib/api";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "motion/react";

/* ─── Severity config ─────────────────────────────────────────────────────── */

type SeverityKey = "most_restrictive" | "moderate" | "least_restrictive" | "equivalent" | "not_specified";

const SEVERITY_CONFIG: Record<SeverityKey, {
    label: string;
    color: string;
    bg: string;
    bgHover: string;
    border: string;
    text: string;
    icon: React.ComponentType<{ className?: string }>;
    dot: string;
}> = {
    most_restrictive: {
        label: "Most Restrictive",
        color: "#ef4444",
        bg: "bg-red-500/10 dark:bg-red-500/15",
        bgHover: "hover:bg-red-500/20 dark:hover:bg-red-500/25",
        border: "border-red-500/20 dark:border-red-400/20",
        text: "text-red-700 dark:text-red-400",
        icon: ShieldAlert,
        dot: "bg-red-500",
    },
    moderate: {
        label: "Moderate",
        color: "#eab308",
        bg: "bg-amber-500/10 dark:bg-amber-500/15",
        bgHover: "hover:bg-amber-500/20 dark:hover:bg-amber-500/25",
        border: "border-amber-500/20 dark:border-amber-400/20",
        text: "text-amber-700 dark:text-amber-400",
        icon: Shield,
        dot: "bg-amber-500",
    },
    least_restrictive: {
        label: "Least Restrictive",
        color: "#22c55e",
        bg: "bg-emerald-500/10 dark:bg-emerald-500/15",
        bgHover: "hover:bg-emerald-500/20 dark:hover:bg-emerald-500/25",
        border: "border-emerald-500/20 dark:border-emerald-400/20",
        text: "text-emerald-700 dark:text-emerald-400",
        icon: ShieldCheck,
        dot: "bg-emerald-500",
    },
    equivalent: {
        label: "Equivalent",
        color: "#6b7280",
        bg: "bg-gray-500/5 dark:bg-gray-500/10",
        bgHover: "hover:bg-gray-500/10 dark:hover:bg-gray-500/15",
        border: "border-gray-500/10 dark:border-gray-400/10",
        text: "text-gray-600 dark:text-gray-400",
        icon: Minus,
        dot: "bg-gray-400",
    },
    not_specified: {
        label: "Not Specified",
        color: "#6b7280",
        bg: "bg-gray-500/5 dark:bg-gray-500/10",
        bgHover: "hover:bg-gray-500/10 dark:hover:bg-gray-500/15",
        border: "border-gray-500/10 dark:border-gray-400/10",
        text: "text-gray-500 dark:text-gray-500",
        icon: Minus,
        dot: "bg-gray-400",
    },
};

function getSeverityConfig(severity: string) {
    return SEVERITY_CONFIG[severity as SeverityKey] || SEVERITY_CONFIG.not_specified;
}

/* ─── Payer score helper ──────────────────────────────────────────────────── */

function computePayerScores(
    dimensions: { key: string; label: string; values: { payerName: string; value: string; severity: string }[] }[],
    payers: string[]
) {
    const scores: Record<string, { payer: string; restrictive: number; moderate: number; relaxed: number; total: number }> = {};

    payers.forEach(p => {
        scores[p] = { payer: p, restrictive: 0, moderate: 0, relaxed: 0, total: 0 };
    });

    dimensions.forEach(dim => {
        dim.values.forEach(v => {
            if (!scores[v.payerName]) return;
            scores[v.payerName].total++;
            if (v.severity === "most_restrictive") scores[v.payerName].restrictive++;
            else if (v.severity === "moderate") scores[v.payerName].moderate++;
            else if (v.severity === "least_restrictive") scores[v.payerName].relaxed++;
        });
    });

    return payers.map(p => scores[p]);
}

/* ─── Cell tooltip ────────── */

function CellTooltip({ children, content }: { children: React.ReactNode; content: string }) {
    const [show, setShow] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    return (
        <div
            className="relative"
            onMouseEnter={() => {
                timeoutRef.current = setTimeout(() => setShow(true), 400);
            }}
            onMouseLeave={() => {
                clearTimeout(timeoutRef.current);
                setShow(false);
            }}
        >
            {children}
            <AnimatePresence>
                {show && content && (
                    <motion.div
                        initial={{ opacity: 0, y: 4, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 4, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg bg-[#1c1c1e] dark:bg-[#2a2a2e] text-white text-xs leading-relaxed shadow-xl border border-white/10 max-w-[280px] whitespace-normal pointer-events-none"
                    >
                        {content}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#1c1c1e] dark:border-t-[#2a2a2e]" />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

/* ─── Detail panel ────────── */

function DimensionDetailPanel({
    dimension,
    onClose,
}: {
    dimension: { key: string; label: string; values: { payerName: string; value: string; severity: string }[] };
    onClose: () => void;
}) {
    return (
        <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
        >
            <div className="mx-4 mb-4 rounded-xl border border-border bg-card/50 dark:bg-card/80 p-5 backdrop-blur-sm">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <Layers className="h-4 w-4 text-muted-foreground" />
                        <h4 className="text-sm font-semibold text-foreground">{dimension.label}</h4>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-md hover:bg-muted transition-colors cursor-pointer"
                    >
                        <X className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                </div>
                <div className="grid gap-3">
                    {dimension.values.map((v) => {
                        const sev = getSeverityConfig(v.severity);
                        const Icon = sev.icon;
                        return (
                            <div
                                key={v.payerName}
                                className={cn(
                                    "flex items-start gap-3 rounded-lg border px-4 py-3 transition-all",
                                    sev.bg, sev.border
                                )}
                            >
                                <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", sev.text)} />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-medium text-foreground">{v.payerName}</span>
                                        <Badge
                                            className={cn(
                                                "text-[10px] px-1.5 py-0 h-4 border",
                                                sev.bg, sev.border, sev.text
                                            )}
                                        >
                                            {sev.label}
                                        </Badge>
                                    </div>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {v.value || "—"}
                                    </p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </motion.div>
    );
}

/* ─── Main page ───────────────────────────────────────────────────────────── */

export default function ComparisonMatrixPage() {
    const searchParams = useSearchParams();
    const initialDrug = searchParams.get("drug") ?? "";

    const [selectedDrug, setSelectedDrug] = useState(initialDrug);
    const [selectedIndication, setSelectedIndication] = useState("");
    const [expandedDimension, setExpandedDimension] = useState<string | null>(null);
    const [hoveredCell, setHoveredCell] = useState<{ dim: string; payer: string } | null>(null);
    const [sortBy, setSortBy] = useState<"default" | "restrictive">("default");

    const { data: policiesData, isLoading: loadingPolicies } = usePolicies({ limit: 100 });
    const { data: compareData, isLoading: loadingMatrix, error, refetch } = useCompare(
        selectedDrug,
        selectedIndication || undefined
    );

    const primaryHcpcs = compareData?.hcpcsCode ?? null;

    // Extract unique drug names from policies for the dropdown
    const drugList = useMemo(() => {
        if (!policiesData?.items?.length) return [];
        const drugs = new Set<string>();
        policiesData.items.forEach(p => { if (p.drugName) drugs.add(p.drugName); });
        return Array.from(drugs).sort();
    }, [policiesData]);

    // Payer restrictiveness scores
    const payerScores = useMemo(() => {
        if (!compareData?.dimensions?.length || !compareData?.payers?.length) return [];
        return computePayerScores(compareData.dimensions, compareData.payers);
    }, [compareData]);

    // Sort dimensions
    const sortedDimensions = useMemo(() => {
        if (!compareData?.dimensions) return [];
        const dims = [...compareData.dimensions];
        if (sortBy === "restrictive") {
            dims.sort((a, b) => {
                const aRed = a.values.filter(v => v.severity === "most_restrictive").length;
                const bRed = b.values.filter(v => v.severity === "most_restrictive").length;
                return bRed - aRed;
            });
        }
        return dims;
    }, [compareData, sortBy]);

    // Overall restrictiveness summary
    const overallSummary = useMemo(() => {
        if (!compareData?.dimensions?.length) return null;
        let totalCells = 0;
        let restrictive = 0;
        let moderate = 0;
        let relaxed = 0;
        compareData.dimensions.forEach(dim => {
            dim.values.forEach(v => {
                totalCells++;
                if (v.severity === "most_restrictive") restrictive++;
                else if (v.severity === "moderate") moderate++;
                else if (v.severity === "least_restrictive") relaxed++;
            });
        });
        return { totalCells, restrictive, moderate, relaxed };
    }, [compareData]);

    const handleExport = useCallback(() => {
        if (!selectedDrug) return;
        const url = buildApiUrl("/api/compare/export", { drug: selectedDrug });
        window.open(url, "_blank");
    }, [selectedDrug]);

    const handleExportCSVLocal = useCallback(() => {
        if (!compareData?.dimensions?.length || !compareData?.payers?.length) return;
        const headers = ["Dimension", ...compareData.payers];
        const rows = compareData.dimensions.map(dim => {
            const cells = [dim.label || dim.key];
            compareData.payers.forEach(payer => {
                const val = dim.values.find(v => v.payerName === payer);
                cells.push(val ? `${val.value} (${val.severity})` : "—");
            });
            return cells;
        });
        const csv = [headers, ...rows].map(row => row.map(c => `"${(c || "").replace(/"/g, '""')}"`).join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${selectedDrug}_comparison_matrix.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }, [compareData, selectedDrug]);

    const hasData = !!compareData?.dimensions?.length && !!compareData?.payers?.length;

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {/* ── Header ── */}
            <div className="shrink-0 px-6 pt-6 pb-4 space-y-4 border-b border-border">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3">
                            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#ea580c]/10 dark:bg-[#ea580c]/15">
                                <TableProperties className="h-5 w-5 text-[#ea580c]" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                                    Comparison Matrix
                                </h1>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    Cross-payer evaluation of policy criteria restrictiveness
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Legend */}
                    <div className="flex items-center gap-4 bg-card/80 dark:bg-card/60 backdrop-blur-sm px-4 py-2.5 rounded-xl border border-border">
                        {(["most_restrictive", "moderate", "least_restrictive", "equivalent"] as SeverityKey[]).map((key) => {
                            const config = SEVERITY_CONFIG[key];
                            return (
                                <div key={key} className="flex items-center gap-1.5">
                                    <div className={cn("w-2.5 h-2.5 rounded-full", config.dot)} />
                                    <span className="text-[11px] text-muted-foreground font-medium">{config.label}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Filters */}
                <div className="flex gap-4 flex-wrap items-end">
                    <div className="w-56 space-y-1.5">
                        <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Drug</Label>
                        {loadingPolicies ? (
                            <Skeleton className="h-9 w-full" />
                        ) : (
                            <select
                                id="compare-drug-select"
                                className="flex h-9 w-full items-center rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground font-mono focus:outline-none focus:ring-2 focus:ring-ring/30 transition-all"
                                value={selectedDrug}
                                onChange={(e) => setSelectedDrug(e.target.value)}
                            >
                                <option value="">— pick a drug —</option>
                                {drugList.map(d => <option key={d} value={d}>{d}</option>)}
                            </select>
                        )}
                    </div>
                    <div className="w-56 space-y-1.5">
                        <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Indication</Label>
                        <select
                            id="compare-indication-select"
                            className="flex h-9 w-full items-center rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 transition-all"
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
                        {primaryHcpcs && (
                            <span className="text-xs font-mono px-2 py-1 rounded bg-primary/10 text-primary border border-primary/20">
                                {primaryHcpcs}
                            </span>
                        )}
                    </div>
                    <div className="flex items-end gap-2 ml-auto">
                        <Button
                            variant="outline"
                            size="sm"
                            className="bg-card h-9 cursor-pointer"
                            onClick={() => refetch()}
                            disabled={loadingMatrix}
                        >
                            <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", loadingMatrix && "animate-spin")} />
                            {loadingMatrix ? "Loading…" : "Compare"}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            className="bg-card h-9 cursor-pointer"
                            onClick={hasData ? handleExportCSVLocal : handleExport}
                            disabled={!hasData}
                        >
                            <Download className="mr-1.5 h-3.5 w-3.5" /> Export CSV
                        </Button>
                    </div>
                </div>
            </div>

            {/* ── Error ── */}
            {error && (
                <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive shrink-0">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error instanceof Error ? error.message : "Failed to load comparison matrix"}
                </div>
            )}

            {/* ── Content ── */}
            <div className="flex-1 overflow-y-auto min-h-0 px-6 py-5 space-y-5">
                {loadingMatrix ? (
                    <LoadingState />
                ) : compareData?.message && !hasData ? (
                    <EmptyMessage message={compareData.message} />
                ) : hasData ? (
                    <>
                        {/* Payer summary cards */}
                        <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${compareData.payers.length}, 1fr)` }}>
                            {payerScores.map((score, i) => (
                                <motion.div
                                    key={score.payer}
                                    initial={{ opacity: 0, y: 12 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.06, duration: 0.35, ease: "easeOut" }}
                                >
                                    <PayerScoreCard score={score} />
                                </motion.div>
                            ))}
                        </div>

                        {/* Overall summary bar */}
                        {overallSummary && (
                            <motion.div
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2, duration: 0.3 }}
                                className="flex items-center gap-4 px-4 py-3 rounded-xl border border-border bg-card/50 dark:bg-card/30"
                            >
                                <BarChart3 className="h-4 w-4 text-muted-foreground shrink-0" />
                                <span className="text-xs font-medium text-muted-foreground">
                                    {compareData.dimensions.length} dimensions across {compareData.payers.length} payers
                                </span>
                                <div className="flex-1" />
                                <div className="flex items-center gap-3">
                                    <MiniStat color="bg-red-500" label="Restrictive" count={overallSummary.restrictive} />
                                    <MiniStat color="bg-amber-500" label="Moderate" count={overallSummary.moderate} />
                                    <MiniStat color="bg-emerald-500" label="Relaxed" count={overallSummary.relaxed} />
                                </div>
                                <div className="ml-2 flex items-center gap-1.5">
                                    <button
                                        onClick={() => setSortBy(sortBy === "default" ? "restrictive" : "default")}
                                        className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer px-2 py-1 rounded-md hover:bg-muted"
                                    >
                                        <ArrowUpDown className="h-3 w-3" />
                                        {sortBy === "restrictive" ? "Default order" : "Sort by severity"}
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* The Matrix */}
                        <motion.div
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3, duration: 0.4 }}
                            className="rounded-xl border border-border overflow-hidden bg-card/50 dark:bg-card/30"
                        >
                            {/* Matrix header */}
                            <div
                                className="grid border-b-2 border-border bg-card dark:bg-[#141416]"
                                style={{
                                    gridTemplateColumns: `220px repeat(${compareData.payers.length}, 1fr)`,
                                }}
                            >
                                <div className="px-4 py-3 flex items-center gap-2">
                                    <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                                        Dimension
                                    </span>
                                </div>
                                {compareData.payers.map((payer) => (
                                    <div
                                        key={payer}
                                        className="px-4 py-3 flex items-center justify-center border-l border-border"
                                    >
                                        <span className="text-xs font-bold uppercase tracking-widest text-foreground text-center">
                                            {payer}
                                        </span>
                                    </div>
                                ))}
                            </div>

                            {/* Matrix rows */}
                            {sortedDimensions.map((dim, dimIdx) => (
                                <React.Fragment key={dim.key}>
                                    <div
                                        className={cn(
                                            "grid transition-colors cursor-pointer group",
                                            dimIdx % 2 === 0
                                                ? "bg-transparent"
                                                : "bg-muted/20 dark:bg-white/[0.02]",
                                            expandedDimension === dim.key && "bg-muted/40 dark:bg-white/[0.04]"
                                        )}
                                        style={{
                                            gridTemplateColumns: `220px repeat(${compareData.payers.length}, 1fr)`,
                                        }}
                                        onClick={() =>
                                            setExpandedDimension(expandedDimension === dim.key ? null : dim.key)
                                        }
                                    >
                                        {/* Dimension label */}
                                        <div className="px-4 py-3.5 flex items-center gap-2 border-r border-border/50">
                                            <ChevronDown
                                                className={cn(
                                                    "h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform duration-200",
                                                    expandedDimension === dim.key && "rotate-180"
                                                )}
                                            />
                                            <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors truncate">
                                                {dim.label || dim.key}
                                            </span>
                                        </div>

                                        {/* Payer cells */}
                                        {compareData.payers.map((payer) => {
                                            const cellData = dim.values.find(v => v.payerName === payer);
                                            const severity = cellData?.severity || "not_specified";
                                            const config = getSeverityConfig(severity);
                                            const isHovered = hoveredCell?.dim === dim.key && hoveredCell?.payer === payer;

                                            return (
                                                <CellTooltip key={payer} content={cellData?.value || ""}>
                                                    <div
                                                        className={cn(
                                                            "px-3 py-3.5 border-l border-border/50 flex items-center transition-all duration-150",
                                                            config.bgHover,
                                                            isHovered && config.bg,
                                                        )}
                                                        onMouseEnter={() => setHoveredCell({ dim: dim.key, payer })}
                                                        onMouseLeave={() => setHoveredCell(null)}
                                                    >
                                                        <div
                                                            className={cn(
                                                                "flex items-center gap-2 px-3 py-2 rounded-lg border w-full min-h-[36px] transition-all duration-200",
                                                                config.bg,
                                                                config.border,
                                                                isHovered && "shadow-sm scale-[1.01]"
                                                            )}
                                                        >
                                                            <div className={cn("w-1.5 h-1.5 rounded-full shrink-0", config.dot)} />
                                                            <span className={cn("text-xs font-medium leading-tight line-clamp-2", config.text)}>
                                                                {cellData?.value || "—"}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </CellTooltip>
                                            );
                                        })}
                                    </div>

                                    {/* Expanded detail panel */}
                                    <AnimatePresence>
                                        {expandedDimension === dim.key && (
                                            <DimensionDetailPanel
                                                dimension={dim}
                                                onClose={() => setExpandedDimension(null)}
                                            />
                                        )}
                                    </AnimatePresence>
                                </React.Fragment>
                            ))}
                        </motion.div>

                        {/* Footer info */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground pb-2">
                            <div className="flex items-center gap-1.5">
                                <Info className="h-3 w-3" />
                                <span>
                                    Showing {compareData.drug}
                                    {compareData.indication ? ` — ${compareData.indication}` : ""}
                                    {" · "}Click a row to expand dimension details
                                </span>
                            </div>
                            <span className="font-mono text-muted-foreground/50">
                                {compareData.payers.length} payers × {compareData.dimensions.length} dimensions
                            </span>
                        </div>
                    </>
                ) : (
                    <EmptyState />
                )}
            </div>
        </div>
    );
}

/* ─── Sub-components ──────────────────────────────────────────────────────── */

function PayerScoreCard({ score }: { score: { payer: string; restrictive: number; moderate: number; relaxed: number; total: number } }) {
    const restrictivePercent = score.total > 0 ? Math.round((score.restrictive / score.total) * 100) : 0;
    const moderatePercent = score.total > 0 ? Math.round((score.moderate / score.total) * 100) : 0;
    const relaxedPercent = score.total > 0 ? Math.round((score.relaxed / score.total) * 100) : 0;

    let overallBadge: { label: string; variant: "destructive" | "warning" | "success" | "secondary" } = {
        label: "Mixed",
        variant: "secondary",
    };
    if (restrictivePercent >= 50) overallBadge = { label: "Restrictive", variant: "destructive" };
    else if (relaxedPercent >= 50) overallBadge = { label: "Permissive", variant: "success" };
    else if (moderatePercent >= 50) overallBadge = { label: "Moderate", variant: "warning" };

    return (
        <div className="rounded-xl border border-border bg-card p-4 space-y-3 hover:shadow-md transition-shadow group">
            <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground truncate">{score.payer}</span>
                <Badge variant={overallBadge.variant} className="text-[10px] h-5 shrink-0">
                    {overallBadge.label}
                </Badge>
            </div>

            {/* Stacked bar */}
            <div className="h-2 rounded-full overflow-hidden bg-muted/50 flex">
                {restrictivePercent > 0 && (
                    <div
                        className="bg-red-500 transition-all duration-500 ease-out"
                        style={{ width: `${restrictivePercent}%` }}
                    />
                )}
                {moderatePercent > 0 && (
                    <div
                        className="bg-amber-500 transition-all duration-500 ease-out"
                        style={{ width: `${moderatePercent}%` }}
                    />
                )}
                {relaxedPercent > 0 && (
                    <div
                        className="bg-emerald-500 transition-all duration-500 ease-out"
                        style={{ width: `${relaxedPercent}%` }}
                    />
                )}
            </div>

            {/* Micro stats */}
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                    {score.restrictive}
                </span>
                <span className="flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                    {score.moderate}
                </span>
                <span className="flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    {score.relaxed}
                </span>
                <span className="ml-auto font-mono">{score.total} criteria</span>
            </div>
        </div>
    );
}

function MiniStat({ color, label, count }: { color: string; label: string; count: number }) {
    return (
        <div className="flex items-center gap-1.5">
            <div className={cn("w-2 h-2 rounded-full", color)} />
            <span className="text-[11px] text-muted-foreground">{count}</span>
        </div>
    );
}

function LoadingState() {
    return (
        <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
                {[0, 1, 2].map(i => (
                    <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
                        <div className="flex justify-between">
                            <Skeleton className="h-5 w-28" />
                            <Skeleton className="h-5 w-16" />
                        </div>
                        <Skeleton className="h-2 w-full rounded-full" />
                        <Skeleton className="h-3 w-20" />
                    </div>
                ))}
            </div>
            <Skeleton className="h-10 w-full rounded-xl" />
            {[0, 1, 2, 3, 4, 5].map(i => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
            ))}
        </div>
    );
}

function EmptyMessage({ message }: { message: string }) {
    return (
        <div className="flex-1 flex items-center justify-center py-20">
            <div className="text-center space-y-3">
                <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-muted/30 mx-auto">
                    <TableProperties className="h-7 w-7 text-muted-foreground/40" />
                </div>
                <p className="text-sm text-muted-foreground max-w-xs">{message}</p>
                <p className="text-xs text-muted-foreground/50">Upload payer policies to generate a comparison matrix.</p>
            </div>
        </div>
    );
}

function EmptyState() {
    return (
        <div className="flex-1 flex items-center justify-center py-20">
            <div className="text-center space-y-3">
                <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-muted/30 mx-auto">
                    <TableProperties className="h-7 w-7 text-muted-foreground/40" />
                </div>
                <p className="text-sm text-muted-foreground">Select a drug and click <span className="font-medium text-foreground">Compare</span> to load the matrix.</p>
                <p className="text-xs text-muted-foreground/50">The matrix compares policy criteria restrictiveness across payers.</p>
            </div>
        </div>
    );
}
