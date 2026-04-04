"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BookOpen, Quote, ChevronDown, ArrowUp } from "lucide-react";
import ReactMarkdown from "react-markdown";

const suggestedQueries = [
    "Which plans cover infliximab?",
    "UHC prior auth for Remicade",
    "Compare adalimumab step therapy",
    "Aetna CPB 0321 changes",
    "Rituximab biosimilar coverage",
];

const mockResponse = `### Step Therapy Requirements for Adalimumab: Aetna vs UHC

Both Aetna and UnitedHealthcare cover adalimumab (Humira and its biosimilars) for Rheumatoid Arthritis, but their step therapy requirements differ significantly.

| Payer | Preferred Products | Prior Therapy Required | Trial Duration |
|-------|-------------------|------------------------|----------------|
| **Aetna** | Cyltezo, Amjevita | **1 DMARD failure** (e.g., methotrexate) | 12 weeks |
| **UnitedHealthcare** | Amjevita | **2 failures** (DMARD + targeted conventional) | 14 weeks |

**Summary**: Aetna is **less restrictive** than UHC. Aetna requires one 12-week DMARD trial; UHC requires two prior therapies over 14 weeks.

*Based on ingested Commercial policies as of Q1 2026.*`;

interface Message {
    role: "user" | "assistant";
    content: string;
}

const citations = [
    {
        payer: "AETNA",
        doc: "CPB 0321 · Feb 12, 2026",
        quote: "Patient must have a documented inadequate response to at least one conventional DMARD for a minimum of 12 weeks prior to authorization.",
    },
    {
        payer: "UNITEDHEALTHCARE",
        doc: "Medical Benefit: Adalimumab · Jan 1, 2026",
        quote: "Authorization requires documentation demonstrating trial and failure of two prior therapies for no less than 14 weeks.",
    },
];

export default function QueryInterfacePage() {
    const [query, setQuery] = useState("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isResponding, setIsResponding] = useState(false);
    const [citationsOpen, setCitationsOpen] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const isEmpty = messages.length === 0 && !isResponding;

    useEffect(() => {
        if (!isEmpty) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isResponding, isEmpty]);

    const handleQuery = (q?: string) => {
        const text = q ?? query;
        if (!text.trim() || isResponding) return;
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setQuery("");
        setIsResponding(true);
        setTimeout(() => {
            setMessages((prev) => [...prev, { role: "assistant", content: mockResponse }]);
            setIsResponding(false);
        }, 1400);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleQuery();
        }
    };

    return (
        <div className="flex flex-col h-full relative">
            {/* ── EMPTY STATE ── centered hero */}
            {isEmpty && (
                <div className="flex-1 flex flex-col items-center justify-center px-6 pb-4 select-none">
                    {/* Gemini-style multicolor diamond */}
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

                    {/* Large centered input — Gemini style */}
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

                        {/* Pill suggestion chips */}
                        <div className="flex flex-wrap justify-center gap-2 mt-5">
                            {suggestedQueries.map((sq, i) => (
                                <button
                                    key={i}
                                    onClick={() => handleQuery(sq)}
                                    className="rounded-full border border-border bg-card px-4 py-1.5 text-[13px] text-muted-foreground transition-all hover:border-ring/40 hover:bg-muted hover:text-foreground dark:border-white/10 dark:bg-[#1a1a1a] dark:hover:border-white/20"
                                >
                                    {sq}
                                </button>
                            ))}
                        </div>
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
                                        {/* Gemini diamond avatar */}
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
                                            <div className="prose prose-sm max-w-none text-foreground/90 prose-headings:text-foreground prose-p:leading-relaxed prose-p:text-foreground/80 prose-strong:text-foreground dark:prose-invert">
                                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                                            </div>

                                            {/* Citations accordion */}
                                            <div className="overflow-hidden rounded-2xl border border-border text-sm dark:border-white/8">
                                                <button
                                                    className="flex w-full items-center justify-between px-4 py-3 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground dark:hover:bg-white/[0.03]"
                                                    onClick={() => setCitationsOpen(!citationsOpen)}
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <BookOpen className="h-3.5 w-3.5" />
                                                        <span className="text-xs">2 sources cited</span>
                                                    </div>
                                                    <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${citationsOpen ? "rotate-180" : ""}`} />
                                                </button>
                                                {citationsOpen && (
                                                    <div className="divide-y divide-border border-t border-border dark:divide-white/8 dark:border-white/8">
                                                        {citations.map((c, ci) => (
                                                            <div key={ci} className="px-4 py-3 space-y-2">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/60 dark:border-white/10">{c.payer}</span>
                                                                    <span className="text-xs text-foreground/70 font-medium">{c.doc}</span>
                                                                </div>
                                                                <div className="flex gap-2 border-l border-border pl-3 text-xs text-muted-foreground dark:border-white/10">
                                                                    <Quote className="h-3 w-3 shrink-0 mt-0.5 opacity-50" />
                                                                    <p className="italic leading-relaxed">{c.quote}</p>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
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

            {/* ── BOTTOM INPUT BAR (appears after first message) ── */}
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
