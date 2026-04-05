"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { UploadCloud, CheckCircle2, Loader2, FileText, ArrowRight, AlertCircle } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { apiFetch, ApiError } from "@/lib/api";

type UploadState = "idle" | "creating" | "uploading" | "extracting" | "complete" | "error";

interface PresignResponse {
    uploadUrl: string;
    policyDocId: string;
    s3Key: string;
}

interface StatusResponse {
    extractionStatus: string;
    extractionJobId?: string;
}

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 40; // 2 minutes max

export default function PolicyUploadPage() {
    const [uploadState, setUploadState] = useState<UploadState>("idle");
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [policyDocId, setPolicyDocId] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Form refs
    const payerRef = useRef<HTMLSelectElement>(null);
    const planTypeRef = useRef<HTMLSelectElement>(null);
    const titleRef = useRef<HTMLInputElement>(null);
    const dateRef = useRef<HTMLInputElement>(null);

    const pollStatus = async (docId: string): Promise<void> => {
        let attempts = 0;
        while (attempts < POLL_MAX_ATTEMPTS) {
            await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
            try {
                const status = await apiFetch<StatusResponse>(`/api/policies/${docId}/status`);
                if (status.extractionStatus === "complete" || status.extractionStatus === "review_required") {
                    setUploadState("complete");
                    return;
                }
                if (status.extractionStatus === "failed") {
                    throw new Error("Extraction failed on the server");
                }
            } catch (e) {
                if (e instanceof ApiError && e.status === 404) {
                    // Not yet visible — keep polling
                } else {
                    throw e;
                }
            }
            attempts++;
        }
        throw new Error("Extraction timed out. Check back later.");
    };

    const handleUpload = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!selectedFile) {
            setErrorMsg("Please select a PDF file to upload.");
            return;
        }

        setErrorMsg(null);
        setUploadState("creating");

        try {
            // Step 1: Get presigned URL — also checks for duplicates
            let presign: PresignResponse;
            try {
                presign = await apiFetch<PresignResponse>("/api/policies/upload-url", {
                    method: "POST",
                    body: JSON.stringify({
                        payerName: payerRef.current?.value,
                        planType: planTypeRef.current?.value,
                        documentTitle: titleRef.current?.value,
                        effectiveDate: dateRef.current?.value,
                    }),
                });
            } catch (e) {
                if (e instanceof ApiError && e.status === 409) {
                    setErrorMsg("A policy with the same payer, title, and effective date already exists. Delete the existing one first or change the effective date.");
                    setUploadState("error");
                    return;
                }
                throw e;
            }
            setPolicyDocId(presign.policyDocId);
            setUploadState("uploading");

            // Step 2: PUT file directly to S3 presigned URL (bypass proxy — direct S3)
            const s3Res = await fetch(presign.uploadUrl, {
                method: "PUT",
                headers: { "Content-Type": "application/pdf" },
                body: selectedFile,
            });

            if (!s3Res.ok) {
                throw new Error(`S3 upload failed: ${s3Res.status}`);
            }

            setUploadState("extracting");

            // Step 3: Poll for extraction completion
            await pollStatus(presign.policyDocId);

        } catch (e) {
            setErrorMsg(e instanceof ApiError ? e.message : (e instanceof Error ? e.message : "Upload failed"));
            setUploadState("error");
        }
    };

    const handleFileSelect = (file: File) => {
        if (file.type !== "application/pdf") {
            setErrorMsg("Only PDF files are supported.");
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            setErrorMsg("File exceeds 50 MB limit.");
            return;
        }
        setErrorMsg(null);
        setSelectedFile(file);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    };

    const isProcessing = uploadState !== "idle" && uploadState !== "complete" && uploadState !== "error";

    const stepDone = (step: "creating" | "uploading" | "extracting") => {
        const order: UploadState[] = ["creating", "uploading", "extracting", "complete"];
        return order.indexOf(uploadState) > order.indexOf(step);
    };

    const stepActive = (step: UploadState) => uploadState === step;

    return (
        <div className="h-full flex flex-col p-6 gap-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Policy Upload</h2>
                <p className="text-muted-text mt-1">
                    Upload medical benefit drug policies for automated extraction and criteria normalization.
                </p>
            </div>

            <div className="flex flex-row flex-1 min-h-0 items-stretch border border-border rounded-xl overflow-hidden bg-card">
                {/* Left — Drop zone + progress */}
                <div className="flex-1 flex flex-col gap-4 p-6">
                    <Card
                        className={cn(
                            "border-dashed border-2 transition-all group cursor-pointer hover:border-primary/50 bg-background flex-1",
                            dragOver ? "border-primary/70 bg-primary/5" : uploadState === "idle" ? "border-border" : "border-primary/50"
                        )}
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleDrop}
                    >
                        <CardContent className="flex flex-col items-center justify-center h-full text-center gap-4">
                            <div className="p-5 rounded-full bg-muted/70 group-hover:bg-primary/10 transition-colors">
                                <UploadCloud className="h-10 w-10 text-muted-text group-hover:text-primary transition-colors" />
                            </div>
                            <div>
                                {selectedFile ? (
                                    <>
                                        <p className="text-base font-semibold text-primary">{selectedFile.name}</p>
                                        <p className="text-sm text-muted-text mt-1">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                                    </>
                                ) : (
                                    <>
                                        <p className="text-base font-semibold">Drag & drop policy PDF</p>
                                        <p className="text-sm text-muted-text mt-1">or click to browse local files</p>
                                    </>
                                )}
                            </div>
                            <p className="text-xs text-muted-text/50 font-mono">PDF · max 50 MB</p>
                        </CardContent>
                    </Card>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="application/pdf"
                        className="hidden"
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                    />

                    {errorMsg && (
                        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            {errorMsg}
                        </div>
                    )}

                    {uploadState !== "idle" && uploadState !== "error" && (
                        <Card className="shrink-0 border-primary/20 bg-primary/5">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Extraction Progress</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center gap-3">
                                    {stepActive("creating") || stepActive("uploading")
                                        ? <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                        : <CheckCircle2 className="h-4 w-4 text-success" />
                                    }
                                    <span className="text-sm">Uploading document</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {stepActive("extracting")
                                        ? <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                        : stepDone("extracting") || uploadState === "complete"
                                            ? <CheckCircle2 className="h-4 w-4 text-success" />
                                            : <div className="h-4 w-4 rounded-full border border-muted" />
                                    }
                                    <span className="text-sm">Extracting text via Textract</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    {uploadState === "complete"
                                        ? <CheckCircle2 className="h-4 w-4 text-success" />
                                        : <div className="h-4 w-4 rounded-full border border-muted" />
                                    }
                                    <span className="text-sm">Normalizing policy criteria</span>
                                </div>
                                {uploadState === "complete" && (
                                    <div className="pt-3 mt-1 border-t border-border space-y-3">
                                        <div className="rounded-md bg-success/10 border border-success/20 p-3">
                                            <p className="text-xs font-semibold text-success flex items-center gap-2">
                                                <FileText className="h-4 w-4" /> Extraction complete
                                                {policyDocId && <span className="font-mono text-[10px] opacity-60">· {policyDocId.slice(0, 8)}</span>}
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
                                    <select ref={payerRef} id="payer" className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring">
                                        <option value="UnitedHealthcare">UnitedHealthcare</option>
                                        <option value="Aetna">Aetna</option>
                                        <option value="Cigna">Cigna</option>
                                        <option value="EmblemHealth">EmblemHealth</option>
                                        <option value="Prime Therapeutics">Prime Therapeutics</option>
                                        <option value="Florida Blue">Florida Blue</option>
                                        <option value="MCG">MCG</option>
                                        <option value="BCBS NC">BCBS NC</option>
                                        <option value="Priority Health">Priority Health</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="planType">Plan Type</Label>
                                    <select ref={planTypeRef} id="planType" className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring">
                                        <option>Commercial</option>
                                        <option>Medicare Advantage</option>
                                        <option>Medicaid</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="title">Document Title</Label>
                                    <Input ref={titleRef} id="title" placeholder="e.g. Infliximab Medical Benefit Policy" className="bg-background border-border" />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="date">Effective Date</Label>
                                    <Input ref={dateRef} id="date" type="date" className="bg-background border-border font-mono text-sm" />
                                </div>
                            </div>

                            <Button
                                type="submit"
                                size="lg"
                                className="mt-auto w-full bg-secondary text-secondary-foreground font-semibold hover:bg-secondary/90"
                                disabled={isProcessing || uploadState === "complete"}
                            >
                                {isProcessing ? (
                                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing...</>
                                ) : uploadState === "complete" ? (
                                    "Upload Complete"
                                ) : (
                                    "Upload and Extract"
                                )}
                            </Button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}
