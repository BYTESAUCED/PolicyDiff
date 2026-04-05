"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
    Search,
    ChevronDown,
    ChevronRight,
    TableProperties,
    FileTextIcon,
    Loader2,
    Trash2Icon,
    AlertCircle,
    RefreshCw,
    ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { usePolicies, useDeletePolicy, type PolicyDocument } from "@/hooks/use-api";
import { apiFetch } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DosingEntry {
    indicationContext?: string;
    regimen?: string;
    maxDoseMg?: number | null;
}

interface CriterionEntry {
    criterionText?: string;
    criterionType?: string;
    rawExcerpt?: string;
    logicOperator?: string;
    requiredDrugsTriedFirst?: string[];
    stepTherapyMinCount?: number;
}

interface CriteriaItem {
    criteriaId?: string;
    drugIndicationId?: string;
    drugName?: string;
    indicationName?: string;
    hcpcsCode?: string;
    benefitType?: string;
    stepTherapyCount?: number;
    stepTherapyDrugs?: string[];
    trialDuration?: string;
    prescriberRequirement?: string;
    approvalDurationMonths?: number;
    dosingPerIndication?: DosingEntry[] | string;
    universalCriteria?: CriterionEntry[] | string[];
    initialAuthCriteria?: CriterionEntry[];
    reauthorizationCriteria?: CriterionEntry[];
    productName?: string;
    productGroup?: string;
    brandNames?: string[];
    confidenceScore?: number;
    confidence?: number;
    approvalPhase?: string;
    coveredStatus?: string;
    indicationICD10?: string[];
    needsReview?: boolean;
    reviewReasons?: string[];
    preferredProducts?: { rank: number; productName: string }[];
}

interface DrugGroup {
    drugName: string;
    policies: PolicyDocument[];
}

