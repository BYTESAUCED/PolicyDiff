"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Filter, Search, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

const discordances = [
    {
        id: "dsc1",
        payer: "Aetna",
        drug: "Ustekinumab",
        criterion: "Step Therapy",
        medical: { val: "4 DMARD failures", sev: "destructive" },
        pharmacy: { val: "2 DMARD failures", sev: "warning" },
        mostRestrictive: "medical",
    },
    {
        id: "dsc2",
        payer: "Cigna",
        drug: "Infliximab",
        criterion: "Prescriber",
        medical: { val: "Rheumatologist only", sev: "destructive" },
        pharmacy: { val: "Any specialist", sev: "success" },
        mostRestrictive: "medical",
    },
    {
        id: "dsc3",
        payer: "UnitedHealthcare",
        drug: "Rituximab",
        criterion: "Trial Duration",
        medical: { val: "12 weeks", sev: "success" },
        pharmacy: { val: "16 weeks", sev: "destructive" },
        mostRestrictive: "pharmacy",
    },
    {
        id: "dsc4",
        payer: "Anthem",
        drug: "Adalimumab",
        criterion: "Step Therapy",
        medical: { val: "1 DMARD failure", sev: "success" },
        pharmacy: { val: "2 DMARD failures", sev: "destructive" },
        mostRestrictive: "pharmacy",
    },
];

const sevColor = (sev: string) =>
    sev === "destructive"
        ? "text-red-400"
        : sev === "warning"
            ? "text-amber-400"
            : "text-emerald-400";

export default function DiscordancePage() {
    const [searchQuery, setSearchQuery] = useState("");

    const filtered = discordances.filter(
        (d) =>
            d.payer.toLowerCase().includes(searchQuery.toLowerCase()) ||
            d.drug.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="p-6 max-w-7xl space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-bold tracking-tight">Discordance Alerts</h2>
                    <span className="text-xs font-mono text-destructive border border-destructive/30 rounded px-2 py-0.5">
                        {filtered.length} conflicts
                    </span>
                </div>
                <div className="flex gap-2">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Filter..."
                            className="pl-9 w-48"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" size="icon" className="shrink-0">
                        <Filter className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Table */}
            <div className="rounded-xl border border-border overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="border-b border-border hover:bg-transparent">
                            <TableHead className="h-10 px-5 font-medium text-xs uppercase tracking-wider">Drug</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Payer</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Criterion</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Med. Benefit</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Pharm. Benefit</TableHead>
                            <TableHead className="h-10 px-4 font-medium text-xs uppercase tracking-wider">Winner</TableHead>
                            <TableHead className="h-10 px-4 w-10" />
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filtered.map((item) => (
                            <TableRow key={item.id} className="border-border hover:bg-white/[0.02]">
                                <TableCell className="h-12 px-5 font-medium text-sm">{item.drug}</TableCell>
                                <TableCell className="h-12 px-4 text-sm text-muted-foreground">{item.payer}</TableCell>
                                <TableCell className="h-12 px-4">
                                    <span className="text-xs font-mono text-muted-foreground border border-border rounded px-2 py-0.5">
                                        {item.criterion}
                                    </span>
                                </TableCell>
                                <TableCell className={`h-14 px-4 text-sm font-medium ${sevColor(item.medical.sev)}`}>
                                    {item.medical.val}
                                </TableCell>
                                <TableCell className={`h-14 px-4 text-sm font-medium ${sevColor(item.pharmacy.sev)}`}>
                                    {item.pharmacy.val}
                                </TableCell>
                                <TableCell className="h-14 px-4">
                                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${item.mostRestrictive === "medical"
                                        ? "border-red-500/30 text-red-400 bg-red-500/5"
                                        : "border-amber-500/30 text-amber-400 bg-amber-500/5"
                                        }`}>
                                        {item.mostRestrictive === "medical" ? "Medical" : "Pharmacy"}
                                    </span>
                                </TableCell>
                                <TableCell className="h-14 px-4">
                                    <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground">
                                        <ArrowRight className="h-3.5 w-3.5" />
                                    </Button>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
