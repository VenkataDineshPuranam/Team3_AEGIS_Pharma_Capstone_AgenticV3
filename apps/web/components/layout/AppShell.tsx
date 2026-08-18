"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { getQueue } from "@/lib/api";
import { useApiResource, useVisiblePolling } from "@/hooks/useApiResource";
import { AssistantLauncher } from "@/components/assistant/AssistantLauncher";
import { useAuth } from "./AuthContext";
import { NotificationBell } from "./NotificationBell";
import { OperatorBar } from "./OperatorBar";

/**
 * Application shell: persistent sidebar on desktop, slide-over on mobile.
 *
 * Navigation lists only destinations backed by real API data (Phase 4). There is no
 * "Reports", "Settings", or "Integrations" entry, because nothing behind them exists --
 * an enterprise-looking nav full of dead links is the fastest way to make a working
 * system feel like a mock-up.
 */

interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: ReactNode;
  /** Shows the live pending count. */
  badge?: "queue";
  /** Restricts this destination to a specific role. Omitted = visible to everyone. This
   *  is a UX convenience only, same as RequireAuth's own docstring says about itself --
   *  the API's own 403 (services/api/main.py::_require_super_admin) is what actually
   *  enforces it. */
  role?: string;
}

const NAV: NavItem[] = [
  {
    href: "/",
    label: "Overview",
    description: "System state at a glance",
    icon: <IconGrid />,
  },
  {
    href: "/guide",
    label: "Getting Started",
    description: "New here? Start with this",
    icon: <IconCompass />,
  },
  {
    href: "/decisions",
    label: "Decision Queue",
    description: "Runs awaiting a human decision",
    icon: <IconInbox />,
    badge: "queue",
  },
  {
    href: "/runs",
    label: "Run History",
    description: "Every recorded run",
    icon: <IconHistory />,
  },
  {
    href: "/evidence",
    label: "Evidence",
    description: "The evidence corpus and its authority",
    icon: <IconDocument />,
  },
  {
    href: "/workflows",
    label: "Workflows",
    description: "What each workflow may conclude",
    icon: <IconFlow />,
  },
  {
    href: "/governance",
    label: "Governance",
    description: "Controls, policies and boundaries",
    icon: <IconShield />,
  },
  {
    href: "/health",
    label: "System Health",
    description: "Measured dependency status",
    icon: <IconPulse />,
  },
  {
    href: "/coverage",
    label: "Evaluation & Security",
    description: "What has been verified, and what has not",
    icon: <IconCheckShield />,
    role: "Super Admin",
  },
  {
    href: "/compliance",
    label: "Compliance",
    description: "EU AI Act and ISO 42001 evidence",
    icon: <IconScale />,
    role: "Super Admin",
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { session } = useAuth();
  const nav = NAV.filter((item) => !item.role || item.role === session?.role);
  const [mobileOpen, setMobileOpen] = useState(false);
  // React's "adjust state during render" pattern rather than an effect: closing the
  // drawer on navigation is a pure function of the route changing, computed synchronously
  // instead of one render behind an effect (which would flash the drawer open a frame
  // longer on every navigation).
  const [lastPathname, setLastPathname] = useState(pathname);
  if (pathname !== lastPathname) {
    setLastPathname(pathname);
    if (mobileOpen) setMobileOpen(false);
  }

  // The pending count is the one number worth carrying in the chrome: it is the reason an
  // operator opens this application at all.
  const pollMs = useVisiblePolling(15_000);
  const queue = useApiResource((signal) => getQueue(undefined, signal), [], { pollMs });
  const pendingCount = queue.data?.length ?? null;

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>

      {/* --- mobile header ------------------------------------------------ */}
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-[var(--border-subtle)] bg-[var(--surface-raised)]/95 px-4 py-2.5 backdrop-blur lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen((v) => !v)}
          aria-expanded={mobileOpen}
          aria-controls="app-nav"
          className="rounded-[var(--radius-md)] p-1.5 text-[var(--text-secondary)] hover:bg-[var(--surface-sunken)]"
        >
          <span className="sr-only">{mobileOpen ? "Close navigation" : "Open navigation"}</span>
          <span aria-hidden="true" className="text-lg leading-none">
            {mobileOpen ? "✕" : "☰"}
          </span>
        </button>
        <Wordmark />
        <div className="ml-auto flex items-center gap-2">
          {pendingCount != null && pendingCount > 0 && (
            <Link
              href="/decisions"
              className="tnum rounded-[var(--radius-full)] border border-[var(--status-pending-border)] bg-[var(--status-pending-bg)] px-2 py-0.5 text-xs font-medium text-[var(--status-pending-fg)]"
            >
              {pendingCount} pending
            </Link>
          )}
          <NotificationBell />
        </div>
      </header>

      {/* --- sidebar ------------------------------------------------------ */}
      <nav
        id="app-nav"
        aria-label="Primary"
        className={cn(
          "z-20 shrink-0 border-[var(--border-subtle)] bg-[var(--surface-raised)]",
          "lg:sticky lg:top-0 lg:flex lg:h-dvh lg:w-64 lg:flex-col lg:border-r",
          mobileOpen ? "block border-b" : "hidden lg:flex",
        )}
      >
        <div className="hidden items-center gap-2.5 px-5 py-4 lg:flex">
          <Wordmark />
          <div className="ml-auto">
            <NotificationBell />
          </div>
        </div>

        <ul className="flex-1 space-y-0.5 overflow-y-auto px-2.5 py-2 lg:py-1">
          {nav.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-[var(--radius-md)] px-2.5 py-2 text-[13px] font-medium transition-colors",
                    active
                      ? "bg-[var(--brand-subtle)] text-[var(--brand)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text-primary)]",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "shrink-0",
                      active ? "text-[var(--brand)]" : "text-[var(--text-tertiary)]",
                    )}
                  >
                    {item.icon}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  {item.badge === "queue" && pendingCount != null && pendingCount > 0 && (
                    <span className="tnum shrink-0 rounded-[var(--radius-full)] bg-[var(--status-pending-bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--status-pending-fg)]">
                      {pendingCount}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="border-t border-[var(--border-subtle)] p-3">
          <OperatorBar />
        </div>
      </nav>

      {/* --- main --------------------------------------------------------- */}
      <main id="main" className="min-w-0 flex-1">
        {children}
      </main>

      {/* Mounted in the shell rather than per-page, so the assistant is reachable from
          every authenticated screen. It sits inside RequireAuth's tree, so it is never
          rendered on /login -- there is no session to answer questions under. */}
      <AssistantLauncher />
    </div>
  );
}

