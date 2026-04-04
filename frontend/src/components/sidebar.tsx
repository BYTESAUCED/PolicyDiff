"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard, UploadCloud, Search, TableProperties, Activity, MessageSquare, AlertTriangle, FileCheck, PanelLeftClose, PanelRightClose, ChevronLeft, ChevronRight
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ModeToggle } from "./mode-toggle";

const routes = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard },
    { label: "Policy Upload", href: "/upload", icon: UploadCloud },
    { label: "Drug Explorer", href: "/explorer", icon: Search },
    { label: "Comparison Matrix", href: "/compare", icon: TableProperties },
    { label: "Change Feed", href: "/diffs", icon: Activity },
    { label: "Query Interface", href: "/query", icon: MessageSquare },
    { label: "Discordance Alerts", href: "/discordance", icon: AlertTriangle },
    { label: "Approval Path", href: "/approval-path", icon: FileCheck },
];

export function AppSidebar() {
    const pathname = usePathname();
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <aside
            className={cn(
                "h-full bg-sidebar flex-shrink-0 text-sidebar-foreground border-r border-border transition-all duration-300 ease-in-out flex flex-col z-20",
                isCollapsed ? "w-[72px]" : "w-64"
            )}
        >
            <div className={cn("h-14 flex items-center border-b border-border shrink-0 transition-all duration-300 overflow-hidden", isCollapsed ? "justify-center px-1" : "justify-between px-4")}>
                <Link href="/" className="flex items-center gap-2 overflow-hidden">
                    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shrink-0", isCollapsed && "ml-1")}>
                        <span className="font-bold text-sm">PD</span>
                    </div>
                    {!isCollapsed && <span className="font-bold text-lg tracking-tight truncate transition-opacity duration-300 whitespace-nowrap">PolicyDiff</span>}
                </Link>
                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className={cn("flex items-center justify-center rounded-md text-muted-text hover:text-white transition-colors hover:bg-white/5 cursor-pointer shrink-0 p-1.5", isCollapsed ? "ml-0" : "ml-2")}
                    title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                >
                    {isCollapsed ? <PanelRightClose className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto py-6 px-3 custom-scrollbar flex flex-col gap-2">
                {routes.map((route) => {
                    const isActive = pathname === route.href;
                    return (
                        <Link
                            key={route.href}
                            href={route.href}
                            title={isCollapsed ? route.label : undefined}
                            className={cn(
                                "flex items-center rounded-md transition-colors px-3 h-10 shrink-0 group relative cursor-pointer",
                                isActive
                                    ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-foreground"
                                    : "text-muted-text hover:bg-sidebar-accent hover:text-sidebar-foreground",
                                isCollapsed ? "justify-center px-0 w-10 mx-auto" : "w-full"
                            )}
                        >
                            <route.icon className={cn("h-5 w-5 shrink-0 transition-transform group-hover:scale-[1.03]", isActive ? "text-primary dark:text-primary-foreground" : "text-muted-text opacity-70 group-hover:opacity-100")} />
                            {!isCollapsed && (
                                <span className="ml-3 text-sm font-medium truncate">{route.label}</span>
                            )}
                        </Link>
                    );
                })}
            </div>

            <div className="p-3 mt-auto flex flex-col gap-2 shrink-0 border-t border-border">
                <ModeToggle isCollapsed={isCollapsed} />
            </div>
        </aside>
    );
}
