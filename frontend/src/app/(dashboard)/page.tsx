"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Search, ArrowRight, BookMarked, TableProperties,
    Clock, ChevronRight, AlertCircle, Pill, FileText,
    Plus, Calendar
} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useState, useRef, useEffect } from "react";

// ── Search data ───────────────────────────────────────────────────────────────

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

// ── Mock data ─────────────────────────────────────────────────────────────────

const watchedDrugs = [
    {
        name: "Infliximab",
        generic: "infliximab",
        payers: ["UHC", "Cigna", "Aetna", "BCBS NC", "Humana", "CVS"],
        updatedPayers: 2,
        lastUpdate: "2 days ago",
    },
    {
        name: "Adalimumab",
        generic: "adalimumab",
        payers: ["UHC", "Aetna", "BCBS CA", "Molina"],
        updatedPayers: 1,
        lastUpdate: "4 days ago",
    },
    {
        name: "Ustekinumab",
        generic: "ustekinumab",
        payers: ["Cigna", "BCBS NC", "UPMC", "Centene"],
        updatedPayers: 0,
        lastUpdate: "3 weeks ago",
    },
];

const recentChanges = [
    {
        type: "Clinical",
        payer: "UnitedHealthcare",
        drug: "Infliximab",
        description: "Avsola and Inflectra now mandatory first-line. Remicade requires documented biosimilar failure.",
        date: "2 days ago",
        effectiveDate: "2026-04-01",
    },
    {
        type: "Clinical",
        payer: "Aetna",
        drug: "Adalimumab",
        description: "Step therapy trial duration increased from 12 to 14 weeks for rheumatoid arthritis indication.",
        date: "4 days ago",
        effectiveDate: "2026-03-15",
    },
    {
        type: "Cosmetic",
        payer: "Cigna",
        drug: "Ustekinumab",
        description: "Updated clinical reference citations. No criteria changes.",
        date: "1 week ago",
        effectiveDate: "2026-03-10",
    },
    {
        type: "Clinical",
        payer: "BCBS NC",
        drug: "Infliximab",
        description: "Prior authorization now required for all biosimilar products, previously only brand.",
        date: "1 week ago",
        effectiveDate: "2026-03-08",
    },
    {
        type: "Cosmetic",
        payer: "Humana",
        drug: "Secukinumab",
        description: "Effective date updated. Formatting changes to step therapy table.",
        date: "2 weeks ago",
        effectiveDate: "2026-02-28",
    },
];

const recentComparisons = [
    {
        drug: "Infliximab",
        payers: ["UHC", "Cigna", "Aetna", "BCBS NC"],
        runBy: "Om",
        date: "3 hrs ago",
        href: "/compare",
    },
    {
        drug: "Adalimumab",
        payers: ["UHC", "Aetna", "BCBS CA"],
        runBy: "Atharva",
        date: "Yesterday",
        href: "/compare",
    },
    {
        drug: "Ustekinumab",
        payers: ["Cigna", "UPMC", "Centene"],
        runBy: "Dominic",
        date: "2 days ago",
        href: "/compare",
    },
];



// ── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const searchRef = useRef<HTMLDivElement>(null);

    const results = query.trim()
        ? allDrugs
            .map((d) => ({ drug: d, score: Math.max(fuzzyMatch(query, d.name), fuzzyMatch(query, d.brands)) }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ drug }) => drug)
        : [];

    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    return (
        <div className="p-8 space-y-10 max-w-6xl">

            {/* ── Search & Header ── */}
            <div className="space-y-6">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6">
                    <div className="space-y-3">
                        <h1 className="text-4xl md:text-5xl font-medium tracking-tight text-foreground leading-[1.1] font-serif">
                            Welcome back, Om.
                        </h1>
                        <p className="text-lg text-muted-foreground">
                            Here's what changed in <span className="italic text-[#cd6c55] font-serif">medical drug policies</span> today.
                        </p>
                    </div>
                    <div className="shrink-0 md:pt-2">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-border dark:border-white/10 bg-card/50 text-xs font-bold tracking-widest text-muted-foreground uppercase">
                            <Calendar className="h-3.5 w-3.5 text-primary" />
                            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric'})}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4 flex-wrap text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        <span className="text-muted-foreground">Tracking</span>
                        <span className="font-semibold text-foreground">12 drugs</span>
                    </div>
                    <div className="w-[1px] h-3.5 bg-border dark:bg-white/10" />
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                        <span className="text-muted-foreground">Changes this wk</span>
                        <span className="font-semibold text-foreground">5</span>
                    </div>
                    <div className="w-[1px] h-3.5 bg-border dark:bg-white/10" />
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                        <span className="text-muted-foreground">Actionable alerts</span>
                        <span className="font-semibold text-foreground">2</span>
                    </div>
                </div>

                <div className="relative" ref={searchRef}>
                    <Search className="absolute left-3.5 top-[11px] h-4 w-4 text-muted-foreground pointer-events-none z-10" />
                    <Input
                        placeholder="Search a drug — e.g. Infliximab, Adalimumab, Humira…"
                        className="pl-10 h-11 text-sm bg-card border-border font-mono"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
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

            {/* ── Watched Drugs ── */}
            <section className="space-y-5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-1 h-3.5 rounded-full bg-primary" />
                        <BookMarked className="h-4 w-4 text-primary" />
                        <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Watched Drugs</h2>
                        <span className="text-xs text-muted-foreground">({watchedDrugs.length})</span>
                    </div>
                    <Link href="/diffs">
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground gap-1 cursor-pointer">
                            All changes <ArrowRight className="h-3 w-3" />
                        </Button>
                    </Link>
                </div>

                <div className="grid grid-cols-3 border border-border dark:border-white/10 rounded-lg divide-x divide-border dark:divide-white/10 bg-transparent">
                    {watchedDrugs.map((drug) => (
                        <Link key={drug.name} href="/explorer" className="block group cursor-pointer px-5 py-5 hover:bg-muted/20 transition-colors">
                            <div className="space-y-4">
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <Pill className="h-4 w-4 text-primary shrink-0" />
                                        <span className="text-sm font-semibold tracking-tight group-hover:text-primary transition-colors">{drug.name}</span>
                                    </div>
                                    {drug.updatedPayers > 0 && (
                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800 shrink-0 whitespace-nowrap">
                                            {drug.updatedPayers} updated
                                        </span>
                                    )}
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                    {drug.payers.map((p) => (
                                        <span key={p} className="text-[11px] font-mono px-2 py-0.5 rounded border border-border dark:border-white/10 text-muted-foreground bg-transparent">
                                            {p}
                                        </span>
                                    ))}
                                </div>
                                <p className="text-xs text-muted-foreground/70">Last change {drug.lastUpdate}</p>
                            </div>
                        </Link>
                    ))}
                </div>
            </section>

            {/* ── Bottom grid ── */}
            <div className="grid grid-cols-7 gap-6">

                {/* Recent Policy Changes */}
                <section className="col-span-4 space-y-5">
                    <div className="flex items-center gap-2">
                        <div className="w-1 h-3.5 rounded-full bg-primary" />
                        <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Recent Policy Changes</h2>
                    </div>
                    <div className="divide-y divide-border dark:divide-white/10 border-y border-border dark:border-white/10">
                        {recentChanges.map((change, i) => (
                            <Link key={i} href="/diffs" className="block group cursor-pointer hover:bg-muted/20 transition-colors">
                                <div className="flex items-start gap-4 py-4 px-2">
                                    <div className="mt-1.5 shrink-0">
                                        {change.type === "Clinical" ? (
                                            <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
                                        ) : (
                                            <div className="w-2 h-2 rounded-full bg-muted-foreground/40" />
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{change.payer}</span>
                                            <span className="text-muted-foreground/30 text-xs">·</span>
                                            <span className="text-xs font-mono text-muted-foreground">{change.drug}</span>
                                            <span className="text-muted-foreground/30 text-xs">·</span>
                                            {change.type === "Clinical" ? (
                                                <span className="text-[10px] font-bold uppercase tracking-widest text-red-600 dark:text-red-400">
                                                    Clinical
                                                </span>
                                            ) : (
                                                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                                                    Cosmetic
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">{change.description}</p>
                                    </div>
                                    <div className="text-right shrink-0">
                                        <p className="text-xs text-muted-foreground">{change.date}</p>
                                        <p className="text-[10px] font-mono text-muted-foreground/60 mt-0.5">eff. {change.effectiveDate}</p>
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                    <Link href="/diffs" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
                        View all changes <ArrowRight className="h-3 w-3" />
                    </Link>
                </section>

                {/* Recent Comparisons */}
                <section className="col-span-3 space-y-5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <div className="w-1 h-3.5 rounded-full bg-primary" />
                            <h2 className="text-xs font-bold uppercase tracking-widest text-foreground">Recent Comparisons</h2>
                        </div>
                        <Link href="/compare">
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground gap-1 cursor-pointer">
                                <TableProperties className="h-3 w-3" /> New
                            </Button>
                        </Link>
                    </div>
                    <div className="border border-border dark:border-white/10 rounded-lg divide-y divide-border dark:divide-white/10 bg-transparent">
                        {recentComparisons.map((comp, i) => (
                            <Link key={i} href={comp.href} className="block group cursor-pointer hover:bg-muted/20 transition-colors first:rounded-t-lg last:rounded-b-lg">
                                <div className="px-4 py-4">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="flex items-center gap-1.5">
                                            <Pill className="h-3.5 w-3.5 text-primary shrink-0" />
                                            <span className="text-sm font-medium group-hover:text-primary transition-colors">{comp.drug}</span>
                                        </div>
                                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 translate-x-[-4px] group-hover:translate-x-0" />
                                    </div>
                                    <div className="flex flex-wrap gap-1 mt-2.5">
                                        {comp.payers.map((p) => (
                                            <span key={p} className="text-[11px] font-mono px-1.5 py-0.5 rounded border border-border dark:border-white/10 text-muted-foreground bg-transparent">
                                                {p}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-1.5 mt-2.5">
                                        <Clock className="h-3 w-3 text-muted-foreground/50" />
                                        <p className="text-[11px] text-muted-foreground/70">{comp.date} · {comp.runBy}</p>
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                </section>

            </div>
        </div>
    );
}
