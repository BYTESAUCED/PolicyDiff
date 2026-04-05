"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
    Search,
    Filter,
    ChevronDown,
    ChevronRight,
    TableProperties,
    FileTextIcon,
    Loader2,
    Trash2Icon,
    AlertCircle,
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

interface CriteriaItem {
    criteriaId?: string;
    indicationName?: string;
    benefitType?: string;
    stepTherapyCount?: number;
}

// Group policies by drug name
interface DrugGroup {
    drugName: string;
    policies: PolicyDoc[];
}

function groupByDrug(policies: PolicyDoc[]): DrugGroup[] {
    const map = new Map<string, PolicyDoc[]>();
    policies.forEach(p => {
        const key = p.drugName || "Unknown Drug";
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

type DrugActionType = "compare" | "view" | "delete";

export default function DrugExplorerPage() {
    const [expandedRows, setExpandedRows] = useState<string[]>([]);
    const [expandedCriteria, setExpandedCriteria] = useState<Record<string, CriteriaItem[]>>({});
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

    useEffect(() => {
        fetchPolicies();
    }, [fetchPolicies]);

    const toggleRow = async (drugName: string) => {
        setExpandedRows(prev =>
            prev.includes(drugName) ? prev.filter(r => r !== drugName) : [...prev, drugName]
        );
    };

    const loadCriteria = async (policyDocId: string) => {
        if (expandedCriteria[policyDocId] || loadingCriteria[policyDocId]) return;
        setLoadingCriteria(prev => ({ ...prev, [policyDocId]: true }));
        try {
            const data = await apiFetch<{ items: CriteriaItem[] }>(`/api/policies/${policyDocId}/criteria`);
            setExpandedCriteria(prev => ({ ...prev, [policyDocId]: data.items ?? [] }));
        } catch {
            setExpandedCriteria(prev => ({ ...prev, [policyDocId]: [] }));
        } finally {
            setLoadingCriteria(prev => ({ ...prev, [policyDocId]: false }));
        }
    };

    const handleDelete = async (policyDocId: string) => {
        setPendingAction({ id: policyDocId, type: "delete" });
        try {
            await apiFetch(`/api/policies/${policyDocId}`, { method: "DELETE" });
            await fetchPolicies();
        } catch {
            // Silently fail — user can retry
        } finally {
            setPendingAction(null);
        }
    };

    const isActionPending = (type: DrugActionType, id: string) =>
        pendingAction?.id === id && pendingAction.type === type;
    const isBusy = (id: string) => pendingAction?.id === id;

    const filtered = searchQuery.trim()
        ? drugGroups
            .map(g => ({
                group: g,
                score: fuzzyMatch(searchQuery, g.drugName),
            }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ group }) => group)
        : drugGroups;

    return (
        <div className="p-6 max-w-7xl space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Drug Explorer</h2>
                    <p className="text-muted-text mt-1">
                        Browse all extracted drug criteria across ingested payer policies.
                    </p>
                </div>
                <div className="flex gap-2 w-full md:w-auto">
                    <div className="relative w-full md:w-64">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-text" />
                        <Input
                            placeholder="Search drug name..."
                            className="pl-9 bg-card border-border"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" className="shrink-0 bg-card" onClick={fetchPolicies} disabled={loading}>
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Filter className="h-4 w-4 mr-2" />}
                        {!loading && "Refresh"}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
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
                            <TableHead className="h-12 w-[140px] px-4 font-medium">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            Array.from({ length: 4 }).map((_, i) => (
                                <TableRow key={i} className="border-border">
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-4" /></TableCell>
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-28" /></TableCell>
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-48" /></TableCell>
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-8" /></TableCell>
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-24" /></TableCell>
                                    <TableCell className="h-16 px-4"><Skeleton className="h-4 w-20" /></TableCell>
                                </TableRow>
                            ))
                        ) : filtered.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="h-32 text-center text-sm text-muted-foreground">
                                    {drugGroups.length === 0
                                        ? "No policies uploaded yet. Upload a policy PDF to get started."
                                        : "No drugs match your search."
                                    }
                                </TableCell>
                            </TableRow>
                        ) : (
                            filtered.map((group) => {
                                const expanded = expandedRows.includes(group.drugName);
                                const payers = [...new Set(group.policies.map(p => p.payerName).filter(Boolean))] as string[];
                                const latestDate = group.policies
                                    .map(p => p.effectiveDate || p.createdAt || "")
                                    .sort()
                                    .reverse()[0];

                                return (
                                    <React.Fragment key={group.drugName}>
                                        <TableRow
                                            className={`cursor-pointer hover:bg-muted/50 border-border ${expanded ? "bg-muted/30" : ""}`}
                                            onClick={() => toggleRow(group.drugName)}
                                        >
                                            <TableCell className="h-16 px-4">
                                                {expanded
                                                    ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                                    : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                                }
                                            </TableCell>
                                            <TableCell className="h-16 px-4 font-mono font-medium">{group.drugName}</TableCell>
                                            <TableCell className="h-16 px-4">
                                                <div className="flex flex-wrap gap-1.5">
                                                    {payers.map(payer => (
                                                        <span
                                                            key={payer}
                                                            className="text-[11px] text-muted-foreground/70 border border-border rounded px-1.5 py-0.5 font-mono"
                                                        >
                                                            {payer}
                                                        </span>
                                                    ))}
                                                </div>
                                            </TableCell>
                                            <TableCell className="h-16 px-4 font-mono text-sm">{group.policies.length}</TableCell>
                                            <TableCell className="h-16 px-4 text-sm text-muted-foreground">{formatDate(latestDate)}</TableCell>
                                            <TableCell className="h-16 px-4" onClick={(e) => e.stopPropagation()}>
                                                <TooltipProvider>
                                                    <div className="flex items-center gap-1">
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                                                    asChild
                                                                >
                                                                    <Link href={`/compare?drug=${encodeURIComponent(group.drugName.toLowerCase())}`}>
                                                                        <TableProperties className="size-4" />
                                                                    </Link>
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Compare</TooltipContent>
                                                        </Tooltip>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                                                    onClick={() => toggleRow(group.drugName)}
                                                                >
                                                                    <FileTextIcon className="size-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>View Details</TooltipContent>
                                                        </Tooltip>
                                                    </div>
                                                </TooltipProvider>
                                            </TableCell>
                                        </TableRow>

                                        {expanded && (
                                            <TableRow className="border-border hover:bg-transparent">
                                                <TableCell colSpan={6} className="p-0">
                                                    <div className="p-6 border-l-2 border-primary ml-[22px] my-2">
                                                        <div className="flex items-center justify-between mb-4">
                                                            <h4 className="font-semibold text-sm">Policy Documents ({group.policies.length})</h4>
                                                        </div>
                                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                                            {group.policies.map((policy) => {
                                                                const criteria = expandedCriteria[policy.policyDocId];
                                                                const loadingC = loadingCriteria[policy.policyDocId];
                                                                const busy = isBusy(policy.policyDocId);
                                                                return (
                                                                    <div key={policy.policyDocId} className="p-3 rounded-md border border-border text-sm space-y-2">
                                                                        <div className="flex items-center justify-between">
                                                                            <span className="font-medium truncate">{policy.payerName || "Unknown Payer"}</span>
                                                                            <Badge
                                                                                variant="outline"
                                                                                className={`border-0 text-[10px] h-4 ${
                                                                                    policy.extractionStatus === "complete"
                                                                                        ? "bg-green-500/10 text-green-400"
                                                                                        : policy.extractionStatus === "failed"
                                                                                            ? "bg-red-500/10 text-red-400"
                                                                                            : "bg-amber-500/10 text-amber-400"
                                                                                }`}
                                                                            >
                                                                                {policy.extractionStatus || "pending"}
                                                                            </Badge>
                                                                        </div>
                                                                        {policy.planType && (
                                                                            <div className="text-xs text-muted-foreground font-mono">{policy.planType}</div>
                                                                        )}
                                                                        {policy.effectiveDate && (
                                                                            <div className="flex justify-between text-muted-foreground text-xs">
                                                                                <span>Effective</span>
                                                                                <span className="font-mono">{policy.effectiveDate}</span>
                                                                            </div>
                                                                        )}
                                                                        {criteria && (
                                                                            <div className="flex justify-between text-muted-foreground text-xs">
                                                                                <span>Indications</span>
                                                                                <span className="font-mono">{criteria.length}</span>
                                                                            </div>
                                                                        )}
                                                                        <div className="flex items-center justify-between">
                                                                            <button
                                                                                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-sky-400 transition-colors"
                                                                                onClick={() => loadCriteria(policy.policyDocId)}
                                                                                disabled={loadingC}
                                                                            >
                                                                                {loadingC
                                                                                    ? <Loader2 className="h-3 w-3 animate-spin" />
                                                                                    : <ChevronRight className="h-3 w-3" />
                                                                                }
                                                                                View criteria
                                                                            </button>
                                                                            <TooltipProvider>
                                                                                <Tooltip>
                                                                                    <TooltipTrigger asChild>
                                                                                        <Button
                                                                                            variant="ghost"
                                                                                            size="icon"
                                                                                            className="h-6 w-6 text-destructive hover:bg-destructive/10"
                                                                                            disabled={busy}
                                                                                            onClick={() => handleDelete(policy.policyDocId)}
                                                                                        >
                                                                                            {isActionPending("delete", policy.policyDocId)
                                                                                                ? <Loader2 className="size-3 animate-spin" />
                                                                                                : <Trash2Icon className="size-3" />
                                                                                            }
                                                                                        </Button>
                                                                                    </TooltipTrigger>
                                                                                    <TooltipContent>Delete</TooltipContent>
                                                                                </Tooltip>
                                                                            </TooltipProvider>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </React.Fragment>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
