import type { LucideIcon } from "lucide-react";
import {
  Briefcase,
  Building2,
  GraduationCap,
  HeartHandshake,
  LayoutDashboard,
  Shield,
} from "lucide-react";

export type NavItem = {
  label: string;
  icon: LucideIcon;
  href?: string;
  enabled: boolean;
};

export type NavSection = {
  heading?: string;
  items: NavItem[];
};

// Mirrors apps/web/context_processors.py::nav_items — same IA across both
// frontends until the Django UI is retired. Only modules with a real page
// are enabled; the rest preview the intended structure as "Soon".
export const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard", enabled: true },
    ],
  },
  {
    heading: "School",
    items: [
      { label: "Students", icon: GraduationCap, enabled: false },
      { label: "Staff & teachers", icon: Briefcase, href: "/staff", enabled: true },
      { label: "Parents & guardians", icon: HeartHandshake, enabled: false },
      { label: "Schools & academics", icon: Building2, href: "/schools", enabled: true },
    ],
  },
  {
    heading: "Administration",
    items: [{ label: "Users & roles", icon: Shield, enabled: false }],
  },
];