function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2.5 rounded-[var(--radius-sm)]">
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-[var(--radius-md)] bg-[var(--brand)] text-[13px] font-bold text-white"
      >
        Æ
      </span>
      <span className="min-w-0">
        <span className="block text-[13px] font-semibold leading-tight tracking-tight text-[var(--text-primary)]">
          AEGIS
        </span>
        <span className="block text-[10px] uppercase leading-tight tracking-[0.14em] text-[var(--text-tertiary)]">
          Control Center
        </span>
      </span>
    </Link>
  );
}

/**
 * Page header. Every page uses this so the h1, the description, and the action slot land
 * in the same place -- consistency an operator can rely on when moving between screens.
 */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumb?: ReactNode;
}) {
  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--surface-raised)]">
      <div className="mx-auto max-w-[100rem] px-4 py-5 sm:px-6 lg:px-8">
        {breadcrumb && <div className="mb-2">{breadcrumb}</div>}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-[var(--text-primary)]">
              {title}
            </h1>
            {description && (
              <div className="mt-1 max-w-3xl text-[13px] leading-relaxed text-[var(--text-secondary)]">
                {description}
              </div>
            )}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}

export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto max-w-[100rem] px-4 py-6 sm:px-6 lg:px-8", className)}>
      {children}
    </div>
  );
}

/* --- icons: inline, 16px, currentColor. No icon library for seven glyphs. --- */

function iconProps() {
  return {
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
}

function IconGrid() {
  return (
    <svg {...iconProps()}>
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  );
}

function IconInbox() {
  return (
    <svg {...iconProps()}>
      <path d="M2 9.5V4a1.5 1.5 0 0 1 1.5-1.5h9A1.5 1.5 0 0 1 14 4v5.5" />
      <path d="M2 9.5h3l1 2h4l1-2h3V12a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12V9.5Z" />
    </svg>
  );
}

function IconHistory() {
  return (
    <svg {...iconProps()}>
      <path d="M2.5 8a5.5 5.5 0 1 0 1.7-4" />
      <path d="M2 2v3h3" />
      <path d="M8 5v3l2 1.5" />
    </svg>
  );
}

function IconDocument() {
  return (
    <svg {...iconProps()}>
      <path d="M9 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5.5L9 1.5Z" />
      <path d="M9 1.5v4h4" />
    </svg>
  );
}

function IconFlow() {
  return (
    <svg {...iconProps()}>
      <rect x="1.5" y="2" width="4.5" height="3.5" rx="1" />
      <rect x="10" y="2" width="4.5" height="3.5" rx="1" />
      <rect x="5.75" y="10.5" width="4.5" height="3.5" rx="1" />
      <path d="M3.75 5.5v2.25h8.5V5.5M8 7.75v2.75" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg {...iconProps()}>
      <path d="M8 1.5 13 3.5v4c0 3.2-2.1 6-5 7-2.9-1-5-3.8-5-7v-4L8 1.5Z" />
      <path d="M6 7.75 7.5 9.25 10.25 6.5" />
    </svg>
  );
}

function IconCheckShield() {
  return (
    <svg {...iconProps()}>
      <rect x="1.5" y="2.5" width="6" height="6" rx="1" />
      <path d="M3 5.5 4 6.5 6 4.5" />
      <path d="M10.5 2 14 3.5v3.5c0 2.6-1.7 4.8-3.5 5.5-1.8-.7-3.5-2.9-3.5-5.5" />
    </svg>
  );
}

function IconPulse() {
  return (
    <svg {...iconProps()}>
      <path d="M1.5 8h3l1.5-4 2.5 8 1.5-4h3.5" />
    </svg>
  );
}

function IconCompass() {
  return (
    <svg {...iconProps()}>
      <circle cx="8" cy="8" r="6.5" />
      <path d="M10.2 5.8 8.9 8.9 5.8 10.2 7.1 7.1z" />
    </svg>
  );
}

function IconScale() {
  return (
    <svg {...iconProps()}>
      <path d="M8 2v11.5M5 13.5h6" />
      <path d="M2 5.5h4.5M9.5 5.5H14" />
      <path d="M2 5.5 0.5 9a1.5 1.5 0 0 0 3 0Z" />
      <path d="M14 5.5 12.5 9a1.5 1.5 0 0 0 3 0Z" />
    </svg>
  );
}