function groupByDrug(policies: PolicyDocument[]): DrugGroup[] {
    const map = new Map<string, PolicyDocument[]>();
    policies.forEach(p => {
        const key = p.drugName || p.documentTitle || "Unknown Drug";
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

    const { data: policiesData, isLoading, error, refetch } = usePolicies({ limit: 100 });
    const deletePolicyMutation = useDeletePolicy();

    const drugGroups = policiesData?.items?.length
        ? groupByDrug(policiesData.items.filter(p => p.drugName || p.documentTitle || p.payerName))
        : [];

    const toggleRow = (drugName: string) => {
        const isExpanding = !expandedRows.includes(drugName);
        setExpandedRows(prev =>
            prev.includes(drugName) ? prev.filter(r => r !== drugName) : [...prev, drugName]
        );
        // Auto-load criteria for all policies in this group when expanding
        if (isExpanding) {
            const group = drugGroups.find(g => g.drugName === drugName);
            group?.policies.forEach(p => loadCriteria(p.policyDocId));
        }
    };

    const loadCriteria = async (policyDocId: string) => {
        if (expandedCriteria[policyDocId] || loadingCriteria[policyDocId]) return;
        setLoadingCriteria(prev => ({ ...prev, [policyDocId]: true }));
        try {
            const data = await apiFetch<{ items: CriteriaItem[] }>(`api/policies/${policyDocId}/criteria`);
            setExpandedCriteria(prev => ({ ...prev, [policyDocId]: data.items ?? [] }));
        } catch {
            setExpandedCriteria(prev => ({ ...prev, [policyDocId]: [] }));
        } finally {
            setLoadingCriteria(prev => ({ ...prev, [policyDocId]: false }));
        }
    };

    const handleViewPdf = async (policyDocId: string) => {
        try {
            setPendingAction({ id: policyDocId, type: "view" });
            const p = drugGroups.flatMap(g => g.policies).find(p => p.policyDocId === policyDocId);
            const { downloadUrl } = await apiFetch<{ downloadUrl: string }>(`api/policies/${policyDocId}/download`);
            window.open(downloadUrl, "_blank", "noopener,noreferrer");
        } catch (err) {
            console.error("Failed to generate PDF download URL", err);
            alert("No PDF found for this policy or link generation failed.");
        } finally {
            setPendingAction(null);
        }
    };

    const handleDelete = (policyDocId: string) => {
        setPendingAction({ id: policyDocId, type: "delete" });
        deletePolicyMutation.mutate(policyDocId, {
            onSettled: () => setPendingAction(null),
        });
    };

    const isActionPending = (type: DrugActionType, id: string) =>
        pendingAction?.id === id && pendingAction.type === type;
    const isBusy = (id: string) => pendingAction?.id === id;

    const filtered = searchQuery.trim()
        ? drugGroups
            .map(g => ({
                group: g,
                score: Math.max(
                    fuzzyMatch(searchQuery, g.drugName),
                    // also match on any J-code found in expanded criteria
                    ...Object.values(expandedCriteria)
                        .flat()
                        .filter(c => c.drugName?.toLowerCase() === g.drugName.toLowerCase() && c.hcpcsCode)
                        .map(c => fuzzyMatch(searchQuery, c.hcpcsCode!)),
                ),
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
                    <Button variant="outline" className="shrink-0 bg-card" onClick={() => refetch()} disabled={isLoading}>
                        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                        {!isLoading && "Refresh"}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error instanceof Error ? error.message : "Failed to load policies"}
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
                        {isLoading ? (
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
                                const payers = [...new Set(group.policies.map(p => p.payerName).filter(Boolean))];
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
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                                    disabled={group.policies.some(p => isBusy(p.policyDocId))}
                                                                    onClick={() => {
                                                                        if (confirm(`Delete ${group.policies.length === 1 ? "this policy" : `all ${group.policies.length} policies`} for ${group.drugName}?`)) {
                                                                            group.policies.forEach(p => handleDelete(p.policyDocId));
                                                                        }
                                                                    }}
                                                                >
                                                                    {group.policies.some(p => isActionPending("delete", p.policyDocId))
                                                                        ? <Loader2 className="size-4 animate-spin" />
                                                                        : <Trash2Icon className="size-4" />
                                                                    }
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Delete</TooltipContent>
                                                        </Tooltip>
                                                    </div>
                                                </TooltipProvider>
                                            </TableCell>
                                        </TableRow>

                                        {expanded && (
                                            <TableRow className="border-border hover:bg-transparent">
                                                <TableCell colSpan={6} className="p-0">
                                                    <div className="px-8 py-6 border-l-2 border-primary ml-[22px] my-2 space-y-6">
                                                        <h4 className="font-semibold text-base">Policy Documents ({group.policies.length})</h4>

                                                        {group.policies.map((policy) => {
                                                            const criteria = expandedCriteria[policy.policyDocId];
                                                            const loadingC = loadingCriteria[policy.policyDocId];
                                                            const busy = isBusy(policy.policyDocId);
                                                            return (
                                                                <div key={policy.policyDocId} className="rounded-lg border border-border overflow-hidden">
                                                                    {/* Policy header bar */}
                                                                    <div className="flex items-center justify-between px-5 py-3 bg-muted/30 border-b border-border">
                                                                        <div className="flex items-center gap-3">
                                                                            <span className="font-semibold text-sm">{policy.payerName || "Unknown Payer"}</span>
                                                                            {policy.documentTitle && (
                                                                                <span className="text-sm text-muted-foreground">— {policy.documentTitle}</span>
                                                                            )}
                                                                            <Badge
                                                                                variant="outline"
                                                                                className={`border-0 text-[10px] h-5 px-2 ${
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
                                                                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                                                            {policy.planType && <span className="font-mono">{policy.planType}</span>}
                                                                            {policy.effectiveDate && <span>Eff. <span className="font-mono">{policy.effectiveDate}</span></span>}
                                                                            <span>Indications: <span className="font-mono text-foreground">{criteria ? criteria.length : policy.indicationsFound ?? "—"}</span></span>
                                                                            {policy.confidenceSummary?.averageConfidence != null && (
                                                                                <span>Confidence: <span className="font-mono text-foreground">{Math.round(policy.confidenceSummary.averageConfidence * 100)}%</span></span>
                                                                            )}
                                                                            <TooltipProvider>
                                                                                <Tooltip>
                                                                                    <TooltipTrigger asChild>
                                                                                        <Button 
                                                                                            variant="ghost" 
                                                                                            size="icon" 
                                                                                            className="h-6 w-6 ml-2 text-muted-foreground hover:text-sky-400"
                                                                                            disabled={isBusy(policy.policyDocId)}
                                                                                            onClick={() => handleViewPdf(policy.policyDocId)}
                                                                                        >
                                                                                            {isActionPending("view", policy.policyDocId) 
                                                                                                ? <Loader2 className="size-3 animate-spin" />
                                                                                                : <ExternalLink className="size-3" />
                                                                                            }
                                                                                        </Button>
                                                                                    </TooltipTrigger>
                                                                                    <TooltipContent>View Original PDF</TooltipContent>
                                                                                </Tooltip>
                                                                            </TooltipProvider>
                                                                        </div>
                                                                    </div>

                                                                    {/* Criteria table */}
                                                                    {loadingC && !criteria && (
                                                                        <div className="px-5 py-4 space-y-2">
                                                                            <Skeleton className="h-4 w-full" />
                                                                            <Skeleton className="h-4 w-3/4" />
                                                                        </div>
                                                                    )}
                                                                    {criteria && criteria.length > 0 && (
                                                                        <div className="divide-y divide-border">
                                                                            {criteria.map((c, ci) => (
                                                                                <div key={ci} className="px-5 py-4 space-y-3">
                                                                                    {/* Indication header */}
                                                                                    <div className="flex items-center justify-between">
                                                                                        <div className="flex items-center gap-3 flex-wrap">
                                                                                            <p className="text-sm font-semibold">{c.indicationName || "Unknown Indication"}</p>
                                                                                            {c.hcpcsCode && (
                                                                                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 tracking-wider">
                                                                                                    {c.hcpcsCode}
                                                                                                </span>
                                                                                            )}
                                                                                            {c.benefitType && (
                                                                                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">{c.benefitType}</span>
                                                                                            )}
                                                                                            {c.approvalPhase && (
                                                                                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">{c.approvalPhase.replace(/_/g, " ")}</span>
                                                                                            )}
                                                                                            {c.coveredStatus && (
                                                                                                <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${c.coveredStatus === "covered" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>{c.coveredStatus}</span>
                                                                                            )}
                                                                                            {c.needsReview && (
                                                                                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400">needs review</span>
                                                                                            )}
                                                                                        </div>
                                                                                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                                                            {c.indicationICD10 && c.indicationICD10.length > 0 && (
                                                                                                <span className="font-mono">ICD-10: {c.indicationICD10.join(", ")}</span>
                                                                                            )}
                                                                                            {(c.confidence ?? c.confidenceScore) != null && (
                                                                                                <span className="font-mono">{Math.round(((c.confidence ?? c.confidenceScore) as number) * 100)}% conf</span>
                                                                                            )}
                                                                                        </div>
                                                                                    </div>

                                                                                    {/* Key fields grid */}
                                                                                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                                                                                        {c.initialAuthCriteria && c.initialAuthCriteria.length > 0 && (
                                                                                            <div className="col-span-2 lg:col-span-4">
                                                                                                <span className="text-xs text-muted-foreground block mb-1">Initial Auth Criteria</span>
                                                                                                <ul className="space-y-1">
                                                                                                    {c.initialAuthCriteria.map((cr, cri) => (
                                                                                                        <li key={cri} className="text-sm font-mono flex items-start gap-2">
                                                                                                            <span className="text-muted-foreground shrink-0">{cr.logicOperator || "•"}</span>
                                                                                                            <span>{cr.criterionText}</span>
                                                                                                        </li>
                                                                                                    ))}
                                                                                                </ul>
                                                                                            </div>
                                                                                        )}
                                                                                        {c.approvalDurationMonths != null && (
                                                                                            <div>
                                                                                                <span className="text-xs text-muted-foreground">Auth Duration</span>
                                                                                                <p className="font-mono">{c.approvalDurationMonths} months</p>
                                                                                            </div>
                                                                                        )}
                                                                                        {c.prescriberRequirement && (
                                                                                            <div>
                                                                                                <span className="text-xs text-muted-foreground">Prescriber</span>
                                                                                                <p className="font-mono">{c.prescriberRequirement}</p>
                                                                                            </div>
                                                                                        )}
                                                                                        {c.trialDuration && (
                                                                                            <div>
                                                                                                <span className="text-xs text-muted-foreground">Trial Duration</span>
                                                                                                <p className="font-mono">{c.trialDuration}</p>
                                                                                            </div>
                                                                                        )}
                                                                                        {c.productName && (
                                                                                            <div>
                                                                                                <span className="text-xs text-muted-foreground">Product</span>
                                                                                                <p className="font-mono">{c.productName}</p>
                                                                                            </div>
                                                                                        )}
                                                                                    </div>

                                                                                    {/* Dosing (array of objects) */}
                                                                                    {c.dosingPerIndication && (
                                                                                        <div>
                                                                                            <span className="text-xs text-muted-foreground block mb-1">Dosing</span>
                                                                                            {typeof c.dosingPerIndication === "string" ? (
                                                                                                <p className="text-sm font-mono">{c.dosingPerIndication}</p>
                                                                                            ) : (
                                                                                                <div className="space-y-1">
                                                                                                    {c.dosingPerIndication.map((d, di) => (
                                                                                                        <p key={di} className="text-sm font-mono">
                                                                                                            {d.regimen}{d.maxDoseMg ? ` (max ${d.maxDoseMg}mg)` : ""}
                                                                                                            {d.indicationContext ? <span className="text-muted-foreground"> — {d.indicationContext}</span> : null}
                                                                                                        </p>
                                                                                                    ))}
                                                                                                </div>
                                                                                            )}
                                                                                        </div>
                                                                                    )}

                                                                                    {/* Universal criteria (array of objects or strings) */}
                                                                                    {c.universalCriteria && c.universalCriteria.length > 0 && (
                                                                                        <div>
                                                                                            <span className="text-xs text-muted-foreground block mb-1">Universal Criteria</span>
                                                                                            <ul className="space-y-1">
                                                                                                {c.universalCriteria.map((uc, uci) => (
                                                                                                    <li key={uci} className="text-sm font-mono flex items-start gap-2">
                                                                                                        <span className="text-muted-foreground shrink-0">•</span>
                                                                                                        <span>{typeof uc === "string" ? uc : uc.criterionText || JSON.stringify(uc)}</span>
                                                                                                    </li>
                                                                                                ))}
                                                                                            </ul>
                                                                                        </div>
                                                                                    )}

                                                                                    {/* Preferred products & brand names */}
                                                                                    {((c.preferredProducts && c.preferredProducts.length > 0) || (c.brandNames && c.brandNames.length > 0)) && (
                                                                                        <div className="flex flex-wrap gap-3">
                                                                                            {c.preferredProducts && c.preferredProducts.length > 0 && (
                                                                                                <div className="flex items-center gap-1.5">
                                                                                                    <span className="text-xs text-muted-foreground">Preferred:</span>
                                                                                                    {c.preferredProducts.map((pp, ppi) => (
                                                                                                        <span key={ppi} className="text-xs font-mono px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">{pp.productName}</span>
                                                                                                    ))}
                                                                                                </div>
                                                                                            )}
                                                                                            {c.brandNames && c.brandNames.length > 0 && (
                                                                                                <div className="flex items-center gap-1.5">
                                                                                                    <span className="text-xs text-muted-foreground">Brands:</span>
                                                                                                    {c.brandNames.map((bn, bni) => (
                                                                                                        <span key={bni} className="text-xs font-mono px-2 py-0.5 rounded border border-border text-muted-foreground">{bn}</span>
                                                                                                    ))}
                                                                                                </div>
                                                                                            )}
                                                                                        </div>
                                                                                    )}

                                                                                    {/* Review reasons */}
                                                                                    {c.reviewReasons && c.reviewReasons.length > 0 && (
                                                                                        <div className="rounded bg-amber-500/5 border border-amber-500/20 px-3 py-2">
                                                                                            <span className="text-xs text-amber-400 font-medium block mb-1">Review Reasons</span>
                                                                                            {c.reviewReasons.map((r, ri) => (
                                                                                                <p key={ri} className="text-xs font-mono text-amber-400/80">{r}</p>
                                                                                            ))}
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    )}
                                                                    {criteria && criteria.length === 0 && (
                                                                        <div className="px-5 py-4 text-sm text-muted-foreground/60 italic">
                                                                            No criteria extracted yet
                                                                        </div>
                                                                    )}

                                                                    {/* Footer actions */}
                                                                    <div className="flex items-center justify-between px-5 py-2 bg-muted/10 border-t border-border">
                                                                        <button
                                                                            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-sky-400 transition-colors"
                                                                            onClick={() => loadCriteria(policy.policyDocId)}
                                                                            disabled={loadingC}
                                                                        >
                                                                                {loadingC
                                                                                    ? <Loader2 className="h-3 w-3 animate-spin" />
                                                                                    : <ChevronRight className="h-3 w-3" />
                                                                                }
                                                                                {criteria ? "Refresh criteria" : "View criteria"}
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
