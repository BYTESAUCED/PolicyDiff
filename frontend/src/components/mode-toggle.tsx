"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

export function ModeToggle({ isCollapsed }: { isCollapsed?: boolean }) {
  const { theme, setTheme } = useTheme();

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className={cn(
        "flex items-center rounded-md transition-colors px-3 h-10 group relative cursor-pointer",
        "text-muted-text hover:bg-muted hover:text-foreground",
        isCollapsed ? "justify-center px-0 w-10 mx-auto" : "w-full"
      )}
      title="Toggle theme"
    >
      <div className="relative h-5 w-5 shrink-0 flex items-center justify-center">
        <Sun className="absolute h-[1.2rem] w-[1.2rem] transition-all scale-100 rotate-0 dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-[1.2rem] w-[1.2rem] transition-all scale-0 rotate-90 dark:rotate-0 dark:scale-100" />
      </div>
      {!isCollapsed && <span className="ml-3 text-sm font-medium truncate">Theme Settings</span>}
    </button>
  );
}
