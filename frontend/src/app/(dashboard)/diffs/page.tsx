"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, ArrowRight, Filter, Calendar, AlertCircle, ChevronDown } from "lucide-react";
import { useDiffsFeed, useDiffs } from "@/hooks/use-api";

type TimeRange = "week" | "month" | "quarter" | "all";
type SeverityFilter = "all" | "breaking" | "restrictive" | "relaxed";

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

const timeRangeLabels: Record<TimeRange, string> = {
    week: "This Week",
    month: "This Month",
    quarter: "This Quarter",
    all: "All Time",
};

function isWithinRange(iso: string, range: TimeRange): boolean {
    if (range === "all" || !iso) return true;
    const now = Date.now();
    const t = new Date(iso).getTime();
    const day = 24 * 60 * 60 * 1000;
    if (range === "week") return now - t < 7 * day;
    if (range === "month") return now - t < 30 * day;
    if (range === "quarter") return now - t < 90 * day;
    return true;
}

export default function ChangeFeedPage() {
    const [expanded, setExpanded] = useState<string[]>([]);
    const [timeRange, setTimeRange] = useState<TimeRange>("quarter");
    const [timeDropdown, setTimeDropdown] = useState(false);
    const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
    const [filterDropdown, setFilterDropdown] = useState(false);

    const { data: feedData, isLoading: loadingFeed, error: feedError, refetch: refetchFeed } = useDiffsFeed(50);
    const { data: diffsData, isLoading: loadingDiffs, error: diffsError, refetch: refetchDiffs } = useDiffs();

    const isLoading = loadingFeed && loadingDiffs;
    const error = feedError || diffsError;

    // Merge feed entries from both endpoints
    const feedEntries = feedData?.feed ?? [];

    // Also flatten diffs into feed-like entries if feed is empty
    const diffsAsEntries = (diffsData?.items ?? []).flatMap(item =>
        (item.changes ?? []).map(change => ({
            diffId: item.diffId,
            diffType: item.diffType,
            drugName: item.drugName,
            payerName: item.payerName,
            indication: change.indication ?? item.indicationName ?? "",
            field: change.field,
            severity: change.severity,
            humanSummary: change.humanSummary,
            oldValue: change.oldValue,
            newValue: change.newValue,
            generatedAt: item.generatedAt,
        }))
    );

    // Use feed entries if available, otherwise fall back to diffs
    const allEntries = feedEntries.length > 0 ? feedEntries : diffsAsEntries;

    // Apply filters
    const filtered = allEntries.filter(item => {
        if (!isWithinRange(item.generatedAt, timeRange)) return false;
        if (severityFilter !== "all" && item.severity !== severityFilter) return false;
        return true;
    });

    const toggle = (id: string) => {
        setExpanded(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
    };

    const handleRefresh = () => {
        refetchFeed();
        refetchDiffs();
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
                    {/* Time range dropdown */}
                    <div className="relative">
                        <Button
                            variant="outline"
                            className="bg-card"
                            onClick={() => { setTimeDropdown(!timeDropdown); setFilterDropdown(false); }}
                        >
                            <Calendar className="mr-2 h-4 w-4" />
                            {timeRangeLabels[timeRange]}
                            <ChevronDown className="ml-2 h-3 w-3" />
                        </Button>
                        {timeDropdown && (
                            <div className="absolute right-0 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-lg overflow-hidden min-w-[160px]">
                                {(Object.keys(timeRangeLabels) as TimeRange[]).map(range => (
                                    <button
                                        key={range}
                                        className={`w-full text-left px-4 py-2 text-sm hover:bg-muted/40 transition-colors ${timeRange === range ? "font-semibold text-primary" : "text-foreground"}`}
                                        onClick={() => { setTimeRange(range); setTimeDropdown(false); }}
                                    >
                                        {timeRangeLabels[range]}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Severity filter dropdown */}
                    <div className="relative">
                        <Button
                            variant="outline"
                            className="bg-card"
                            onClick={() => { setFilterDropdown(!filterDropdown); setTimeDropdown(false); }}
                        >
                            <Filter className="mr-2 h-4 w-4" />
                            {severityFilter === "all" ? "All Severity" : severityFilter}
                            <ChevronDown className="ml-2 h-3 w-3" />
                        </Button>
                        {filterDropdown && (
                            <div className="absolute right-0 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-lg overflow-hidden min-w-[160px]">
                                {(["all", "breaking", "restrictive", "relaxed"] as SeverityFilter[]).map(sev => (
                                    <button
                                        key={sev}
                                        className={`w-full text-left px-4 py-2 text-sm hover:bg-muted/40 transition-colors ${severityFilter === sev ? "font-semibold text-primary" : "text-foreground"}`}
                                        onClick={() => { setSeverityFilter(sev); setFilterDropdown(false); }}
                                    >
                                        {sev === "all" ? "All Severity" : sev.charAt(0).toUpperCase() + sev.slice(1)}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <Button variant="outline" className="bg-card" onClick={handleRefresh} disabled={isLoading}>
                        Refresh
                    </Button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error instanceof Error ? error.message : "Failed to load change feed"}
                </div>
            )}

            {/* Stats bar */}
            {!isLoading && allEntries.length > 0 && (
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span>{filtered.length} change{filtered.length !== 1 ? "s" : ""} shown</span>
                    {filtered.length !== allEntries.length && (
                        <span className="text-muted-foreground/50">({allEntries.length} total)</span>
                    )}
                    {filtered.filter(e => e.severity === "breaking").length > 0 && (
                        <>
                            <span className="text-muted-foreground/30">·</span>
                            <span className="text-destructive font-medium">
                                {filtered.filter(e => e.severity === "breaking").length} breaking
                            </span>
                        </>
                    )}
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
            ) : filtered.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border px-6 py-16 text-center space-y-3">
                    <p className="text-sm text-muted-foreground">
                        {allEntries.length === 0
                            ? "No policy changes yet. Upload a second version of an existing policy to generate temporal diffs."
                            : `No changes match the current filters. Showing 0 of ${allEntries.length} total.`
                        }
                    </p>
                    {allEntries.length > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => { setTimeRange("all"); setSeverityFilter("all"); }}
                        >
                            Clear filters
                        </Button>
                    )}
                </div>
            ) : (
                <div className="relative border-l border-border ml-4 pl-8 space-y-8">
                    {filtered.map((item, idx) => {
                        const itemKey = `${item.diffId}-${item.field}-${idx}`;
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
