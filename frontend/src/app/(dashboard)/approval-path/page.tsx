"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, FileSignature, AlertTriangle, AlertCircle, Loader2, Sparkles } from "lucide-react";

const payers = [
    {
        name: "Aetna",
        score: 92,
        status: "Likely Approved",
        color: "success" as const,
        items: [
            { ok: true,  warn: false, text: "All step therapy met (12+ wks)" },
            { ok: true,  warn: false, text: "Prescriber match" },
        ],
    },
    {
        name: "Cigna",
        score: 88,
        status: "Likely Approved",
        color: "warning" as const,
        items: [
            { ok: true,  warn: false, text: "Step therapy met" },
            { ok: false, warn: true,  text: "Minor gap: disease activity doc" },
        ],
    },
    {
        name: "UnitedHealthcare",
        score: 61,
        status: "Gap Detected",
        color: "destructive" as const,
        items: [
            { ok: false, warn: false, text: "Two DMARDs required" },
            { ok: false, warn: false, text: "Must try Amjevita first" },
        ],
    },
];

const colorMap = {
    success:     { border: "border-success/40",     score: "text-success",     badge: "bg-success/10 text-success border-success/20",     bar: "bg-success" },
    warning:     { border: "border-warning/40",     score: "text-warning",     badge: "bg-warning/10 text-warning border-warning/20",     bar: "bg-warning" },
    destructive: { border: "border-destructive/40", score: "text-destructive", badge: "bg-destructive/10 text-destructive border-destructive/20", bar: "bg-destructive" },
};

