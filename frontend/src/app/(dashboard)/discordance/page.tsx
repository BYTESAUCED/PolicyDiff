"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Filter, Search, ArrowRight, AlertCircle, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DiscordanceSummary {
    diffId?: string;
    drugName: string;
    payerName: string;
    discordanceScore?: number | null;
    summary: string;
    changesCount?: number;
    generatedAt?: string;
    status?: string;
}

interface DiscordanceResponse {
    items: DiscordanceSummary[];
    count: number;
}

// Map discordance score to severity label
function scoreSeverity(score: number | null | undefined): { label: string; cls: string } {
    if (score == null) return { label: "Pending", cls: "text-muted-foreground" };
    if (score >= 0.7) return { label: "High", cls: "text-red-400" };
    if (score >= 0.4) return { label: "Medium", cls: "text-amber-400" };
    return { label: "Low", cls: "text-emerald-400" };
}

export default function DiscordancePage() {
    const [searchQuery, setSearchQuery] = useState("");
    const [discordances, setDiscordances] = useState<DiscordanceSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchDiscordances = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiFetch<DiscordanceResponse>("/api/discordance");
            setDiscordances(data.items ?? []);
        } catch (e) {
            setError(e instanceof ApiError ? e.message : "Failed to load discordance alerts");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDiscordances();
    }, [fetchDiscordances]);

    const filtered = discordances.filter(
        (d) =>
            d.payerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            d.drugName.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="p-6 max-w-7xl space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold tracking-tight">Discordance Alerts</h2>
                    {!loading && (
                        <span className="text-xs font-mono text-destructive border border-destructive/30 rounded px-2 py-0.5">
                            {filtered.length} conflict{filtered.length !== 1 ? "s" : ""}
                        </span>
                    )}
                </div>
                <div className="flex gap-2">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Filter..."
                            className="pl-9 w-48"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" size="icon" className="shrink-0" onClick={fetchDiscordances} disabled={loading}>
                        {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Filter className="h-4 w-4" />}
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            {/* Table */}
            <div className="rounded-xl border border-border overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="border-b border-border hover:bg-transparent">
                            <TableHead className="h-10 px-5 font-medium text-xs uppercase tracking-wider">Drug</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Payer</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Summary</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Severity</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Conflicts</TableHead>
                            <TableHead className="h-10 px-4 w-10" />
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            Array.from({ length: 4 }).map((_, i) => (
                                <TableRow key={i} className="border-border">
                                    <TableCell className="h-12 px-5"><Skeleton className="h-4 w-24" /></TableCell>
                                    <TableCell className="h-12 px-4"><Skeleton className="h-4 w-20" /></TableCell>
                                    <TableCell className="h-12 px-4"><Skeleton className="h-4 w-48" /></TableCell>
                                    <TableCell className="h-12 px-4"><Skeleton className="h-4 w-12" /></TableCell>
                                    <TableCell className="h-12 px-4"><Skeleton className="h-4 w-8" /></TableCell>
                                    <TableCell className="h-12 px-4" />
                                </TableRow>
                            ))
                        ) : filtered.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="h-32 text-center text-sm text-muted-foreground">
                                    {discordances.length === 0
                                        ? "No discordance alerts detected. Upload both medical and pharmacy benefit policies for the same drug to enable analysis."
                                        : "No results match your filter."
                                    }
                                </TableCell>
                            </TableRow>
                        ) : (
                            filtered.map((item) => {
                                const sev = scoreSeverity(item.discordanceScore);
                                return (
                                    <TableRow key={`${item.drugName}-${item.payerName}`} className="border-border hover:bg-white/[0.02]">
                                        <TableCell className="h-12 px-5 font-medium text-sm">{item.drugName}</TableCell>
                                        <TableCell className="h-12 px-4 text-sm text-muted-foreground">{item.payerName}</TableCell>
                                        <TableCell className="h-12 px-4 text-sm text-muted-foreground max-w-xs">
                                            <p className="line-clamp-2">{item.summary}</p>
                                        </TableCell>
                                        <TableCell className={`h-12 px-4 text-sm font-medium ${sev.cls}`}>
                                            {sev.label}
                                            {item.discordanceScore != null && (
                                                <span className="text-xs font-mono ml-1 opacity-60">
                                                    ({Math.round(item.discordanceScore * 100)}%)
                                                </span>
                                            )}
                                        </TableCell>
                                        <TableCell className="h-12 px-4 text-sm font-mono text-muted-foreground">
                                            {item.changesCount ?? "—"}
                                        </TableCell>
                                        <TableCell className="h-12 px-4">
                                            <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground">
                                                <ArrowRight className="h-3.5 w-3.5" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
