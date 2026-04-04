"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
} from "lucide-react";
import Link from "next/link";

interface Drug {
    id: string;
    name: string;
    brandNames: string;
    payers: string[];
    indications: number;
    lastUpdated: string;
}

type DrugActionType = "compare" | "view" | "delete";

const drugsData: Drug[] = [
    {
        id: "d1",
        name: "Infliximab",
        brandNames: "Remicade, Inflectra, Avsola",
        payers: ["UnitedHealthcare", "Aetna", "Cigna", "Anthem"],
        indications: 14,
        lastUpdated: "Feb 12, 2026",
    },
    {
        id: "d2",
        name: "Adalimumab",
        brandNames: "Humira, Amjevita, Cyltezo",
        payers: ["UnitedHealthcare", "Aetna", "Cigna"],
        indications: 11,
        lastUpdated: "Feb 10, 2026",
    },
    {
        id: "d3",
        name: "Ustekinumab",
        brandNames: "Stelara, Wezlana",
        payers: ["UnitedHealthcare", "Aetna", "Anthem"],
        indications: 4,
        lastUpdated: "Jan 15, 2026",
    },
    {
        id: "d4",
        name: "Rituximab",
        brandNames: "Rituxan, Truxima, Ruxience",
        payers: ["UnitedHealthcare", "Cigna"],
        indications: 9,
        lastUpdated: "Dec 05, 2025",
    },
];

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

export default function DrugExplorerPage() {
    const [expandedRows, setExpandedRows] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [pendingAction, setPendingAction] = useState<{ id: string; type: DrugActionType } | null>(null);

    const toggleRow = (id: string) => {
        setExpandedRows((prev) =>
            prev.includes(id) ? prev.filter((rowId) => rowId !== id) : [...prev, id]
        );
    };

    const isActionPending = (type: DrugActionType, id: string) =>
        pendingAction?.id === id && pendingAction.type === type;

    const isBusy = (id: string) => pendingAction?.id === id;

    const handleAction = (drug: Drug, actionType: DrugActionType) => {
        setPendingAction({ id: drug.id, type: actionType });
        setTimeout(() => setPendingAction(null), 1000);
    };

    const filtered = searchQuery.trim()
        ? drugsData
            .map((d) => ({
                drug: d,
                score: Math.max(fuzzyMatch(searchQuery, d.name), fuzzyMatch(searchQuery, d.brandNames)),
            }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ drug }) => drug)
        : drugsData;

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
                            placeholder="Search drug or brand name..."
                            className="pl-9 bg-card border-border"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" className="shrink-0 bg-card">
                        <Filter className="h-4 w-4 mr-2" /> Filter
                    </Button>
                </div>
            </div>

            <div className="rounded-lg border border-border">
                <Table>
                    <TableHeader>
                        <TableRow className="border-b border-border hover:bg-transparent">
                            <TableHead className="h-12 w-10 px-4" />
                            <TableHead className="h-12 px-4 font-medium">Drug Name</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Brand Names</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Payers</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Indications</TableHead>
                            <TableHead className="h-12 px-4 font-medium">Last Updated</TableHead>
                            <TableHead className="h-12 w-[140px] px-4 font-medium">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filtered.map((drug) => {
                            const expanded = expandedRows.includes(drug.id);
                            const busy = isBusy(drug.id);

                            return (
                                <React.Fragment key={drug.id}>
                                    <TableRow
                                        className={`cursor-pointer hover:bg-muted/50 border-border ${expanded ? "bg-muted/30" : ""}`}
                                        onClick={() => toggleRow(drug.id)}
                                    >
                                        <TableCell className="h-16 px-4">
                                            {expanded
                                                ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                                : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                            }
                                        </TableCell>
                                        <TableCell className="h-16 px-4 font-mono font-medium">{drug.name}</TableCell>
                                        <TableCell className="h-16 px-4 text-sm text-muted-foreground">{drug.brandNames}</TableCell>
                                        <TableCell className="h-16 px-4">
                                            <div className="flex flex-wrap gap-1.5">
                                                {drug.payers.map((payer) => (
                                                    <span
                                                        key={payer}
                                                        className="text-[11px] text-muted-foreground/70 border border-border rounded px-1.5 py-0.5 font-mono"
                                                    >
                                                        {payer}
                                                    </span>
                                                ))}
                                            </div>
                                        </TableCell>
                                        <TableCell className="h-16 px-4 font-mono text-sm">{drug.indications}</TableCell>
                                        <TableCell className="h-16 px-4 text-sm text-muted-foreground">{drug.lastUpdated}</TableCell>
                                        <TableCell className="h-16 px-4" onClick={(e) => e.stopPropagation()}>
                                            <TooltipProvider>
                                                <div className="flex items-center gap-1">
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                                                disabled={busy}
                                                                asChild={!busy}
                                                                onClick={() => handleAction(drug, "compare")}
                                                            >
                                                                {isActionPending("compare", drug.id)
                                                                    ? <Loader2 className="size-4 animate-spin" />
                                                                    : <Link href={`/compare?drug=${drug.name.toLowerCase()}`}><TableProperties className="size-4" /></Link>
                                                                }
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
                                                                disabled={busy}
                                                                onClick={() => handleAction(drug, "view")}
                                                            >
                                                                {isActionPending("view", drug.id)
                                                                    ? <Loader2 className="size-4 animate-spin" />
                                                                    : <FileTextIcon className="size-4" />
                                                                }
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent>View Details</TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8 text-destructive hover:bg-destructive/10"
                                                                disabled={busy}
                                                                onClick={() => handleAction(drug, "delete")}
                                                            >
                                                                {isActionPending("delete", drug.id)
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
                                            <TableCell colSpan={7} className="p-0">
                                                <div className="p-6 border-l-2 border-primary ml-[22px] my-2">
                                                    <div className="flex items-center justify-between mb-4">
                                                        <h4 className="font-semibold text-sm">Policy Documents ({drug.payers.length})</h4>
                                                    </div>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                                        {drug.payers.map((payer) => (
                                                            <div key={payer} className="p-3 rounded-md border border-border text-sm space-y-2">
                                                                <div className="flex items-center justify-between">
                                                                    <span className="font-medium">{payer}</span>
                                                                    <Badge variant="outline" className="border-0 bg-green-500/10 text-green-400 text-[10px] h-4">Active</Badge>
                                                                </div>
                                                                <div className="flex justify-between text-muted-foreground text-xs">
                                                                    <span>Indications</span>
                                                                    <span className="font-mono">{Math.max(1, drug.indications - Math.floor(Math.random() * 3))}</span>
                                                                </div>
                                                                <div className="flex justify-between text-muted-foreground text-xs cursor-pointer hover:text-sky-400 transition-colors">
                                                                    <span>View criteria</span>
                                                                    <ChevronRight className="h-3 w-3" />
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
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


