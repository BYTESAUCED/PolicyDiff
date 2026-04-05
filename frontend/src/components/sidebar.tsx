"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard, UploadCloud, Search, TableProperties, Activity, MessageSquare, FileCheck, PanelLeftClose, PanelRightClose, LogIn, LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const routes = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard, iconClassName: "text-[#0ea5e9]" },
    { label: "Policy Upload", href: "/upload", icon: UploadCloud, iconClassName: "text-[#8b5cf6]" },
    { label: "Drug Explorer", href: "/explorer", icon: Search, iconClassName: "text-[#e11d74]" },
    { label: "Comparison Matrix", href: "/compare", icon: TableProperties, iconClassName: "text-[#ea580c]" },
    { label: "Change Feed", href: "/diffs", icon: Activity, iconClassName: "text-[#10b981]" },
    { label: "Query Interface", href: "/query", icon: MessageSquare, iconClassName: "text-[#2563eb]" },
    { label: "Approval Path", href: "/approval-path", icon: FileCheck, iconClassName: "text-[#16a34a]" },
];

export function AppSidebar() {
    const pathname = usePathname();
    const [isCollapsed, setIsCollapsed] = useState(false);
    const { user, isAuthenticated, isLoading, login, logout } = useAuth();

    return (
        <aside
            className={cn(
                "h-full flex-shrink-0 border-r border-border bg-background text-foreground transition-all duration-300 ease-in-out flex flex-col z-20",
                isCollapsed ? "w-[72px]" : "w-64"
            )}
        >
            <div className={cn("h-14 flex items-center border-b border-border shrink-0 transition-all duration-300 overflow-hidden", isCollapsed ? "justify-center px-1" : "justify-between px-4")}>
                <Link href="/" className="flex items-center gap-2 overflow-hidden">
                    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-[#c66d5b] shrink-0", isCollapsed && "ml-1")}>
                        <span className="font-bold text-sm">PD</span>
                    </div>
                    {!isCollapsed && <span className="font-bold text-lg tracking-tight truncate whitespace-nowrap transition-opacity duration-300">PolicyDiff</span>}
                </Link>
                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className={cn("flex items-center justify-center rounded-md p-1.5 text-muted-text transition-colors hover:bg-muted hover:text-foreground cursor-pointer shrink-0", isCollapsed ? "ml-0" : "ml-2")}
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
                                    ? "bg-[#f6ebe7] text-[#c66d5b] dark:bg-[#3a2326] dark:text-[#f2c4c8]"
                                    : "text-muted-text hover:bg-muted hover:text-foreground",
                                isCollapsed ? "justify-center px-0 w-10 mx-auto" : "w-full"
                            )}
                        >
                            <route.icon
                                className={cn(
                                    "h-5 w-5 shrink-0 transition-transform group-hover:scale-[1.03]",
                                    route.iconClassName
                                )}
                            />
                            {!isCollapsed && (
                                <span className="ml-3 text-sm font-medium truncate">{route.label}</span>
                            )}
                        </Link>
                    );
                })}
            </div>

            {!isLoading && (
                <div className={cn("mt-auto flex shrink-0 flex-col gap-2 border-t border-border p-3", isCollapsed ? "items-center" : "")}>
                    {isAuthenticated ? (
                        <div className={cn("flex items-center gap-2 w-full", isCollapsed ? "flex-col" : "")}>
                            {!isCollapsed && (
                                <span className="text-xs text-muted-text truncate flex-1" title={user?.email ?? ""}>
                                    {user?.email}
                                </span>
                            )}
                            <button
                                onClick={logout}
                                title="Log out"
                                className={cn(
                                    "flex items-center justify-center rounded-md p-1.5 text-muted-text transition-colors hover:bg-muted hover:text-foreground cursor-pointer shrink-0",
                                    isCollapsed ? "w-10" : ""
                                )}
                            >
                                <LogOut className="h-4 w-4" />
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={login}
                            title="Log in"
                            className={cn(
                                "flex items-center rounded-md px-3 h-9 text-sm font-medium text-muted-text transition-colors hover:bg-muted hover:text-foreground cursor-pointer w-full",
                                isCollapsed ? "justify-center px-0 w-10 mx-auto" : ""
                            )}
                        >
                            <LogIn className="h-4 w-4 shrink-0" />
                            {!isCollapsed && <span className="ml-2">Log in</span>}
                        </button>
                    )}
                </div>
            )}
        </aside>
    );
}
