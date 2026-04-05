"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Search, ArrowRight, BookMarked, TableProperties,
    Clock, ChevronRight, Pill, FileText, Calendar
} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useState, useRef, useEffect, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface WatchedDrug {
    name: string;
    generic?: string;
    payers?: string[];
    updatedPayers?: number;
    lastUpdate?: string;
}

interface FeedEntry {
    diffId: string;
    drugName: string;
    payerName: string;
    severity: string;
    humanSummary: string;
    generatedAt: string;
    field?: string;
    indication?: string;
}

interface RecentQuery {
    queryId: string;
    queryText: string;
    queryType: string;
    createdAt: string;
}

// ── Search data (static drug list for autocomplete) ───────────────────────────

const allDrugs = [
    { name: "Infliximab",    brands: "Remicade, Inflectra, Avsola",    payers: 6 },
    { name: "Adalimumab",    brands: "Humira, Amjevita, Cyltezo",       payers: 4 },
    { name: "Ustekinumab",   brands: "Stelara, Wezlana",               payers: 4 },
    { name: "Rituximab",     brands: "Rituxan, Truxima, Ruxience",      payers: 2 },
    { name: "Secukinumab",   brands: "Cosentyx",                        payers: 3 },
    { name: "Dupilumab",     brands: "Dupixent",                        payers: 5 },
    { name: "Vedolizumab",   brands: "Entyvio",                         payers: 3 },
    { name: "Apremilast",    brands: "Otezla",                          payers: 2 },
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

function severityToType(severity: string): "Clinical" | "Cosmetic" {
    return severity === "breaking" || severity === "restrictive" ? "Clinical" : "Cosmetic";
}

function relativeTime(iso: string): string {
    if (!iso) return "";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins} min ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days} day${days > 1 ? "s" : ""} ago`;
    return `${Math.floor(days / 7)} week${Math.floor(days / 7) > 1 ? "s" : ""} ago`;
}

const watchedDrugBlockClasses = [
    "bg-card hover:bg-muted/20",
    "bg-card hover:bg-muted/20",
    "bg-card hover:bg-muted/20",
];

// ── Page ─────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const searchRef = useRef<HTMLDivElement>(null);

    const [watchedDrugs, setWatchedDrugs] = useState<WatchedDrug[]>([]);
    const [recentChanges, setRecentChanges] = useState<FeedEntry[]>([]);
    const [recentQueries, setRecentQueries] = useState<RecentQuery[]>([]);
    const [totalPolicies, setTotalPolicies] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const results = query.trim()
        ? allDrugs
            .map((d) => ({ drug: d, score: Math.max(fuzzyMatch(query, d.name), fuzzyMatch(query, d.brands)) }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ drug }) => drug)
        : [];

    const fetchDashboardData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [prefsData, feedData, queriesData, policiesData] = await Promise.allSettled([
                apiFetch<{ watchedDrugs?: WatchedDrug[] }>("/api/users/me/preferences"),
                apiFetch<{ feed: FeedEntry[] }>("/api/diffs/feed", undefined, { limit: "5" }),
                apiFetch<{ queries: RecentQuery[] }>("/api/queries"),
                apiFetch<{ items: unknown[] }>("/api/policies"),
            ]);

            if (prefsData.status === "fulfilled") {
                const drugs = prefsData.value.watchedDrugs ?? [];
                setWatchedDrugs(drugs);
            }

            if (feedData.status === "fulfilled") {
                setRecentChanges(feedData.value.feed ?? []);
            }

            if (queriesData.status === "fulfilled") {
                setRecentQueries(queriesData.value.queries ?? []);
            }

            if (policiesData.status === "fulfilled") {
                setTotalPolicies(policiesData.value.items?.length ?? 0);
            }
        } catch (e) {
            setError(e instanceof ApiError ? e.message : "Failed to load dashboard data");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDashboardData();
    }, [fetchDashboardData]);

    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    // Derive stats from real data
    const drugsTracked = watchedDrugs.length || totalPolicies || 0;
    const changesThisWeek = recentChanges.filter(c => {
        if (!c.generatedAt) return false;
        return Date.now() - new Date(c.generatedAt).getTime() < 7 * 24 * 60 * 60 * 1000;
    }).length;
    const actionableAlerts = recentChanges.filter(c => c.severity === "breaking").length;

    return (
        <div className="p-8 space-y-10 max-w-6xl">

            {/* ── Search & Header ── */}
            <div className="space-y-6">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6">
                    <div className="space-y-3">
                        <h1 className="text-4xl md:text-5xl font-medium tracking-tight text-foreground leading-[1.1] font-serif">
                            Welcome back.
                        </h1>
                        <p className="text-lg text-muted-foreground">
                            Here's what changed in <span className="italic text-[#cd6c55] font-serif">medical drug policies</span> today.
                        </p>
                    </div>
                    <div className="shrink-0 md:pt-2">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-border dark:border-white/10 bg-card/50 text-xs font-bold tracking-widest text-muted-foreground uppercase">
                            <Calendar className="h-3.5 w-3.5 text-primary" />
                            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4 flex-wrap text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        <span className="text-muted-foreground">Tracking</span>
                        {loading
                            ? <Skeleton className="h-4 w-8" />
                            : <span className="font-semibold text-foreground">{drugsTracked} drugs</span>
                        }
                    </div>
                    <div className="w-[1px] h-3.5 bg-border dark:bg-white/10" />
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                        <span className="text-muted-foreground">Changes this wk</span>
                        {loading
                            ? <Skeleton className="h-4 w-6" />
                            : <span className="font-semibold text-foreground">{changesThisWeek}</span>
                        }
                    </div>
                    <div className="w-[1px] h-3.5 bg-border dark:bg-white/10" />
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                        <span className="text-muted-foreground">Actionable alerts</span>
                        {loading
                            ? <Skeleton className="h-4 w-6" />
                            : <span className="font-semibold text-foreground">{actionableAlerts}</span>
                        }
                    </div>
                </div>

                <div className="relative" ref={searchRef}>
                    <Search className="absolute left-3.5 top-[11px] h-4 w-4 text-muted-foreground pointer-events-none z-10" />
                    <Input
                        placeholder="Search a drug — e.g. Infliximab, Adalimumab, Humira..."
                        className="pl-10 h-11 text-sm bg-card border-border font-mono"
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setOpen(true);
                        }}
                        onFocus={() => setOpen(true)}
                    />
                    {open && results.length > 0 && (
                        <div className="absolute top-full mt-1.5 left-0 right-0 z-50 bg-card border border-border rounded-[12px] shadow-lg overflow-hidden">
                            {results.map((drug) => (
                                <div
                                    key={drug.name}
                                    className="flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors border-b border-border dark:border-white/10 last:border-0 group"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Pill className="h-4 w-4 text-primary shrink-0" />
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium font-mono">{drug.name}</p>
                                            <p className="text-xs text-muted-foreground truncate">{drug.brands}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1.5 shrink-0 ml-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Link href={`/compare?drug=${drug.name.toLowerCase()}`} onClick={() => setOpen(false)}>
                                            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 cursor-pointer">
                                                <TableProperties className="h-3 w-3" /> Compare
                                            </Button>
                                        </Link>
                                        <Link href="/explorer" onClick={() => setOpen(false)}>
                                            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 cursor-pointer">
                                                <FileText className="h-3 w-3" /> View
                                            </Button>
                                        </Link>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* ── Error state ── */}
            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            {/* ── Watched Drugs ── */}
            <section className="space-y-5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-1 h-3.5 rounded-full bg-primary" />
                        <BookMarked className="h-4 w-4 text-primary" />
                        <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Watched Drugs</h2>
                        {!loading && <span className="text-xs text-muted-foreground">({watchedDrugs.length})</span>}
                    </div>
                    <Link href="/diffs">
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground gap-1 cursor-pointer">
                            All changes <ArrowRight className="h-3 w-3" />
                        </Button>
                    </Link>
                </div>

                {loading ? (
                    <div className="grid grid-cols-3 border border-border dark:border-white/10 rounded-lg divide-x divide-border dark:divide-white/10">
                        {[0, 1, 2].map(i => (
                            <div key={i} className="px-5 py-5 space-y-4">
                                <Skeleton className="h-4 w-24" />
                                <div className="flex gap-1.5 flex-wrap">
                                    <Skeleton className="h-5 w-10" />
                                    <Skeleton className="h-5 w-12" />
                                    <Skeleton className="h-5 w-10" />
                                </div>
                                <Skeleton className="h-3 w-28" />
                            </div>
                        ))}
                    </div>
                ) : watchedDrugs.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border px-6 py-8 text-center text-sm text-muted-foreground">
                        No watched drugs yet. Your preferences will appear here once configured.
                    </div>
                ) : (
                    <div className="grid grid-cols-3 border border-border dark:border-white/10 rounded-lg divide-x divide-border dark:divide-white/10 bg-transparent">
                        {watchedDrugs.slice(0, 3).map((drug, index) => (
                            <Link
                                key={drug.name}
                                href="/explorer"
                                className={cn(
                                    "block group cursor-pointer px-5 py-5 transition-colors",
                                    watchedDrugBlockClasses[index % watchedDrugBlockClasses.length],
                                )}
                            >
                                <div className="space-y-4">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex items-center gap-1.5">
                                            <Pill className="h-4 w-4 text-primary shrink-0" />
                                            <span className="text-sm font-semibold tracking-tight group-hover:text-primary transition-colors">{drug.name}</span>
                                        </div>
                                        {(drug.updatedPayers ?? 0) > 0 && (
                                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800 shrink-0 whitespace-nowrap">
                                                {drug.updatedPayers} updated
                                            </span>
                                        )}
                                    </div>
                                    {drug.payers && drug.payers.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5">
                                            {drug.payers.map((payer) => (
                                                <span key={payer} className="text-[11px] font-mono px-2 py-0.5 rounded border border-border dark:border-white/10 text-muted-foreground bg-transparent">
                                                    {payer}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                    {drug.lastUpdate && (
                                        <p className="text-xs text-muted-foreground/70">Last change {drug.lastUpdate}</p>
                                    )}
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </section>

            {/* ── Bottom grid ── */}
            <div className="grid grid-cols-7 gap-6">

                {/* Recent Policy Changes */}
                <section className="col-span-4 space-y-5">
                    <div className="flex items-center gap-2">
                        <div className="w-1 h-3.5 rounded-full bg-primary" />
                        <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Recent Policy Changes</h2>
                    </div>
                    {loading ? (
                        <div className="divide-y divide-border dark:divide-white/10 border-y border-border dark:border-white/10">
                            {[0, 1, 2].map(i => (
                                <div key={i} className="flex items-start gap-4 py-4 px-2">
                                    <Skeleton className="h-2 w-2 rounded-full mt-2 shrink-0" />
                                    <div className="flex-1 space-y-2">
                                        <Skeleton className="h-4 w-48" />
                                        <Skeleton className="h-3 w-full" />
                                        <Skeleton className="h-3 w-3/4" />
                                    </div>
                                    <Skeleton className="h-3 w-16 shrink-0" />
                                </div>
                            ))}
                        </div>
                    ) : recentChanges.length === 0 ? (
                        <div className="border-y border-border dark:border-white/10 py-8 text-center text-sm text-muted-foreground">
                            No policy changes yet. Upload policies to see diffs here.
                        </div>
                    ) : (
                        <div className="divide-y divide-border dark:divide-white/10 border-y border-border dark:border-white/10">
                            {recentChanges.slice(0, 5).map((change) => {
                                const type = severityToType(change.severity);
                                return (
                                    <Link key={change.diffId} href="/diffs" className="block group cursor-pointer hover:bg-muted/20 transition-colors">
                                        <div className="flex items-start gap-4 py-4 px-2">
                                            <div className="mt-1.5 shrink-0">
                                                {type === "Clinical" ? (
                                                    <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
                                                ) : (
                                                    <div className="w-2 h-2 rounded-full bg-muted-foreground/40" />
                                                )}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{change.payerName}</span>
                                                    <span className="text-muted-foreground/30 text-xs">·</span>
                                                    <span className="text-xs font-mono text-muted-foreground">{change.drugName}</span>
                                                    <span className="text-muted-foreground/30 text-xs">·</span>
                                                    {type === "Clinical" ? (
                                                        <span className="text-[10px] font-bold uppercase tracking-widest text-red-600 dark:text-red-400">Clinical</span>
                                                    ) : (
                                                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Cosmetic</span>
                                                    )}
                                                </div>
                                                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">{change.humanSummary}</p>
                                            </div>
                                            <div className="text-right shrink-0">
                                                <p className="text-xs text-muted-foreground">{relativeTime(change.generatedAt)}</p>
                                            </div>
                                        </div>
                                    </Link>
                                );
                            })}
                        </div>
                    )}
                    <Link href="/diffs" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
                        View all changes <ArrowRight className="h-3 w-3" />
                    </Link>
                </section>

                {/* Recent Queries */}
                <section className="col-span-3 space-y-5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className="w-1 h-3.5 rounded-full bg-primary" />
                            <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Recent Queries</h2>
                        </div>
                        <Link href="/query">
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground gap-1 cursor-pointer">
                                <TableProperties className="h-3 w-3" /> New
                            </Button>
                        </Link>
                    </div>
                    {loading ? (
                        <div className="rounded-lg border border-border dark:border-white/10 divide-y divide-border dark:divide-white/10">
                            {[0, 1, 2].map(i => (
                                <div key={i} className="px-4 py-4 space-y-2">
                                    <Skeleton className="h-4 w-32" />
                                    <Skeleton className="h-3 w-24" />
                                </div>
                            ))}
                        </div>
                    ) : recentQueries.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                            No queries yet. Ask a question to get started.
                        </div>
                    ) : (
                        <div className="rounded-lg border border-border dark:border-white/10 divide-y divide-border dark:divide-white/10 bg-transparent">
                            {recentQueries.slice(0, 3).map((q) => (
                                <Link key={q.queryId} href="/query" className="block group cursor-pointer bg-card hover:bg-muted/20 transition-colors first:rounded-t-lg last:rounded-b-lg">
                                    <div className="px-4 py-4">
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-1">{q.queryText}</p>
                                            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                                        </div>
                                        <div className="flex items-center gap-1.5 mt-2">
                                            <Clock className="h-3 w-3 text-muted-foreground/50" />
                                            <p className="text-[11px] text-muted-foreground/70">{relativeTime(q.createdAt)}</p>
                                        </div>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
