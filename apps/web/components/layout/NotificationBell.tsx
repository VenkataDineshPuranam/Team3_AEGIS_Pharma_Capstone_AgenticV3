"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Badge } from "@/components/ui/Badge";
import { useApiResource, useVisiblePolling } from "@/hooks/useApiResource";
import { getNotifications, type NotificationItem, type Workflow } from "@/lib/api";
import { cn } from "@/lib/cn";
import { WORKFLOW_LABELS, formatDateTime } from "@/lib/format";

/**
 * Notification bell -- Stage 23. The visible half of the live HITL escalation notifier
 * (services/integration/hitl_escalation_watch.py); the other half is a best-effort email
 * to NOTIFY_EMAIL_TO. Both fire from the same backend event, the moment a pending run
 * first crosses severity 3 (T2) or 4 (T3) -- see that module's docstring for the full
 * scope statement, restated briefly here because it matters just as much in the UI: this
 * bell can only ever tell you a run has been waiting a long time. It cannot approve,
 * reject, or widen who may decide anything. Clicking a row takes you to the run; nothing
 * here acts on your behalf.
 *
 * "UNREAD" IS A BROWSER-LOCAL CONCEPT, STATED PLAINLY
 * -----------------------------------------------------
 * There is no per-user "read" state on the server -- this app has ten shared demo
 * accounts and no user-scoped notification-read table, and building one would be a much
 * bigger feature than "tell me when a run is overdue." So the unread count is "escalation
 * events newer than the last time THIS BROWSER opened the bell," kept in localStorage.
 * Open the app in a second browser and it has its own independent unread count. That is
 * an accepted, stated simplification -- the same posture pending_queue.py's own docstring
 * takes toward its single-process, non-durable state -- not a bug to file.
 */

const LAST_SEEN_KEY = "aegis.notifications.lastSeenAt";
const POLL_MS = 20_000;

// Same tiny external-store shape lib/auth/session.ts already uses for the same reason:
// localStorage does not exist during server rendering, so reading it in an effect (the
// naive approach) either trips "avoid setState in an effect" or risks a hydration
// mismatch on the very first client render. useSyncExternalStore is the React-sanctioned
// way to read a synchronous external source safely across both.
const lastSeenListeners = new Set<() => void>();

function readLastSeen(): string | null {
  try {
    return localStorage.getItem(LAST_SEEN_KEY);
  } catch {
    return null; // private browsing / quota -- every open just reads as "all unread"
  }
}

function writeLastSeen(iso: string): void {
  try {
    localStorage.setItem(LAST_SEEN_KEY, iso);
  } catch {
    // Nothing to persist to; the bell still works within this render's lifetime.
  }
  for (const listener of lastSeenListeners) listener();
}

function subscribeLastSeen(onStoreChange: () => void) {
  lastSeenListeners.add(onStoreChange);
  return () => lastSeenListeners.delete(onStoreChange);
}

function getLastSeenServerSnapshot(): string | null {
  return null;
}

export function NotificationBell({ align = "right" }: { align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const lastSeen = useSyncExternalStore(subscribeLastSeen, readLastSeen, getLastSeenServerSnapshot);
  const containerRef = useRef<HTMLDivElement>(null);

  const pollMs = useVisiblePolling(POLL_MS);
  const resource = useApiResource((signal) => getNotifications(20, signal), [], { pollMs });
  const items = resource.data ?? [];
  const unreadCount = lastSeen ? items.filter((n) => n.evaluated_at > lastSeen).length : items.length;

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle() {
    setOpen((wasOpen) => {
      const nowOpen = !wasOpen;
      if (nowOpen) writeLastSeen(new Date().toISOString());
      return nowOpen;
    });
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
        className="relative flex size-8 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text-primary)]"
      >
        <IconBell />
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            className="tnum absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-[var(--radius-full)] bg-[var(--status-blocked-fg)] px-1 text-[10px] font-semibold text-white"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Escalation notifications"
          className={cn(
            "absolute z-30 mt-2 w-80 rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-raised)] shadow-[var(--shadow-md)]",
            align === "left" ? "left-0" : "right-0",
          )}
        >
          <div className="border-b border-[var(--border-subtle)] px-3.5 py-2.5">
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Escalations</p>
            <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
              Runs that have been waiting long enough to need attention. Visibility only —
              nothing here decides anything.
            </p>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-3.5 py-4 text-[13px] text-[var(--text-tertiary)]">
                Nothing has escalated recently.
              </p>
            ) : (
              <ul>
                {items.map((item) => (
                  <NotificationRow key={`${item.run_id}-${item.tier}`} item={item} />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function NotificationRow({ item }: { item: NotificationItem }) {
  const tone = item.severity >= 4 ? "blocked" : "pending";
  const label = item.severity >= 4 ? "Expired" : "Escalation due";
  const workflow = item.workflow as Workflow;

  return (
    <li className="border-b border-[var(--border-subtle)] last:border-b-0">
      <Link
        href={`/decisions/${encodeURIComponent(item.run_id)}`}
        className="block px-3.5 py-2.5 hover:bg-[var(--surface-sunken)]"
      >
        <div className="flex items-center gap-2">
          <Badge tone={tone} size="xs">
            {label}
          </Badge>
          <span className="truncate text-[12px] font-medium text-[var(--text-primary)]">
            {WORKFLOW_LABELS[workflow] ?? item.workflow}
          </span>
        </div>
        <p className="mt-1 truncate font-mono text-[12px] text-[var(--text-secondary)]">
          {item.subject_id ?? item.run_id}
        </p>
        <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">
          {item.approver_roles && item.approver_roles.length > 0
            ? `Waiting on ${item.approver_roles.join(", ")}`
            : "Approver not on file"}
          {" · "}
          {formatDateTime(item.evaluated_at)}
        </p>
      </Link>
    </li>
  );
}

function IconBell() {
  return (
    <svg
      width={17}
      height={17}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 6.5a4 4 0 0 1 8 0c0 3 1 4 1 4H3s1-1 1-4Z" />
      <path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" />
    </svg>
  );
}
