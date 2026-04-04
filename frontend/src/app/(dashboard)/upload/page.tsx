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

    const handleUpload = (e: React.FormEvent) => {
        e.preventDefault();
        setUploadState("uploading");
        setTimeout(() => setUploadState("extracting"), 1500);
        setTimeout(() => setUploadState("complete"), 4500);
    };

    return (
        <div className="p-8 max-w-3xl mx-auto space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Policy Upload</h2>
                <p className="text-muted-text mt-2">
                    Upload medical benefit drug policies for automated extraction and criteria normalization.
                </p>
            </div>

            <div className="space-y-6">
                <Card className={cn(
                    "border-dashed border-2 transition-all group cursor-pointer hover:border-primary/50 bg-[#111113]",
                    uploadState === 'idle' ? 'border-border' : 'border-primary/50'
                )}>
                    <CardContent className="flex flex-col items-center justify-center p-12 text-center h-48">
                        <div className="p-4 rounded-full bg-white/5 group-hover:bg-primary/10 transition-colors mb-4">
                            <UploadCloud className="h-8 w-8 text-muted-text group-hover:text-primary transition-colors" />
                        </div>
                        <p className="text-base font-semibold">Drag & drop policy PDF</p>
                        <p className="text-sm text-muted-text mt-1">or click to browse local files</p>
                    </CardContent>
                </Card>

                <Card className="bg-[#111113] border-border shadow-xl">
                    <CardHeader>
                        <CardTitle className="text-lg">Document Metadata</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleUpload} className="space-y-8">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-3">
                                    <Label htmlFor="payer">Payer Name</Label>
                                    <select id="payer" className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                        <option>UnitedHealthcare</option>
                                        <option>Aetna</option>
                                        <option>Cigna</option>
                                        <option>Anthem</option>
                                    </select>
                                </div>
                                <div className="space-y-3">
                                    <Label htmlFor="planType">Plan Type</Label>
                                    <select id="planType" className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm text-primary-text outline-none focus:ring-1 focus:ring-primary/50">
                                        <option>Commercial</option>
                                        <option>Medicare Advantage</option>
                                        <option>Medicaid</option>
                                    </select>
                                </div>
                                <div className="space-y-3">
                                    <Label htmlFor="title">Document Title</Label>
                                    <Input id="title" placeholder="e.g. Infliximab Medical Benefit Policy" className="bg-[#0A0A0A] border-border" />
                                </div>
                                <div className="space-y-3">
                                    <Label htmlFor="date">Effective Date</Label>
                                    <Input id="date" type="date" className="bg-[#0A0A0A] border-border font-mono text-sm" />
                                </div>
                            </div>

                            <Button type="submit" size="lg" className="w-full font-semibold" disabled={uploadState !== "idle"}>
                                {uploadState === "idle" ? "Upload and Extract" : "Processing..."}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {uploadState !== "idle" && (
                    <Card className="shadow-lg border-primary/20 bg-primary/5">
                        <CardHeader>
                            <CardTitle className="text-lg">Extraction Progress</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    {uploadState === "uploading" ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <CheckCircle2 className="h-4 w-4 text-success" />}
                                    <span className="text-sm">Uploading document</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {uploadState === "extracting" ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : (uploadState === "complete" ? <CheckCircle2 className="h-4 w-4 text-success" /> : <div className="h-4 w-4 rounded-full border border-muted" />)}
                                    <span className="text-sm">Extracting Text via Textract</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {uploadState === "complete" ? <CheckCircle2 className="h-4 w-4 text-success" /> : <div className="h-4 w-4 rounded-full border border-muted" />}
                                    <span className="text-sm">Normalizing Policy Criteria</span>
                                </div>
                            </div>
                            {uploadState === "complete" && (
                                <div className="pt-4 mt-4 border-t border-border">
                                    <div className="rounded-md bg-success/10 border border-success/20 p-3 mb-4">
                                        <p className="text-xs font-semibold text-success flex items-center">
                                            <FileText className="h-4 w-4 mr-2" /> Extracted 12 indications
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
        </div>
    );
}
