"use client";

import React, { useState, useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Download, TableProperties } from "lucide-react";

const matrixData = [
    {
        dimension: "Preferred product",
        uhc: { val: "Inflectra/Avsola rank 1", sev: "destructive" },
        aetna: { val: "Inflectra rank 1", sev: "warning" },
        cigna: { val: "Any infliximab", sev: "success" }
    },
    {
        dimension: "Step therapy drugs",
        uhc: { val: "Must fail biosimilar first", sev: "destructive" },
        aetna: { val: "Must fail one DMARD", sev: "warning" },
        cigna: { val: "No step therapy", sev: "success" }
    },
    {
        dimension: "Trial duration",
        uhc: { val: "14 weeks", sev: "destructive" },
        aetna: { val: "12 weeks", sev: "warning" },
        cigna: { val: "Not specified", sev: "success" }
    },
    {
        dimension: "Prescriber req",
        uhc: { val: "None", sev: "success" },
        aetna: { val: "Rheumatologist", sev: "destructive" },
        cigna: { val: "Specialist preferred", sev: "warning" }
    },
    {
        dimension: "Max frequency",
        uhc: { val: "Every 4 weeks", sev: "warning" },
        aetna: { val: "Every 8 weeks", sev: "success" },
        cigna: { val: "Every 8 weeks", sev: "success" }
    },
    {
        dimension: "Dosing limit",
        uhc: { val: "5mg/kg", sev: "warning" },
        aetna: { val: "10mg/kg", sev: "success" },
        cigna: { val: "5mg/kg", sev: "warning" }
    },
];

const SeverityCellRenderer = (params: any) => {
    const data = params.value;
    if (!data) return null;

    let bgClass = "bg-neutral text-white";
    let borderClass = "border-neutral/30";

    if (data.sev === "destructive") {
        bgClass = "bg-destructive/20 text-destructive";
        borderClass = "border-destructive/30";
    } else if (data.sev === "warning") {
        bgClass = "bg-warning/20 text-warning";
        borderClass = "border-warning/30";
    } else if (data.sev === "success") {
        bgClass = "bg-success/20 text-success";
        borderClass = "border-success/30";
    }

    return (
        <div className="flex items-center h-full w-full py-1">
            <div className={`px-3 py-1.5 min-h-[32px] flex items-center rounded-md border ${bgClass} ${borderClass} w-full text-xs font-semibold leading-tight shadow-sm`}>
                {data.val}
            </div>
        </div>
    );
};

export default function ComparisonMatrixPage() {
    const [rowData] = useState(matrixData);

    const [columnDefs] = useState<any>([
        {
            field: "dimension",
            headerName: "Dimension",
            pinned: "left",
            width: 200,
            cellClass: "font-semibold text-primary-text bg-card",
        },
        {
            field: "uhc",
            headerName: "UnitedHealthcare",
            width: 250,
            cellRenderer: SeverityCellRenderer,
        },
        {
            field: "aetna",
            headerName: "Aetna",
            width: 250,
            cellRenderer: SeverityCellRenderer,
        },
        {
            field: "cigna",
            headerName: "Cigna",
            width: 250,
            cellRenderer: SeverityCellRenderer,
        },
    ]);

    const defaultColDef = useMemo(() => ({
        resizable: true,
        sortable: true,
        filter: true,
        flex: 1,
        minWidth: 150,
    }), []);

    return (
        <div className="h-full flex flex-col p-6 space-y-6">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 shrink-0">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Comparison Matrix</h2>
                    <p className="text-muted-text mt-1">
                        Cross-payer evaluation of policy criteria restrictiveness.
                    </p>
                </div>

                <div className="flex items-center gap-3 bg-card p-2 px-4 rounded-lg border border-border">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-destructive"></div>
                        <span className="text-xs text-muted-text">Most Restrictive</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-warning"></div>
                        <span className="text-xs text-muted-text">Moderate</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-success"></div>
                        <span className="text-xs text-muted-text">Least Restrictive</span>
                    </div>
                </div>
            </div>

            <div className="flex gap-4 shrink-0">
                <div className="w-64 space-y-2">
                    <Label>Select Drug</Label>
                    <select className="flex h-10 w-full items-center rounded-md border border-input bg-card px-3 py-2 text-sm text-primary-text font-mono">
                        <option>Infliximab</option>
                        <option>Adalimumab</option>
                        <option>Ustekinumab</option>
                    </select>
                </div>
                <div className="w-64 space-y-2">
                    <Label>Select Indication</Label>
                    <select className="flex h-10 w-full items-center rounded-md border border-input bg-card px-3 py-2 text-sm text-primary-text">
                        <option>Rheumatoid Arthritis</option>
                        <option>Crohn's Disease</option>
                        <option>Psoriatic Arthritis</option>
                    </select>
                </div>
                <div className="flex items-end ml-auto">
                    <Button variant="outline" className="bg-card">
                        <Download className="mr-2 h-4 w-4" /> Export CSV
                    </Button>
                </div>
            </div>

            <div className="ag-theme-alpine-dark flex-1 w-full rounded-md border border-border overflow-hidden custom-ag-grid">
                <AgGridReact
                    rowData={rowData}
                    columnDefs={columnDefs}
                    defaultColDef={defaultColDef}
                    rowHeight={60}
                    suppressMovableColumns={true}
                    domLayout="normal"
                />
            </div>

            <style jsx global>{`
                .custom-ag-grid {
                    --ag-background-color: var(--card);
                    --ag-header-background-color: #0f0f0f;
                    --ag-border-color: var(--border);
                    --ag-row-border-color: var(--border);
                    --ag-odd-row-background-color: var(--background);
                    --ag-font-family: inherit;
                    --ag-font-size: 14px;
                    --ag-header-foreground-color: #f1f5f9;
                    --ag-secondary-foreground-color: #94a3b8;
                    --ag-data-color: #f1f5f9;
                    --ag-pinned-column-shadow: none;
                }
                .custom-ag-grid .ag-header-cell {
                    font-weight: 600;
                    border-bottom: 2px solid var(--border);
                }
                .custom-ag-grid .ag-cell {
                    display: flex;
                    align-items: center;
                }
                /* Hide row focus/hover selection completely for cleaner UI */
                .custom-ag-grid .ag-row-hover,
                .custom-ag-grid .ag-row-focus {
                    background-color: inherit !important;
                }
                .custom-ag-grid .ag-root-wrapper {
                    border: none;
                }
            `}</style>
        </div>
    );
}
