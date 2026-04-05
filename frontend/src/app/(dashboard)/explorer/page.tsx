"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
    Search, Filter, ChevronDown, ChevronRight, TableProperties,
    Loader2, Trash2Icon, AlertCircle, FileTextIcon,
} from "lucide-react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PolicyDoc {
    policyDocId: string;
    drugName?: string;
    payerName?: string;
    planType?: string;
    documentTitle?: string;
    effectiveDate?: string;
    extractionStatus?: string;
    createdAt?: string;
}

interface CriterionItem {
    criterionText: string;
    criterionType?: string;
    logicOperator?: string;
    requiredDrugsTriedFirst?: string[];
    stepTherapyMinCount?: number;
    prescriberType?: string;
}

interface CriteriaRecord {
    drugIndicationId?: string;
    drugName?: string;
    indicationName?: string;
    approvalPhase?: string;
    approvalDurationMonths?: number;
    initialAuthDurationMonths?: number;
    benefitType?: string;
    coveredStatus?: string;
    indicationICD10?: string[];
    initialAuthCriteria?: CriterionItem[];
    reauthorizationCriteria?: CriterionItem[];
    dosingPerIndication?: { indicationContext?: string; regimen?: string }[];
    preferredProducts?: { productName: string; rank: number }[];
    confidence?: number;
}

interface DrugGroup {
    drugName: string;
    policies: PolicyDoc[];
}

function groupByDrug(policies: PolicyDoc[]): DrugGroup[] {
    const map = new Map<string, PolicyDoc[]>();
    policies.forEach(p => {
        const key = p.drugName || p.documentTitle || "Unknown Policy";
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(p);
    });
    return Array.from(map.entries())
        .map(([drugName, policies]) => ({ drugName, policies }))
        .sort((a, b) => a.drugName.localeCompare(b.drugName));
}

function fuzzyMatch(query: string, target: string): number {
    const q = query.toLowerCase();
    const t = target.toLowerCase();
    if (t.includes(q)) return 1000 + (1000 - t.indexOf(q));
    let score = 0, qi = 0, lastIndex = -1, consecutive = 0;
    for (let ti = 0; ti < t.length && qi < q.length; ti++) {
        if (t[ti] === q[qi]) {
            consecutive = lastIndex === ti - 1 ? consecutive + 1 : 1;
            score += consecutive * 10 + Math.max(0, 20 - ti);
            lastIndex = ti;
            qi++;
        }
    }
    return qi === q.length ? score : 0;
}

function formatDate(iso?: string): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function phaseLabel(phase?: string): string {
    if (!phase) return "";
    const map: Record<string, string> = {
        initial: "Initial",
        continuation_1: "Continuation (1 prior)",
        continuation_2plus: "Continuation (2+ prior)",
    };
    return map[phase] ?? phase;
}

function phaseBadgeClass(phase?: string): string {
    if (phase === "initial") return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    if (phase === "continuation_1") return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    if (phase === "continuation_2plus") return "bg-purple-500/10 text-purple-400 border-purple-500/20";
    return "bg-muted text-muted-foreground";
}

type DrugActionType = "delete";

