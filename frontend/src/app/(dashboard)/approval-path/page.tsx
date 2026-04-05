"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
    CheckCircle2, FileSignature, AlertTriangle, AlertCircle,
    Loader2, Sparkles, Copy, Check
} from "lucide-react";
import { useScoreApprovalPath, useGenerateMemo } from "@/hooks/use-api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PriorTrial {
    drug: string;
    weeks: number;
    outcome: string;
}

type StatusColor = "success" | "warning" | "destructive";

function scoreToColor(score: number): StatusColor {
    if (score >= 80) return "success";
    if (score >= 55) return "warning";
    return "destructive";
}

const colorMap: Record<StatusColor, {
    border: string; score: string; badge: string; bar: string;
}> = {
    success:     { border: "border-success/40",     score: "text-success",     badge: "bg-success/10 text-success border-success/20",         bar: "bg-success" },
    warning:     { border: "border-warning/40",     score: "text-warning",     badge: "bg-warning/10 text-warning border-warning/20",         bar: "bg-warning" },
    destructive: { border: "border-destructive/40", score: "text-destructive", badge: "bg-destructive/10 text-destructive border-destructive/20", bar: "bg-destructive" },
};

export default function ApprovalPathPage() {
    // Form state
    const [drug, setDrug] = useState("Infliximab");
    const [indication, setIndication] = useState("Rheumatoid Arthritis");
    const [icd10, setIcd10] = useState("M05.79");
    const [prescriberSpecialty, setPrescriberSpecialty] = useState("Rheumatologist");
    const [diagnosisDocumented, setDiagnosisDocumented] = useState(true);
    const [highDiseaseActivity, setHighDiseaseActivity] = useState(true);
    const [trials, setTrials] = useState<PriorTrial[]>([
        { drug: "Methotrexate", weeks: 16, outcome: "Inadequate Response" },
        { drug: "Inflectra",    weeks: 14, outcome: "Inadequate Response" },
    ]);

    // Results state
    const [error, setError] = useState<string | null>(null);
    const [approvalPathId, setApprovalPathId] = useState<string | null>(null);
    const [payerScores, setPayerScores] = useState<{ payerName: string; score: number; status: string; gaps: string[]; meetsCriteria: boolean }[]>([]);

    // Memo state
    const [memoLoading, setMemoLoading] = useState<Record<string, boolean>>({});
    const [memos, setMemos] = useState<Record<string, { memoText: string; policyTitle: string; effectiveDate: string }>>({});
    const [openMemo, setOpenMemo] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    const scoreMutation = useScoreApprovalPath();
    const memoMutation = useGenerateMemo();
    const generating = scoreMutation.isPending;
    const evaluated = payerScores.length > 0;

    const addTrial = () => setTrials(prev => [...prev, { drug: "", weeks: 12, outcome: "Inadequate Response" }]);
    const updateTrial = (i: number, field: keyof PriorTrial, value: string | number) => {
        setTrials(prev => prev.map((t, idx) => idx === i ? { ...t, [field]: value } : t));
    };
    const removeTrial = (i: number) => setTrials(prev => prev.filter((_, idx) => idx !== i));

    const handleGenerate = () => {
        setError(null);
        setPayerScores([]);
        setApprovalPathId(null);
        setMemos({});
        setOpenMemo(null);

        scoreMutation.mutate(
            {
                drugName: drug.toLowerCase(),
                indicationName: indication,
                icd10Code: icd10,
                patientProfile: {
                    priorDrugsTried: trials.map(t => ({
                        drugName: t.drug,
                        durationWeeks: t.weeks,
                        outcome: t.outcome,
                    })),
                    prescriberSpecialty,
                    diagnosisDocumented,
                    diseaseActivityScore: highDiseaseActivity ? "high" : "moderate",
                },
            },
            {
                onSuccess: (data) => {
                    setApprovalPathId(data.approvalPathId);
                    setPayerScores(data.payerScores ?? []);
                },
                onError: (err) => {
                    setError(err instanceof Error ? err.message : "Evaluation failed. Please try again.");
                },
            }
        );
    };

    const handleGenerateMemo = (payerName: string) => {
        if (!approvalPathId) return;
        setMemoLoading(prev => ({ ...prev, [payerName]: true }));
        memoMutation.mutate(
            { approvalPathId, payerName },
            {
                onSuccess: (data) => {
                    setMemos(prev => ({ ...prev, [payerName]: data }));
                    setOpenMemo(payerName);
                    setMemoLoading(prev => ({ ...prev, [payerName]: false }));
                },
                onError: (err) => {
                    setError(err instanceof Error ? err.message : "Memo generation failed");
                    setMemoLoading(prev => ({ ...prev, [payerName]: false }));
                },
            }
        );
    };

    const handleCopy = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
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
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono text-primary-text outline-none focus:ring-1 focus:ring-primary/50"
                                    value={drug}
                                    onChange={e => setDrug(e.target.value)}
                                >
                                    <option>Infliximab</option>
                                    <option>Adalimumab</option>
                                    <option>Ustekinumab</option>
                                    <option>Rituximab</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs">Indication</Label>
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50"
                                    value={indication}
                                    onChange={e => setIndication(e.target.value)}
                                >
                                    <option>Rheumatoid Arthritis</option>
                                    <option>Crohn&apos;s Disease</option>
                                    <option>Psoriatic Arthritis</option>
                                    <option>Plaque Psoriasis</option>
                                    <option>Ulcerative Colitis</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs">ICD-10 Code</Label>
                                <Input
                                    value={icd10}
                                    onChange={e => setIcd10(e.target.value)}
                                    className="h-9 font-mono bg-background text-sm"
                                />
                            </div>
                        </div>

                        {/* Prior Treatment */}
                        <div className="space-y-3 pt-1 border-t border-border">
                            <p className="text-xs font-medium text-muted-text uppercase tracking-wider pt-3">Prior Treatment</p>
                            {trials.map((trial, i) => (
                                <div key={i} className="rounded-lg border border-border bg-background p-3 space-y-2">
                                    <div className="flex items-center gap-2">
                                        <Input
                                            value={trial.drug}
                                            onChange={e => updateTrial(i, "drug", e.target.value)}
                                            className="h-8 font-mono text-sm bg-transparent border-0 px-0 focus-visible:ring-0 focus-visible:ring-offset-0 flex-1"
                                            placeholder="Drug name"
                                        />
                                        <button
                                            onClick={() => removeTrial(i)}
                                            className="text-muted-foreground/40 hover:text-destructive text-xs shrink-0"
                                        >
                                            ×
                                        </button>
                                    </div>
                                    <div className="flex gap-2">
                                        <Input
                                            value={String(trial.weeks)}
                                            type="number"
                                            min={1}
                                            onChange={e => updateTrial(i, "weeks", parseInt(e.target.value) || 0)}
                                            className="h-7 w-16 text-right font-mono text-xs bg-muted border-border"
                                        />
                                        <span className="text-xs text-muted-text self-center">wks</span>
                                        <select
                                            className="flex-1 h-7 rounded-md border border-input bg-muted px-2 text-xs text-primary-text"
                                            value={trial.outcome}
                                            onChange={e => updateTrial(i, "outcome", e.target.value)}
                                        >
                                            <option>Inadequate Response</option>
                                            <option>Intolerance</option>
                                            <option>Contraindication</option>
                                        </select>
                                    </div>
                                </div>
                            ))}
                            <Button variant="outline" size="sm" className="w-full text-xs h-8 border-dashed" onClick={addTrial}>
                                + Add Trial
                            </Button>
                        </div>

                        {/* Prescriber */}
                        <div className="space-y-3 pt-1 border-t border-border">
                            <p className="text-xs font-medium text-muted-text uppercase tracking-wider pt-3">Prescriber</p>
                            <div className="space-y-2">
                                <Label className="text-xs">Specialty</Label>
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50"
                                    value={prescriberSpecialty}
                                    onChange={e => setPrescriberSpecialty(e.target.value)}
                                >
                                    <option>Rheumatologist</option>
                                    <option>Gastroenterologist</option>
                                    <option>Dermatologist</option>
                                    <option>Primary Care</option>
                                    <option>Other / Not Specified</option>
                                </select>
                            </div>
                            <div className="space-y-2.5 pt-1">
                                <label className="flex items-center gap-2.5 cursor-pointer">
                                    <Checkbox
                                        id="c1"
                                        checked={diagnosisDocumented}
                                        onCheckedChange={v => setDiagnosisDocumented(!!v)}
                                    />
                                    <span className="text-sm">Diagnosis documented</span>
                                </label>
                                <label className="flex items-center gap-2.5 cursor-pointer">
                                    <Checkbox
                                        id="c2"
                                        checked={highDiseaseActivity}
                                        onCheckedChange={v => setHighDiseaseActivity(!!v)}
                                    />
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
                    {error && (
                        <div className="m-6 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            {error}
                        </div>
                    )}

                    {generating ? (
                        <div className="p-6 space-y-6">
                            <div className="space-y-1">
                                <Skeleton className="h-4 w-40" />
                                <Skeleton className="h-3 w-56" />
                            </div>
                            <div className="grid grid-cols-3 gap-4">
                                {[0, 1, 2].map(i => (
                                    <div key={i} className="rounded-xl border border-border p-5 space-y-4">
                                        <Skeleton className="h-5 w-24" />
                                        <Skeleton className="h-10 w-16" />
                                        <Skeleton className="h-1 w-full" />
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-3/4" />
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : !evaluated ? (
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
                                <p className="text-sm text-muted-text mt-0.5">{drug} · {indication} · {icd10}</p>
                            </div>

                            {payerScores.length === 0 ? (
                                <div className="rounded-lg border border-dashed border-border px-6 py-12 text-center text-sm text-muted-foreground">
                                    No payer criteria found for this drug. Upload payer policies first.
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {payerScores.map((payer) => {
                                        const color = scoreToColor(payer.score);
                                        const c = colorMap[color];
                                        const memoLoaded = memos[payer.payerName];
                                        const isLoadingMemo = memoLoading[payer.payerName];

                                        return (
                                            <div key={payer.payerName} className={`rounded-xl border ${c.border} bg-card flex flex-col overflow-hidden`}>
                                                {/* Score header */}
                                                <div className="p-5 flex items-start justify-between">
                                                    <div>
                                                        <p className="font-semibold text-base">{payer.payerName}</p>
                                                        <span className={`inline-block mt-2 text-[11px] font-medium px-2 py-0.5 rounded-full border ${c.badge}`}>
                                                            {payer.status.replace(/_/g, " ")}
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

                                                {/* Gaps / criteria */}
                                                <div className="px-5 pb-4 space-y-2 flex-1">
                                                    {payer.gaps.length === 0 ? (
                                                        <div className="flex items-start gap-2 text-sm">
                                                            <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                                                            <span className="text-muted-text leading-snug">All criteria met</span>
                                                        </div>
                                                    ) : (
                                                        payer.gaps.slice(0, 3).map((gap, i) => (
                                                            <div key={i} className="flex items-start gap-2 text-sm">
                                                                {color === "warning"
                                                                    ? <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                                                                    : <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                                                                }
                                                                <span className={`leading-snug ${color === "warning" ? "text-warning" : "text-destructive"}`}>
                                                                    {gap}
                                                                </span>
                                                            </div>
                                                        ))
                                                    )}
                                                </div>

                                                {/* Action */}
                                                <div className="px-5 pb-5">
                                                    {payer.meetsCriteria || payer.score >= 50 ? (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            className="w-full text-xs"
                                                            disabled={isLoadingMemo}
                                                            onClick={() => {
                                                                if (memoLoaded) {
                                                                    setOpenMemo(openMemo === payer.payerName ? null : payer.payerName);
                                                                } else {
                                                                    handleGenerateMemo(payer.payerName);
                                                                }
                                                            }}
                                                        >
                                                            {isLoadingMemo
                                                                ? <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> Generating...</>
                                                                : <><FileSignature className="mr-2 h-3.5 w-3.5" /> {memoLoaded ? "View PA Memo" : "Generate PA Memo"}</>
                                                            }
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
                            )}

                            {/* Memo display */}
                            {openMemo && memos[openMemo] && (
                                <Card className="border-border">
                                    <CardHeader className="border-b border-border pb-4">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <CardTitle className="text-base font-semibold">Prior Authorization Justification Memo</CardTitle>
                                                <p className="text-xs text-muted-text mt-1 font-mono">
                                                    {openMemo} · {memos[openMemo].policyTitle} · {memos[openMemo].effectiveDate}
                                                </p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="text-xs"
                                                onClick={() => handleCopy(memos[openMemo].memoText)}
                                            >
                                                {copied ? <><Check className="h-3 w-3 mr-1" /> Copied</> : <><Copy className="h-3 w-3 mr-1" /> Copy</>}
                                            </Button>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="p-6">
                                        <div className="prose prose-invert max-w-none text-sm text-primary-text leading-relaxed font-serif whitespace-pre-wrap">
                                            {memos[openMemo].memoText}
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