export default function ApprovalPathPage() {
    const [generating, setGenerating] = useState(false);
    const [evaluated, setEvaluated] = useState(false);
    const [memoOpen, setMemoOpen] = useState(false);

    const handleGenerate = () => {
        setGenerating(true);
        setTimeout(() => {
            setGenerating(false);
            setEvaluated(true);
        }, 1500);
    };

    return (
        <div className="h-full flex flex-col p-6 gap-5">
            {/* Header */}
            <div className="shrink-0">
                <h2 className="text-3xl font-bold tracking-tight">Approval Path Generator</h2>
                <p className="text-muted-text mt-1">Score a patient profile against extracted payer criteria and generate a PA memo.</p>
            </div>

            {/* Body */}
            <div className="flex flex-1 min-h-0 gap-0 border border-border rounded-xl overflow-hidden">

                {/* ── LEFT: Form ── */}
                <div className="w-[340px] shrink-0 flex flex-col border-r border-border bg-card">
                    <div className="px-6 py-5 border-b border-border">
                        <p className="text-xs font-semibold uppercase tracking-widest text-muted-text">Patient Profile</p>
                    </div>

                    <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
                        {/* Drug & Indication */}
                        <div className="space-y-4">
                            <p className="text-xs font-medium text-muted-text uppercase tracking-wider">Drug & Indication</p>
                            <div className="space-y-2">
                                <Label className="text-xs">Drug</Label>
                                <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                    <option>Infliximab</option>
                                    <option>Adalimumab</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs">Indication</Label>
                                <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                    <option>Rheumatoid Arthritis</option>
                                    <option>Crohn&apos;s Disease</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs">ICD-10 Code</Label>
                                <Input defaultValue="M05.79" className="h-9 font-mono bg-background text-sm" />
                            </div>
                        </div>

                        {/* Prior Treatment */}
                        <div className="space-y-3 pt-1 border-t border-border">
                            <p className="text-xs font-medium text-muted-text uppercase tracking-wider pt-3">Prior Treatment</p>
                            {[
                                { drug: "Methotrexate", weeks: 16 },
                                { drug: "Inflectra",    weeks: 14 },
                            ].map((trial, i) => (
                                <div key={i} className="rounded-lg border border-border bg-background p-3 space-y-2">
                                    <Input defaultValue={trial.drug} className="h-8 font-mono text-sm bg-transparent border-0 px-0 focus-visible:ring-0 focus-visible:ring-offset-0" />
                                    <div className="flex gap-2">
                                        <Input defaultValue={String(trial.weeks)} type="number" className="h-7 w-16 text-right font-mono text-xs bg-muted border-border" />
                                        <span className="text-xs text-muted-text self-center">wks</span>
                                        <select className="flex-1 h-7 rounded-md border border-input bg-muted px-2 text-xs text-primary-text">
                                            <option>Inadequate Response</option>
                                            <option>Intolerance</option>
                                        </select>
                                    </div>
                                </div>
                            ))}
                            <Button variant="outline" size="sm" className="w-full text-xs h-8 border-dashed">+ Add Trial</Button>
                        </div>

                        {/* Prescriber */}
                        <div className="space-y-3 pt-1 border-t border-border">
                            <p className="text-xs font-medium text-muted-text uppercase tracking-wider pt-3">Prescriber</p>
                            <div className="space-y-2">
                                <Label className="text-xs">Specialty</Label>
                                <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                    <option>Rheumatologist</option>
                                    <option>Gastroenterologist</option>
                                    <option>Dermatologist</option>
                                    <option>Primary Care</option>
                                    <option>Other / Not Specified</option>
                                </select>
                            </div>
                            <div className="space-y-2.5 pt-1">
                                <label className="flex items-center gap-2.5 cursor-pointer">
                                    <Checkbox id="c1" defaultChecked />
                                    <span className="text-sm">Diagnosis documented</span>
                                </label>
                                <label className="flex items-center gap-2.5 cursor-pointer">
                                    <Checkbox id="c2" defaultChecked />
                                    <span className="text-sm">High disease activity documented</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Evaluate button — pinned */}
                    <div className="px-6 py-4 border-t border-border shrink-0">
                        <Button className="w-full font-semibold" onClick={handleGenerate} disabled={generating}>
                            {generating
                                ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Evaluating...</>
                                : <><Sparkles className="mr-2 h-4 w-4" /> Evaluate Profile</>
                            }
                        </Button>
                    </div>
                </div>

                {/* ── RIGHT: Results ── */}
                <div className="flex-1 flex flex-col overflow-y-auto bg-background">
                    {!evaluated ? (
                        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-12">
                            <div className="h-12 w-12 rounded-full bg-white/5 flex items-center justify-center">
                                <Sparkles className="h-5 w-5 text-muted-text" />
                            </div>
                            <p className="font-medium text-foreground/70">No evaluation yet</p>
                            <p className="text-sm text-muted-text max-w-xs">Fill in the patient profile and click <span className="text-foreground/80 font-medium">Evaluate Profile</span> to score coverage likelihood across payers.</p>
                        </div>
                    ) : (
                        <div className="p-6 space-y-6">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-widest text-muted-text">Coverage Likelihood</p>
                                <p className="text-sm text-muted-text mt-0.5">Infliximab · Rheumatoid Arthritis · M05.79</p>
                            </div>

                            {/* Score cards */}
                            <div className="grid grid-cols-3 gap-4">
                                {payers.map((payer) => {
                                    const c = colorMap[payer.color];
                                    return (
                                        <div key={payer.name} className={`rounded-xl border ${c.border} bg-card flex flex-col overflow-hidden`}>
                                            {/* Score header */}
                                            <div className="p-5 flex items-start justify-between">
                                                <div>
                                                    <p className="font-semibold text-base">{payer.name}</p>
                                                    <span className={`inline-block mt-2 text-[11px] font-medium px-2 py-0.5 rounded-full border ${c.badge}`}>
                                                        {payer.status}
                                                    </span>
                                                </div>
                                                <div className="text-right">
                                                    <span className={`text-4xl font-bold font-mono ${c.score}`}>{payer.score}</span>
                                                    <span className="text-xs text-muted-text font-mono block">/100</span>
                                                </div>
                                            </div>

                                            {/* Score bar */}
                                            <div className="mx-5 h-1 rounded-full bg-white/5 mb-4">
                                                <div className={`h-full rounded-full ${c.bar}`} style={{ width: `${payer.score}%` }} />
                                            </div>

                                            {/* Criteria list */}
                                            <div className="px-5 pb-4 space-y-2 flex-1">
                                                {payer.items.map((item, i) => (
                                                    <div key={i} className="flex items-start gap-2 text-sm">
                                                        {item.ok
                                                            ? <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                                                            : item.warn
                                                                ? <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                                                                : <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                                        }
                                                        <span className={`leading-snug ${item.ok ? "text-muted-text" : item.warn ? "text-warning" : "text-destructive"}`}>
                                                            {item.text}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>

                                            {/* Action */}
                                            <div className="px-5 pb-5">
                                                {payer.color !== "destructive" ? (
                                                    <Button variant="outline" size="sm" className="w-full text-xs" onClick={() => setMemoOpen(true)}>
                                                        <FileSignature className="mr-2 h-3.5 w-3.5" /> Generate PA Memo
                                                    </Button>
                                                ) : (
                                                    <Button variant="outline" size="sm" className="w-full text-xs opacity-40" disabled>
                                                        Criteria Not Met
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Memo */}
                            {memoOpen && (
                                <Card className="border-border">
                                    <CardHeader className="border-b border-border pb-4">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <CardTitle className="text-base font-semibold">Prior Authorization Justification Memo</CardTitle>
                                                <p className="text-xs text-muted-text mt-1 font-mono">Aetna · CPB 0321 · Feb 12, 2026</p>
                                            </div>
                                            <Button size="sm" variant="outline" className="text-xs">Copy</Button>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="p-6">
                                        <div className="prose prose-invert max-w-none text-sm text-primary-text leading-relaxed font-serif space-y-3">
                                            <p><strong>To:</strong> Aetna Prior Authorization Department</p>
                                            <p><strong>Subject:</strong> Prior Authorization Request — Infliximab</p>
                                            <p>Per Aetna&apos;s Clinical Policy Bulletin 0321 for Infliximab Products (Effective February 12, 2026), this patient meets the initial authorization criteria as follows:</p>
                                            <p><strong>1. Diagnosis:</strong> Confirmed severely active Rheumatoid Arthritis (ICD-10: M05.79) with documented high disease activity.</p>
                                            <p><strong>2. Step Therapy:</strong> The patient completed a 16-week trial of Methotrexate (inadequate response) and a 14-week trial of Inflectra per Section II.B of CPB 0321.</p>
                                            <p><strong>3. Prescriber:</strong> Board-certified Rheumatologist — specialist requirement satisfied.</p>
                                            <p>All criteria are met with documentation available upon request. We request immediate prior authorization for Infliximab therapy.</p>
                                            <p>Sincerely,<br />[Consultant / Provider Name]</p>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
