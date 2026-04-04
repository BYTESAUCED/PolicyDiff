"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, ArrowRight, Filter, Calendar } from "lucide-react";

const feedData = [
    {
        id: "diff1",
        payer: "UnitedHealthcare",
        drug: "Infliximab",
        indication: "Rheumatoid Arthritis",
        severity: "destructive",
        severityLabel: "breaking",
        summary: "Avsola and Inflectra now mandatory first-line. Remicade requires biosimilar failure.",
        oldVersion: { date: "Jan 1, 2025", title: "Medical Benefit: Infliximab (2025)" },
        newVersion: { date: "Feb 1, 2026", title: "Medical Benefit: Infliximab (2026)" },
        changes: [
            { field: "Preferred Products", old: "Any infliximab", new: "Avsola, Inflectra (Rank 1)" },
            { field: "Step Therapy", old: "None", new: "Must fail biosimilar" },
        ]
    },
    {
        id: "diff2",
        payer: "Aetna",
        drug: "Adalimumab",
        indication: "Psoriatic Arthritis",
        severity: "warning",
        severityLabel: "restrictive",
        summary: "Trial duration increased from 12 to 14 weeks.",
        oldVersion: { date: "Mar 15, 2025", title: "CPB 0321 (2025)" },
        newVersion: { date: "Feb 12, 2026", title: "CPB 0321 (2026)" },
        changes: [
            { field: "Trial Duration", old: "12 weeks", new: "14 weeks" },
        ]
    },
    {
        id: "diff3",
        payer: "Cigna",
        drug: "Ustekinumab",
        indication: "Plaque Psoriasis",
        severity: "success",
        severityLabel: "relaxed",
        summary: "New indication added for plaque psoriasis in adolescents.",
        oldVersion: { date: "Jun 10, 2024", title: "Cigna Coverage Policy (2024)" },
        newVersion: { date: "Jan 12, 2026", title: "Cigna Coverage Policy (2026)" },
        changes: [
            { field: "Indications", old: "Adults only", new: "Adults + Adolescents (>12y)" },
        ]
    },
];

export default function ChangeFeedPage() {
    const [expanded, setExpanded] = useState<string[]>([]);

    const toggle = (id: string) => {
        setExpanded(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
    };

    return (
        <div className="p-6 max-w-7xl space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight mb-1">Change Feed</h2>
                    <p className="text-muted-text">
                        Chronological temporal diffs across ingested policy versions.
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" className="bg-card">
                        <Calendar className="mr-2 h-4 w-4" /> This Quarter
                    </Button>
                    <Button variant="outline" className="bg-card">
                        <Filter className="mr-2 h-4 w-4" /> Filter
                    </Button>
                </div>
            </div>

            <div className="relative border-l border-border ml-4 pl-8 space-y-8">
                {feedData.map((item) => (
                    <div key={item.id} className="relative">
                        <div className="absolute -left-[41px] top-1 h-5 w-5 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                            <div className="h-2 w-2 rounded-full bg-primary" />
                        </div>

                        <Card className="hover:border-primary/50 transition">
                            <CardContent className="p-4 sm:p-6 space-y-4">
                                <div className="flex flex-wrap gap-2 items-start justify-between">
                                    <div className="flex items-center gap-2">
                                        <Badge variant={item.severity as "destructive" | "warning" | "success" | "default"} className="uppercase text-[10px] tracking-wider px-2 py-0.5">
                                            {item.severityLabel}
                                        </Badge>
                                        <span className="font-semibold">{item.payer}</span>
                                        <span className="text-muted-text">&bull;</span>
                                        <span className="font-mono text-sm text-primary-text">{item.drug}</span>
                                        <span className="text-muted-text">&bull;</span>
                                        <span className="text-sm text-muted-text">{item.indication}</span>
                                    </div>
                                    <span className="text-xs text-muted-text">{item.newVersion.date}</span>
                                </div>

                                <p className="text-sm font-medium leading-relaxed">
                                    {item.summary}
                                </p>

                                <div className="pt-2">
                                    <Button variant="link" className="p-0 h-auto text-sky-500" onClick={() => toggle(item.id)}>
                                        {expanded.includes(item.id) ? "Hide technical diff" : "View technical diff"}
                                    </Button>
                                </div>

                                {expanded.includes(item.id) && (
                                    <div className="mt-4 border border-border bg-background rounded-md overflow-hidden">
                                        <div className="flex items-center p-2 bg-card border-b border-border text-xs text-muted-text gap-2">
                                            <FileText className="h-3 w-3" />
                                            <span>{item.oldVersion.date}</span>
                                            <ArrowRight className="h-3 w-3" />
                                            <FileText className="h-3 w-3" />
                                            <span>{item.newVersion.date}</span>
                                        </div>
                                        <div className="p-4 space-y-3">
                                            {item.changes.map((change, i) => (
                                                <div key={i} className="grid grid-cols-[120px_1fr] items-start gap-4 text-sm">
                                                    <span className="text-muted-text font-medium">{change.field}:</span>
                                                    <div className="flex items-center gap-4">
                                                        <span className="px-2 py-1 rounded bg-destructive/10 text-destructive line-through decoration-destructive/50">{change.old}</span>
                                                        <ArrowRight className="h-4 w-4 text-muted-text shrink-0" />
                                                        <span className="px-2 py-1 rounded bg-success/10 text-success">{change.new}</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                ))}
            </div>
        </div>
    );
}
