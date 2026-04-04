"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    FileText,
    Database,
    ShieldCheck,
    TrendingUp,
    ArrowRight,
    Plus,
    TableProperties
} from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

const stats = [
    {
        label: "Total Policies",
        value: 142,
        total: 142,
        icon: FileText,
        colorClass: "text-emerald-400",
        strokeColor: "#34d399",
        trend: "+12",
    },
    {
        label: "Drugs Tracked",
        value: 24,
        total: 142,
        icon: Database,
        colorClass: "text-rose-400",
        strokeColor: "#fb7185",
        trend: "+4",
    },
    {
        label: "Payers Covered",
        value: 8,
        total: 12,
        icon: ShieldCheck,
        colorClass: "text-amber-400",
        strokeColor: "#fbbf24",
        trend: "+0",
    },
    {
        label: "Quarterly Changes",
        value: 31,
        total: 142,
        icon: TrendingUp,
        colorClass: "text-blue-400",
        strokeColor: "#60a5fa",
        trend: "+2",
    },
];

const recentChanges = [
    {
        payer: "UnitedHealthcare",
        drug: "Infliximab",
        severity: "breaking",
        description: "Avsola and Inflectra now mandatory first-line. Remicade requires biosimilar failure.",
        date: "2 days ago",
    },
    {
        payer: "Aetna",
        drug: "Adalimumab",
        severity: "restrictive",
        description: "Trial duration increased from 12 to 14 weeks for rheumatoid arthritis.",
        date: "4 days ago",
    },
    {
        payer: "Cigna",
        drug: "Ustekinumab",
        severity: "relaxed",
        description: "New indication added for plaque psoriasis in adolescents.",
        date: "1 week ago",
    },
];

const recentActivity = [
    { action: "Policy Uploaded", target: "UHC Infliximab Commercial 2026", user: "Atharva", time: "1 hr ago" },
    { action: "Extraction Complete", target: "Aetna CPB 0321", user: "System", time: "2 hrs ago" },
    { action: "Query Processed", target: "Compare step therapy for adalimumab", user: "Om", time: "3 hrs ago" },
    { action: "Memo Generated", target: "Justification for Remicade (Aetna)", user: "Dominic", time: "5 hrs ago" },
];

export default function DashboardPage() {
    return (
        <div className="p-8 space-y-8 max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
                    <p className="text-muted-text">
                        Welcome back. Here's a summary of policy intelligence for Q2 2026.
                    </p>
                </div>
                <div className="flex gap-4">
                    <Link href="/upload">
                        <Button className="font-semibold">
                            <Plus className="mr-2 h-4 w-4" /> Upload Policy
                        </Button>
                    </Link>
                    <Link href="/compare">
                        <Button variant="outline" className="font-semibold">
                            <TableProperties className="mr-2 h-4 w-4" /> Run Comparison
                        </Button>
                    </Link>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-border/50 py-4 mb-8">
                {stats.map((stat, i) => {
                    return (
                        <div key={i} className="flex flex-col p-6 px-8 relative gap-6">
                            <div className="flex justify-between items-center text-muted-text">
                                <div className="flex items-center space-x-2">
                                    <stat.icon className="w-4 h-4" />
                                    <span className="text-[11px] font-semibold uppercase tracking-widest">{stat.label}</span>
                                </div>
                            </div>

                            <div className="flex flex-col">
                                <span className={cn("text-5xl font-light tabular-nums tracking-tight", stat.colorClass)}>{stat.value}</span>
                                <div className="flex items-center mt-3 gap-2">
                                    <span className={cn("text-sm font-medium", stat.colorClass)}>{stat.trend}</span>
                                    <span className="text-xs text-muted-text/80">this quarter</span>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4 bg-transparent border-border">
                    <CardHeader>
                        <CardTitle>What changed this quarter?</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {recentChanges.map((change, i) => (
                            <div
                                key={i}
                                className="flex items-start gap-4 p-4 rounded-lg border border-border bg-transparent hover:bg-white/5 transition"
                            >
                                <Badge
                                    variant={change.severity === "breaking" ? "destructive" : change.severity === "restrictive" ? "warning" : "success"}
                                    className="mt-0.5 capitalize"
                                >
                                    {change.severity}
                                </Badge>
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold">{change.payer}</span>
                                        <span className="text-muted-text">•</span>
                                        <span className="font-mono text-sm">{change.drug}</span>
                                    </div>
                                    <p className="text-sm text-primary-text leading-relaxed">
                                        {change.description}
                                    </p>
                                    <p className="text-xs text-muted-text">{change.date}</p>
                                </div>
                            </div>
                        ))}
                        <Button variant="link" className="p-0 text-sky-500 hover:text-sky-400" asChild>
                            <Link href="/diffs" className="flex items-center">
                                View all changes <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                        </Button>
                    </CardContent>
                </Card>

                <Card className="col-span-3 bg-transparent border-border">
                    <CardHeader>
                        <CardTitle>Recent Activity</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-8">
                            {recentActivity.map((activity, i) => (
                                <div key={i} className="flex items-center">
                                    <div className="ml-0 space-y-1">
                                        <p className="text-sm font-medium leading-none">
                                            {activity.action}: <span className="text-muted-text font-normal">{activity.target}</span>
                                        </p>
                                        <p className="text-xs text-muted-text">
                                            {activity.user} • {activity.time}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
