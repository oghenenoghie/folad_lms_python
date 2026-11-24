"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { NAV_SECTIONS } from "@/lib/nav";

function isActive(pathname: string, href?: string) {
  if (!href) return false;
  return href === "/dashboard" ? pathname === href : pathname.startsWith(href);
}

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center gap-2 border-b px-5">
        <GraduationCap className="h-6 w-6 text-primary" />
        <span className="font-semibold">School Management</span>
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section, i) => (
          <div key={section.heading ?? i}>
            {section.heading && (
              <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {section.heading}
              </p>
            )}
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(pathname, item.href);
                if (item.enabled && item.href) {
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-accent text-accent-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  );
                }
                return (
                  <div
                    key={item.label}
                    aria-disabled="true"
                    className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground/50"
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                    <Badge variant="secondary" className="ml-auto">
                      Soon
                    </Badge>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </div>
  );
}
