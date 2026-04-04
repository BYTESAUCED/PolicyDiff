"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    FileText, Database, ShieldCheck, TrendingUp,
    ArrowRight, Plus, TableProperties, BookMarked, Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

// TODO: replace with real Auth0 JWT claims
const role: "admin" | "consultant" = "admin";
const watchedDrugs: string[] = ["Infliximab", "Adalimumab"];

const stats = [
    { label: "Total Policies",    value: 142, icon: FileText,    colorClass: "text-emerald-400", trend: "+12" },
    { label: "Drugs Tracked",     value: 24,  icon: Database,    colorClass: "text-rose-400",    trend: "+4"  },
    { label: "Payers Covered",    value: 8,   icon: ShieldCheck, colorClass: "text-amber-400",   trend: "+0"  },
    { label: "Quarterly Changes", value: 31,  icon: TrendingUp,  colorClass: "text-blue-400",    trend: "+2"  },
];

const recentChanges = [
    {
        payer: "UnitedHealthcare", drug: "Infliximab", severity: "breaking",
        description: "Avsola and Inflectra now mandatory first-line. Remicade requires biosimilar failure.",
        date: "2 days ago",
    },
    {
        payer: "Aetna", drug: "Adalimumab", severity: "restrictive",
        description: "Trial duration increased from 12 to 14 weeks for rheumatoid arthritis.",
        date: "4 days ago",
    },
    {
        payer: "Cigna", drug: "Ustekinumab", severity: "relaxed",
        description: "New indication added for plaque psoriasis in adolescents.",
        date: "1 week ago",
    },
];

const recentActivity = [
    { action: "Policy Uploaded",     target: "UHC Infliximab Commercial 2026",     user: "Atharva", time: "1 hr ago"  },
    { action: "Extraction Complete", target: "Aetna CPB 0321",                      user: "System",  time: "2 hrs ago" },
    { action: "Query Processed",     target: "Compare step therapy for adalimumab", user: "Om",      time: "3 hrs ago" },
    { action: "Memo Generated",      target: "Justification for Remicade (Aetna)",  user: "Dominic", time: "5 hrs ago" },
];

const watchedChanges = recentChanges.filter((c) =>
    watchedDrugs.map((d) => d.toLowerCase()).includes(c.drug.toLowerCase())
);

const severityVariant = (s: string) =>
    s === "breaking" ? "destructive" : s === "restrictive" ? "warning" : "success";

export default function DashboardPage() {
    return (
        <div className="p-8 space-y-10 max-w-6xl">

            {/* ── Header ── */}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {role === "admin"
                            ? "Policy intelligence summary · Q2 2026"
                            : "Your personalized policy intelligence · Q2 2026"}
                    </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    {role === "admin" && (
                        <Link href="/upload">
                            <Button size="sm" className="font-medium">
                                <Plus className="mr-1.5 h-3.5 w-3.5" /> Upload Policy
                            </Button>
                        </Link>
                    )}
                    <Link href="/compare">
                        <Button size="sm" variant="outline" className="font-medium">
                            <TableProperties className="mr-1.5 h-3.5 w-3.5" /> Compare
                        </Button>
                    </Link>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground" aria-label="Preferences">
                        <Settings className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* ── Stats ── */}
            <div className="grid grid-cols-4 gap-px bg-border rounded-xl overflow-hidden">
                {stats.map((stat) => (
                    <div key={stat.label} className="bg-background flex flex-col gap-3 p-6">
                        <div className="flex items-center gap-2 text-muted-foreground">
                            <stat.icon className="h-3.5 w-3.5" />
                            <span className="text-xs font-medium uppercase tracking-widest">{stat.label}</span>
                        </div>
                        <div>
                            <span className={cn("text-4xl font-light tabular-nums", stat.colorClass)}>{stat.value}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className={cn("text-xs font-semibold", stat.colorClass)}>{stat.trend}</span>
                            <span className="text-xs text-muted-foreground">this quarter</span>
                        </div>
                    </div>
                ))}
            </div>

            {/* ── Watched Drugs ── */}
            {watchedDrugs.length > 0 ? (
                <section className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <BookMarked className="h-4 w-4 text-primary" />
                            <h2 className="text-sm font-semibold">Your Watched Drugs</h2>
                            <span className="text-xs text-muted-foreground">— {watchedDrugs.join(", ")}</span>
                        </div>
                        <Link href="/diffs">
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground gap-1">
                                View all <ArrowRight className="h-3 w-3" />
                            </Button>
                        </Link>
                    </div>
                    <div className="space-y-2">
                        {watchedChanges.map((change, i) => (
                            <Link key={i} href="/diffs" className="block group cursor-pointer">
                                <div className="flex items-start gap-4 px-5 py-4 rounded-lg border border-border bg-card hover:bg-white/[0.03] transition-colors duration-150">
                                    <Badge variant={severityVariant(change.severity)} className="capitalize shrink-0 mt-0.5 text-[10px]">
                                        {change.severity}
                                    </Badge>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-sm font-medium">{change.payer}</span>
                                            <span className="text-muted-foreground text-xs">·</span>
                                            <span className="text-xs font-mono text-muted-foreground">{change.drug}</span>
                                        </div>
                                        <p className="text-sm text-muted-foreground leading-relaxed">{change.description}</p>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0 self-center">
                                        <span className="text-xs text-muted-foreground">{change.date}</span>
                                        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                </section>
            ) : (
                <div className="flex items-center justify-between px-5 py-4 rounded-lg border border-dashed border-border">
                    <div className="flex items-center gap-3">
                        <BookMarked className="h-4 w-4 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">Watch drugs to get a personalized feed.</p>
                    </div>
                    <Button variant="ghost" size="sm" className="h-7 text-xs gap-1.5 text-muted-foreground">
                        <Settings className="h-3.5 w-3.5" /> Settings
                    </Button>
                </div>
            )}

            {/* ── Bottom grid ── */}
            <div className="grid grid-cols-7 gap-6">

                {/* What changed */}
                <section className="col-span-4 space-y-4">
                    <h2 className="text-sm font-semibold">What changed this quarter?</h2>
                    <div className="space-y-2">
                        {recentChanges.map((change, i) => (
                            <div key={i} className="flex items-start gap-4 px-5 py-4 rounded-lg border border-border bg-card">
                                <Badge variant={severityVariant(change.severity)} className="capitalize shrink-0 mt-0.5 text-[10px]">
                                    {change.severity}
                                </Badge>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-medium">{change.payer}</span>
                                        <span className="text-muted-foreground text-xs">·</span>
                                        <span className="text-xs font-mono text-muted-foreground">{change.drug}</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground leading-relaxed">{change.description}</p>
                                    <p className="text-xs text-muted-foreground/60 mt-1.5">{change.date}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                    <Link href="/diffs" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
                        View all changes <ArrowRight className="h-3 w-3" />
                    </Link>
                </section>

                {/* Recent Activity */}
                <section className="col-span-3 space-y-4">
                    <h2 className="text-sm font-semibold">Recent Activity</h2>
                    <div className="rounded-lg border border-border bg-card divide-y divide-border">
                        {recentActivity.map((item, i) => (
                            <div key={i} className="px-5 py-3.5">
                                <p className="text-sm">
                                    <span className="text-muted-foreground">{item.action}</span>
                                    {" · "}
                                    <span className="font-medium">{item.target}</span>
                                </p>
                                <p className="text-xs text-muted-foreground mt-0.5">{item.user} · {item.time}</p>
                            </div>
                        ))}
                    </div>
                </section>

            </div>
        </div>
    );
}