export default function DrugExplorerPage() {
    const [expandedDrugs, setExpandedDrugs] = useState<string[]>([]);
    const [expandedPolicies, setExpandedPolicies] = useState<string[]>([]);
    const [criteriaMap, setCriteriaMap] = useState<Record<string, CriteriaRecord[]>>({});
    const [loadingCriteria, setLoadingCriteria] = useState<Record<string, boolean>>({});
    const [searchQuery, setSearchQuery] = useState("");
    const [pendingAction, setPendingAction] = useState<{ id: string; type: DrugActionType } | null>(null);
    const [drugGroups, setDrugGroups] = useState<DrugGroup[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchPolicies = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiFetch<{ items: PolicyDoc[] }>("/api/policies");
            setDrugGroups(groupByDrug(data.items ?? []));
        } catch (e) {
            setError(e instanceof ApiError ? e.message : "Failed to load policies");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchPolicies(); }, [fetchPolicies]);

    const toggleDrug = (drugName: string) =>
        setExpandedDrugs(prev => prev.includes(drugName) ? prev.filter(d => d !== drugName) : [...prev, drugName]);

    const togglePolicy = async (policyDocId: string) => {
        setExpandedPolicies(prev =>
            prev.includes(policyDocId) ? prev.filter(p => p !== policyDocId) : [...prev, policyDocId]
        );
        if (!criteriaMap[policyDocId] && !loadingCriteria[policyDocId]) {
            setLoadingCriteria(prev => ({ ...prev, [policyDocId]: true }));
            try {
                const data = await apiFetch<{ items: CriteriaRecord[] }>(`/api/policies/${policyDocId}/criteria`);
                setCriteriaMap(prev => ({ ...prev, [policyDocId]: data.items ?? [] }));
            } catch {
                setCriteriaMap(prev => ({ ...prev, [policyDocId]: [] }));
            } finally {
                setLoadingCriteria(prev => ({ ...prev, [policyDocId]: false }));
            }
        }
    };

    const handleDelete = async (policyDocId: string) => {
        setPendingAction({ id: policyDocId, type: "delete" });
        try {
            await apiFetch(`/api/policies/${policyDocId}`, { method: "DELETE" });
            await fetchPolicies();
        } finally {
            setPendingAction(null);
        }
    };

    const filtered = searchQuery.trim()
        ? drugGroups
            .map(g => ({ group: g, score: fuzzyMatch(searchQuery, g.drugName) }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ group }) => group)
        : drugGroups;

    return (
        <div className="p-6 max-w-7xl space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Drug Explorer</h2>
                    <p className="text-muted-text mt-1">Browse extracted drug criteria across all ingested payer policies.</p>
                </div>
                <div className="flex gap-2 w-full md:w-auto">
                    <div className="relative w-full md:w-64">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-text" />
                        <Input placeholder="Search drug name..." className="pl-9 bg-card border-border"
                            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                    </div>
                    <Button variant="outline" className="shrink-0 bg-card" onClick={fetchPolicies} disabled={loading}>
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Filter className="h-4 w-4 mr-2" />Refresh</>}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />{error}
                </div>
            )}

            <div className="rounded-lg border border-border">
                <Table>
                    <TableHeader>
                        <TableRow className="border-b border-border hover:bg-transparent">
                            <TableHead className="h-12 w-10 px-4" />
                            <TableHead className="h-12 px-4 font-medium">Drug Name</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Payers</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Policies</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Last Updated</TableHead>
                            <TableHead className="h-12 w-[100px] px-4 font-medium">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            Array.from({ length: 4 }).map((_, i) => (
                                <TableRow key={i} className="border-border">
                                    {Array.from({ length: 6 }).map((_, j) => (
                                        <TableCell key={j} className="h-16 px-4"><Skeleton className="h-4 w-24" /></TableCell>
                                    ))}
                                </TableRow>
                            ))
                        ) : filtered.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="h-32 text-center text-sm text-muted-foreground">
                                    {drugGroups.length === 0
                                        ? "No policies uploaded yet. Upload a policy PDF to get started."
                                        : "No drugs match your search."}
                                </TableCell>
                            </TableRow>
                        ) : filtered.map((group) => {
                            const expanded = expandedDrugs.includes(group.drugName);
                            const payers = [...new Set(group.policies.map(p => p.payerName).filter(Boolean))] as string[];
                            const latestDate = group.policies.map(p => p.effectiveDate || p.createdAt || "").sort().reverse()[0];

                            return (
                                <React.Fragment key={group.drugName}>
                                    {/* Drug row */}
                                    <TableRow
                                        className={`cursor-pointer hover:bg-muted/50 border-border ${expanded ? "bg-muted/20" : ""}`}
                                        onClick={() => toggleDrug(group.drugName)}
                                    >
                                        <TableCell className="h-16 px-4">
                                            {expanded
                                                ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                                : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                                        </TableCell>
                                        <TableCell className="h-16 px-4 font-mono font-semibold">{group.drugName}</TableCell>
                                        <TableCell className="h-16 px-4">
                                            <div className="flex flex-wrap gap-1.5">
                                                {payers.map(p => (
                                                    <span key={p} className="text-[11px] text-muted-foreground/70 border border-border rounded px-1.5 py-0.5 font-mono">{p}</span>
                                                ))}
                                            </div>
                                        </TableCell>
                                        <TableCell className="h-16 px-4 font-mono text-sm">{group.policies.length}</TableCell>
                                        <TableCell className="h-16 px-4 text-sm text-muted-foreground">{formatDate(latestDate)}</TableCell>
                                        <TableCell className="h-16 px-4" onClick={e => e.stopPropagation()}>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" asChild>
                                                            <Link href={`/compare?drug=${encodeURIComponent(group.drugName.toLowerCase())}`}>
                                                                <TableProperties className="size-4" />
                                                            </Link>
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>Compare across payers</TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </TableCell>
                                    </TableRow>

                                    {/* Expanded: per-policy cards */}
                                    {expanded && (
                                        <TableRow className="border-border hover:bg-transparent">
                                            <TableCell colSpan={6} className="p-0 pb-2">
                                                <div className="ml-10 mr-4 my-3 space-y-3">
                                                    {group.policies.map((policy) => {
                                                        const policyExpanded = expandedPolicies.includes(policy.policyDocId);
                                                        const criteria = criteriaMap[policy.policyDocId] ?? [];
                                                        const loadingC = loadingCriteria[policy.policyDocId];
                                                        const busy = pendingAction?.id === policy.policyDocId;

                                                        // Group criteria by indicationName
                                                        const byIndication = criteria.reduce<Record<string, CriteriaRecord[]>>((acc, c) => {
                                                            const key = c.indicationName || "Unknown Indication";
                                                            if (!acc[key]) acc[key] = [];
                                                            acc[key].push(c);
                                                            return acc;
                                                        }, {});

                                                        return (
                                                            <div key={policy.policyDocId} className="rounded-lg border border-border bg-card overflow-hidden">
                                                                {/* Policy header */}
                                                                <div
                                                                    className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/30 transition-colors"
                                                                    onClick={() => togglePolicy(policy.policyDocId)}
                                                                >
                                                                    <div className="flex items-center gap-3">
                                                                        {policyExpanded
                                                                            ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                                                            : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                                                                        <span className="font-medium text-sm">{policy.payerName || "Unknown Payer"}</span>
                                                                        {policy.planType && (
                                                                            <span className="text-xs text-muted-foreground font-mono">{policy.planType}</span>
                                                                        )}
                                                                        {policy.effectiveDate && (
                                                                            <span className="text-xs text-muted-foreground">eff. {policy.effectiveDate}</span>
                                                                        )}
                                                                    </div>
                                                                    <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                                                                        <Badge
                                                                            variant="outline"
                                                                            className={`border text-[10px] h-5 ${
                                                                                policy.extractionStatus === "complete" ? "bg-green-500/10 text-green-400 border-green-500/20"
                                                                                : policy.extractionStatus === "failed" ? "bg-red-500/10 text-red-400 border-red-500/20"
                                                                                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                                                            }`}
                                                                        >
                                                                            {policy.extractionStatus || "pending"}
                                                                        </Badge>
                                                                        {criteria.length > 0 && (
                                                                            <span className="text-xs text-muted-foreground font-mono">{criteria.length} records</span>
                                                                        )}
                                                                        <TooltipProvider>
                                                                            <Tooltip>
                                                                                <TooltipTrigger asChild>
                                                                                    <Button
                                                                                        variant="ghost" size="icon"
                                                                                        className="h-6 w-6 text-destructive hover:bg-destructive/10"
                                                                                        disabled={busy}
                                                                                        onClick={() => handleDelete(policy.policyDocId)}
                                                                                    >
                                                                                        {busy ? <Loader2 className="size-3 animate-spin" /> : <Trash2Icon className="size-3" />}
                                                                                    </Button>
                                                                                </TooltipTrigger>
                                                                                <TooltipContent>Delete policy</TooltipContent>
                                                                            </Tooltip>
                                                                        </TooltipProvider>
                                                                    </div>
                                                                </div>

                                                                {/* Criteria panel */}
                                                                {policyExpanded && (
                                                                    <div className="border-t border-border px-4 py-4 space-y-4">
                                                                        {loadingC ? (
                                                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading criteria...
                                                                            </div>
                                                                        ) : criteria.length === 0 ? (
                                                                            <p className="text-sm text-muted-foreground">No criteria extracted yet.</p>
                                                                        ) : (
                                                                            Object.entries(byIndication).map(([indication, records]) => (
                                                                                <div key={indication} className="space-y-2">
                                                                                    {/* Indication header */}
                                                                                    <div className="flex items-center gap-2">
                                                                                        <FileTextIcon className="h-3.5 w-3.5 text-primary shrink-0" />
                                                                                        <span className="text-sm font-semibold">{indication}</span>
                                                                                        {records[0]?.indicationICD10?.length ? (
                                                                                            <span className="text-[10px] font-mono text-muted-foreground">
                                                                                                {records[0].indicationICD10.slice(0, 3).join(", ")}
                                                                                                {records[0].indicationICD10.length > 3 ? ` +${records[0].indicationICD10.length - 3}` : ""}
                                                                                            </span>
                                                                                        ) : null}
                                                                                    </div>

                                                                                    {/* Phase records */}
                                                                                    <div className="ml-5 space-y-2">
                                                                                        {records.map((rec, ri) => (
                                                                                            <div key={ri} className="rounded-md border border-border bg-background p-3 space-y-2">
                                                                                                <div className="flex items-center gap-2 flex-wrap">
                                                                                                    {rec.approvalPhase && (
                                                                                                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${phaseBadgeClass(rec.approvalPhase)}`}>
                                                                                                            {phaseLabel(rec.approvalPhase)}
                                                                                                        </span>
                                                                                                    )}
                                                                                                    {rec.approvalDurationMonths && (
                                                                                                        <span className="text-[10px] text-muted-foreground font-mono">
                                                                                                            {rec.approvalDurationMonths} mo
                                                                                                        </span>
                                                                                                    )}
                                                                                                    {rec.coveredStatus && rec.coveredStatus !== "covered" && (
                                                                                                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded border bg-red-500/10 text-red-400 border-red-500/20">
                                                                                                            {rec.coveredStatus}
                                                                                                        </span>
                                                                                                    )}
                                                                                                    {rec.confidence !== undefined && (
                                                                                                        <span className="text-[10px] text-muted-foreground ml-auto font-mono">
                                                                                                            conf {Math.round(rec.confidence * 100)}%
                                                                                                        </span>
                                                                                                    )}
                                                                                                </div>

                                                                                                {/* Criteria list */}
                                                                                                {rec.initialAuthCriteria && rec.initialAuthCriteria.length > 0 && (
                                                                                                    <ul className="space-y-1">
                                                                                                        {rec.initialAuthCriteria.map((c, ci) => (
                                                                                                            <li key={ci} className="flex items-start gap-2 text-xs text-muted-foreground">
                                                                                                                <span className="shrink-0 mt-0.5 text-[9px] font-bold text-primary/60 uppercase tracking-widest">
                                                                                                                    {c.logicOperator || "AND"}
                                                                                                                </span>
                                                                                                                <span>{c.criterionText}</span>
                                                                                                            </li>
                                                                                                        ))}
                                                                                                    </ul>
                                                                                                )}

                                                                                                {/* Preferred products */}
                                                                                                {rec.preferredProducts && rec.preferredProducts.length > 0 && (
                                                                                                    <div className="flex flex-wrap gap-1 pt-1">
                                                                                                        {rec.preferredProducts.map((pp, pi) => (
                                                                                                            <span key={pi} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                                                                                                #{pp.rank} {pp.productName}
                                                                                                            </span>
                                                                                                        ))}
                                                                                                    </div>
                                                                                                )}
                                                                                            </div>
                                                                                        ))}
                                                                                    </div>
                                                                                </div>
                                                                            ))
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
