"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, ArrowRight, Filter, Calendar, AlertCircle } from "lucide-react";
import { useDiffsFeed } from "@/hooks/use-api";

function severityVariant(severity: string): "destructive" | "warning" | "success" | "default" {
    if (severity === "breaking") return "destructive";
    if (severity === "restrictive") return "warning";
    if (severity === "relaxed") return "success";
    return "default";
}

function formatDate(iso: string): string {
    if (!iso) return "";
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function ChangeFeedPage() {
    const [expanded, setExpanded] = useState<string[]>([]);
    const { data: feedData, isLoading, error, refetch } = useDiffsFeed(20);

    const feed = feedData?.feed ?? [];

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
                    <Button variant="outline" className="bg-card" onClick={() => refetch()}>
                        <Filter className="mr-2 h-4 w-4" /> Refresh
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error instanceof Error ? error.message : "Failed to load change feed"}
                </div>
            )}

            {isLoading ? (
                <div className="relative border-l border-border ml-4 pl-8 space-y-8">
                    {[0, 1, 2].map(i => (
                        <div key={i} className="relative">
                            <div className="absolute -left-[41px] top-1 h-5 w-5 rounded-full bg-background border-2 border-border" />
                            <Card>
                                <CardContent className="p-6 space-y-3">
                                    <div className="flex gap-2">
                                        <Skeleton className="h-5 w-16" />
                                        <Skeleton className="h-5 w-32" />
                                        <Skeleton className="h-5 w-24" />
                                    </div>
                                    <Skeleton className="h-4 w-full" />
                                    <Skeleton className="h-4 w-3/4" />
                                </CardContent>
                            </Card>
                        </div>
                    ))}
                </div>
            ) : feed.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border px-6 py-16 text-center text-sm text-muted-foreground">
                    No policy changes yet. Upload and process policies to see diffs here.
                </div>
            ) : (
                <div className="relative border-l border-border ml-4 pl-8 space-y-8">
                    {feed.map((item) => {
                        const itemKey = `${item.diffId}-${item.field}`;
                        return (
                            <div key={itemKey} className="relative">
                                <div className="absolute -left-[41px] top-1 h-5 w-5 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                                    <div className="h-2 w-2 rounded-full bg-primary" />
                                </div>

                                <Card className="hover:border-primary/50 transition">
                                    <CardContent className="p-4 sm:p-6 space-y-4">
                                        <div className="flex flex-wrap gap-2 items-start justify-between">
                                            <div className="flex items-center gap-2">
                                                <Badge
                                                    variant={severityVariant(item.severity)}
                                                    className="uppercase text-[10px] tracking-wider px-2 py-0.5"
                                                >
                                                    {item.severity || "neutral"}
                                                </Badge>
                                                <span className="font-semibold">{item.payerName}</span>
                                                <span className="text-muted-text">&bull;</span>
                                                <span className="font-mono text-sm text-primary-text">{item.drugName}</span>
                                                {item.indication && (
                                                    <>
                                                        <span className="text-muted-text">&bull;</span>
                                                        <span className="text-sm text-muted-text">{item.indication}</span>
                                                    </>
                                                )}
                                            </div>
                                            <span className="text-xs text-muted-text">{formatDate(item.generatedAt)}</span>
                                        </div>

                                        <p className="text-sm font-medium leading-relaxed">
                                            {item.humanSummary}
                                        </p>

                                        {(item.oldValue || item.newValue) && (
                                            <div className="pt-2">
                                                <Button
                                                    variant="link"
                                                    className="p-0 h-auto text-sky-500"
                                                    onClick={() => toggle(itemKey)}
                                                >
                                                    {expanded.includes(itemKey) ? "Hide technical diff" : "View technical diff"}
                                                </Button>
                                            </div>
                                        )}

                                        {expanded.includes(itemKey) && (item.oldValue || item.newValue) && (
                                            <div className="mt-4 border border-border bg-background rounded-md overflow-hidden">
                                                <div className="flex items-center p-2 bg-card border-b border-border text-xs text-muted-text gap-2">
                                                    <FileText className="h-3 w-3" />
                                                    <span>Before</span>
                                                    <ArrowRight className="h-3 w-3" />
                                                    <FileText className="h-3 w-3" />
                                                    <span>After</span>
                                                </div>
                                                <div className="p-4 space-y-3">
                                                    <div className="grid grid-cols-[120px_1fr] items-start gap-4 text-sm">
                                                        <span className="text-muted-text font-medium">{item.field || "Change"}:</span>
                                                        <div className="flex items-center gap-4 flex-wrap">
                                                            {item.oldValue && (
                                                                <span className="px-2 py-1 rounded bg-destructive/10 text-destructive line-through decoration-destructive/50">
                                                                    {item.oldValue}
                                                                </span>
                                                            )}
                                                            <ArrowRight className="h-4 w-4 text-muted-text shrink-0" />
                                                            {item.newValue && (
                                                                <span className="px-2 py-1 rounded bg-success/10 text-success">
                                                                    {item.newValue}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
