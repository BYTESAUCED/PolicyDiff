"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { UploadCloud, CheckCircle2, Loader2, FileText, ArrowRight } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

export default function PolicyUploadPage() {
    const [uploadState, setUploadState] = useState<"idle" | "uploading" | "extracting" | "complete">("idle");

    const handleUpload = (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();
        setUploadState("uploading");
        setTimeout(() => setUploadState("extracting"), 1500);
        setTimeout(() => setUploadState("complete"), 4500);
    };

    return (
        <div className="h-full flex flex-col p-6 gap-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Policy Upload</h2>
                <p className="text-muted-text mt-1">
                    Upload medical benefit drug policies for automated extraction and criteria normalization.
                </p>
            </div>

            <div className="flex flex-row flex-1 min-h-0 items-stretch border border-border rounded-xl overflow-hidden bg-[#111113]">
                {/* Left — Drop zone + progress */}
                <div className="flex-1 flex flex-col gap-4 p-6">
                    <Card className={cn(
                        "border-dashed border-2 transition-all group cursor-pointer hover:border-primary/50 bg-[#111113] flex-1",
                        uploadState === 'idle' ? 'border-border' : 'border-primary/50'
                    )}>
                        <CardContent className="flex flex-col items-center justify-center h-full text-center gap-4">
                            <div className="p-5 rounded-full bg-white/5 group-hover:bg-primary/10 transition-colors">
                                <UploadCloud className="h-10 w-10 text-muted-text group-hover:text-primary transition-colors" />
                            </div>
                            <div>
                                <p className="text-base font-semibold">Drag & drop policy PDF</p>
                                <p className="text-sm text-muted-text mt-1">or click to browse local files</p>
                            </div>
                            <p className="text-xs text-muted-text/50 font-mono">PDF · max 50 MB</p>
                        </CardContent>
                    </Card>

                    {uploadState !== "idle" && (
                        <Card className="shrink-0 border-primary/20 bg-primary/5">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Extraction Progress</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center gap-3">
                                    {uploadState === "uploading" ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <CheckCircle2 className="h-4 w-4 text-success" />}
                                    <span className="text-sm">Uploading document</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {uploadState === "extracting" ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : (uploadState === "complete" ? <CheckCircle2 className="h-4 w-4 text-success" /> : <div className="h-4 w-4 rounded-full border border-muted" />)}
                                    <span className="text-sm">Extracting text via Textract</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {uploadState === "complete" ? <CheckCircle2 className="h-4 w-4 text-success" /> : <div className="h-4 w-4 rounded-full border border-muted" />}
                                    <span className="text-sm">Normalizing policy criteria</span>
                                </div>
                                {uploadState === "complete" && (
                                    <div className="pt-3 mt-1 border-t border-border space-y-3">
                                        <div className="rounded-md bg-success/10 border border-success/20 p-3">
                                            <p className="text-xs font-semibold text-success flex items-center gap-2">
                                                <FileText className="h-4 w-4" /> Extracted 12 indications
                                            </p>
                                        </div>
                                        <Button asChild variant="outline" className="w-full font-medium">
                                            <Link href="/explorer">
                                                View extracted criteria <ArrowRight className="ml-2 h-4 w-4" />
                                            </Link>
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Separator */}
                <div className="w-px bg-border shrink-0" />

                {/* Right — Metadata form */}
                <div className="flex-1 flex flex-col p-8">
                    <div className="mb-8">
                        <h3 className="text-lg font-semibold">Document Metadata</h3>
                        <p className="text-sm text-muted-text mt-0.5">Fill in details before uploading.</p>
                    </div>
                    <div className="flex-1 flex flex-col">
                        <form onSubmit={handleUpload} className="flex flex-col flex-1 gap-5">
                            <div className="flex-1 space-y-5">
                                <div className="space-y-2">
                                    <Label htmlFor="payer">Payer Name</Label>
                                    <select id="payer" className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                        <option>UnitedHealthcare</option>
                                        <option>Aetna</option>
                                        <option>Cigna</option>
                                        <option>Anthem</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="planType">Plan Type</Label>
                                    <select id="planType" className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                        <option>Commercial</option>
                                        <option>Medicare Advantage</option>
                                        <option>Medicaid</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="title">Document Title</Label>
                                    <Input id="title" placeholder="e.g. Infliximab Medical Benefit Policy" className="bg-background border-border" />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="date">Effective Date</Label>
                                    <Input id="date" type="date" className="bg-background border-border font-mono text-sm" />
                                </div>
                            </div>

                            <Button type="submit" size="lg" className="w-full font-semibold mt-auto" disabled={uploadState !== "idle"}>
                                {uploadState === "idle" ? "Upload and Extract" : "Processing..."}
                            </Button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}
