"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BookOpen, Quote, ChevronDown, ArrowUp, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { apiFetch, ApiError } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Citation {
    payer: string;
    documentTitle: string;
    effectiveDate: string;
    excerpt: string;
}

interface QueryResponse {
    queryId: string;
    queryType: string;
    answer: string;
    citations: Citation[];
    dataCompleteness: string;
    responseTimeMs: number;
}

interface RecentQuery {
    queryId: string;
    queryText: string;
    queryType: string;
    createdAt: string;
}

interface Message {
    role: "user" | "assistant";
    content: string;
    citations?: Citation[];
    dataCompleteness?: string;
    error?: boolean;
}

const suggestedQueries = [
    "Which plans cover infliximab?",
    "UHC prior auth for Remicade",
    "Compare adalimumab step therapy",
    "Aetna CPB 0321 changes",
    "Rituximab biosimilar coverage",
];

export default function QueryInterfacePage() {
    const [query, setQuery] = useState("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isResponding, setIsResponding] = useState(false);
    const [citationsOpen, setCitationsOpen] = useState<Record<number, boolean>>({});
    const [recentQueries, setRecentQueries] = useState<RecentQuery[]>([]);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const isEmpty = messages.length === 0 && !isResponding;

    useEffect(() => {
        if (!isEmpty) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isResponding, isEmpty]);

    // Load recent queries for suggested chips
    const loadRecentQueries = useCallback(async () => {
        try {
            const data = await apiFetch<{ queries: RecentQuery[] }>("/api/queries");
            setRecentQueries(data.queries ?? []);
        } catch {
            // Non-critical — silently ignore
        }
    }, []);

    useEffect(() => {
        loadRecentQueries();
    }, [loadRecentQueries]);

    const handleQuery = async (q?: string) => {
        const text = (q ?? query).trim();
        if (!text || isResponding) return;

        setMessages(prev => [...prev, { role: "user", content: text }]);
        setQuery("");
        setIsResponding(true);

        try {
            // ADR: POST /api/query returns answer synchronously | backend calls Bedrock inline
            const result = await apiFetch<QueryResponse>("/api/query", {
                method: "POST",
                body: JSON.stringify({ queryText: text }),
            });

            setMessages(prev => [...prev, {
                role: "assistant",
                content: result.answer,
                citations: result.citations ?? [],
                dataCompleteness: result.dataCompleteness,
            }]);

            // Refresh recent queries list after successful query
            loadRecentQueries();
        } catch (e) {
            const msg = e instanceof ApiError ? e.message : "Query failed. Please try again.";
            setMessages(prev => [...prev, { role: "assistant", content: msg, error: true }]);
        } finally {
            setIsResponding(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleQuery();
        }
    };

    const toggleCitations = (idx: number) => {
        setCitationsOpen(prev => ({ ...prev, [idx]: !prev[idx] }));
    };

    // Show recent query texts as chips if no suggested queries match
    const chips = suggestedQueries;

    return (
        <div className="flex flex-col h-full relative">
            {/* ── EMPTY STATE ── */}
            {isEmpty && (
                <div className="flex-1 flex flex-col items-center justify-center px-6 pb-4 select-none">
                    <div className="mb-6">
                        <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                            <path d="M18 2C18 2 14 14 2 18C14 18 18 34 18 34C18 34 22 18 34 18C22 18 18 2 18 2Z" fill="url(#g1)" />
                            <defs>
                                <linearGradient id="g1" x1="2" y1="2" x2="34" y2="34" gradientUnits="userSpaceOnUse">
                                    <stop stopColor="#4285F4" />
                                    <stop offset="0.33" stopColor="#9B59B6" />
                                    <stop offset="0.66" stopColor="#E74C3C" />
                                    <stop offset="1" stopColor="#F39C12" />
                                </linearGradient>
                            </defs>
                        </svg>
                    </div>

                    <h1 className="text-4xl font-semibold tracking-tight text-foreground mb-1">
                        What would you like to know?
                    </h1>
                    <p className="text-base text-muted-foreground mb-10">
                        Ask anything about payer policies, step therapy, or coverage criteria.
                    </p>

                    <div className="w-full max-w-2xl">
                        <div className="relative rounded-3xl border border-border bg-card px-5 pt-4 pb-3 shadow-xl transition-colors focus-within:border-ring dark:border-white/10 dark:bg-[#1a1a1a] dark:focus-within:border-white/20">
                            <Textarea
                                ref={textareaRef}
                                placeholder="Ask PolicyDiff..."
                                className="min-h-[32px] max-h-[160px] w-full resize-none border-0 bg-transparent p-0 text-base text-foreground shadow-none placeholder:text-muted-foreground/60 focus-visible:ring-0 focus-visible:ring-offset-0"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={handleKeyDown}
                                rows={1}
                            />
                            <div className="flex items-center justify-end mt-3">
                                <Button
                                    size="icon"
                                    className="h-8 w-8 shrink-0 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90"
                                    disabled={!query.trim()}
                                    onClick={() => handleQuery()}
                                >
                                    <ArrowUp className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>

                        <div className="flex flex-wrap justify-center gap-2 mt-5">
                            {chips.map((sq, i) => (
                                <button
                                    key={i}
                                    onClick={() => handleQuery(sq)}
                                    className="rounded-full border border-border bg-card px-4 py-1.5 text-[13px] text-muted-foreground transition-all hover:border-ring/40 hover:bg-muted hover:text-foreground dark:border-white/10 dark:bg-[#1a1a1a] dark:hover:border-white/20"
                                >
                                    {sq}
                                </button>
                            ))}
                        </div>

                        {recentQueries.length > 0 && (
                            <p className="text-center text-xs text-muted-foreground/50 mt-4">
                                {recentQueries.length} previous {recentQueries.length === 1 ? "query" : "queries"} in history
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* ── CHAT THREAD ── */}
            {!isEmpty && (
                <div className="flex-1 overflow-y-auto">
                    <div className="max-w-2xl mx-auto w-full px-6 py-10 space-y-10">
                        {messages.map((msg, i) => (
                            <div key={i}>
                                {msg.role === "user" ? (
                                    <div className="flex justify-end">
                                        <div className="max-w-[80%] rounded-3xl rounded-tr-md border border-border bg-card px-5 py-3 text-sm leading-relaxed text-foreground dark:border-white/8 dark:bg-[#1a1a1a]">
                                            {msg.content}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex gap-3">
                                        <div className="shrink-0 mt-1">
                                            <svg width="20" height="20" viewBox="0 0 36 36" fill="none">
                                                <path d="M18 2C18 2 14 14 2 18C14 18 18 34 18 34C18 34 22 18 34 18C22 18 18 2 18 2Z" fill="url(#g2)" />
                                                <defs>
                                                    <linearGradient id="g2" x1="2" y1="2" x2="34" y2="34" gradientUnits="userSpaceOnUse">
                                                        <stop stopColor="#4285F4" />
                                                        <stop offset="0.5" stopColor="#9B59B6" />
                                                        <stop offset="1" stopColor="#E74C3C" />
                                                    </linearGradient>
                                                </defs>
                                            </svg>
                                        </div>
                                        <div className="flex-1 min-w-0 space-y-5">
                                            {msg.error ? (
                                                <div className="flex items-center gap-2 text-sm text-destructive">
                                                    <AlertCircle className="h-4 w-4 shrink-0" />
                                                    {msg.content}
                                                </div>
                                            ) : (
                                                <div className="prose prose-sm max-w-none text-foreground/90 prose-headings:text-foreground prose-p:leading-relaxed prose-p:text-foreground/80 prose-strong:text-foreground dark:prose-invert">
                                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                </div>
                                            )}

                                            {msg.dataCompleteness && msg.dataCompleteness !== "complete" && !msg.error && (
                                                <p className="text-xs text-amber-500/80 font-mono">
                                                    Data completeness: {msg.dataCompleteness}
                                                </p>
                                            )}

                                            {/* Citations accordion */}
                                            {msg.citations && msg.citations.length > 0 && (
                                                <div className="overflow-hidden rounded-2xl border border-border text-sm dark:border-white/8">
                                                    <button
                                                        className="flex w-full items-center justify-between px-4 py-3 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground dark:hover:bg-white/[0.03]"
                                                        onClick={() => toggleCitations(i)}
                                                    >
                                                        <div className="flex items-center gap-2">
                                                            <BookOpen className="h-3.5 w-3.5" />
                                                            <span className="text-xs">{msg.citations.length} source{msg.citations.length !== 1 ? "s" : ""} cited</span>
                                                        </div>
                                                        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${citationsOpen[i] ? "rotate-180" : ""}`} />
                                                    </button>
                                                    {citationsOpen[i] && (
                                                        <div className="divide-y divide-border border-t border-border dark:divide-white/8 dark:border-white/8">
                                                            {msg.citations.map((c, ci) => (
                                                                <div key={ci} className="px-4 py-3 space-y-2">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/60 dark:border-white/10">{c.payer}</span>
                                                                        <span className="text-xs text-foreground/70 font-medium">{c.documentTitle}</span>
                                                                        {c.effectiveDate && (
                                                                            <span className="text-xs text-muted-foreground/50">· {c.effectiveDate}</span>
                                                                        )}
                                                                    </div>
                                                                    {c.excerpt && (
                                                                        <div className="flex gap-2 border-l border-border pl-3 text-xs text-muted-foreground dark:border-white/10">
                                                                            <Quote className="h-3 w-3 shrink-0 mt-0.5 opacity-50" />
                                                                            <p className="italic leading-relaxed">{c.excerpt}</p>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}

                        {/* Typing indicator */}
                        {isResponding && (
                            <div className="flex gap-3">
                                <div className="shrink-0 mt-1">
                                    <svg width="20" height="20" viewBox="0 0 36 36" fill="none">
                                        <path d="M18 2C18 2 14 14 2 18C14 18 18 34 18 34C18 34 22 18 34 18C22 18 18 2 18 2Z" fill="url(#g3)" />
                                        <defs>
                                            <linearGradient id="g3" x1="2" y1="2" x2="34" y2="34" gradientUnits="userSpaceOnUse">
                                                <stop stopColor="#4285F4" />
                                                <stop offset="0.5" stopColor="#9B59B6" />
                                                <stop offset="1" stopColor="#E74C3C" />
                                            </linearGradient>
                                        </defs>
                                    </svg>
                                </div>
                                <div className="flex items-center gap-1 pt-1">
                                    <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:0ms]" />
                                    <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:150ms]" />
                                    <span className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:300ms]" />
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>
                </div>
            )}

            {/* ── BOTTOM INPUT BAR ── */}
            {!isEmpty && (
                <div className="shrink-0 px-6 py-4">
                    <div className="max-w-2xl mx-auto">
                        <div className="relative rounded-3xl border border-border bg-card px-5 pt-4 pb-3 transition-colors focus-within:border-ring dark:border-white/10 dark:bg-[#1a1a1a] dark:focus-within:border-white/20">
                            <Textarea
                                placeholder="Ask a follow-up..."
                                className="min-h-[24px] max-h-[160px] w-full resize-none border-0 bg-transparent p-0 text-sm text-foreground shadow-none placeholder:text-muted-foreground/60 focus-visible:ring-0 focus-visible:ring-offset-0"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={handleKeyDown}
                                rows={1}
                            />
                            <div className="flex items-center justify-end mt-3">
                                <Button
                                    size="icon"
                                    className="h-8 w-8 shrink-0 rounded-full bg-secondary text-secondary-foreground hover:bg-secondary/90"
                                    disabled={isResponding || !query.trim()}
                                    onClick={() => handleQuery()}
                                >
                                    <ArrowUp className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                        <p className="text-center text-[10px] text-muted-foreground/30 mt-2 font-mono">
                            anthropic.claude-sonnet · policy synthesis
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
