"use client";

import type { ReactNode } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/ui/States";
import { useAuth } from "./AuthContext";

/**
 * Page-level role gate -- a friendlier version of the raw 403 the API returns
 * (services/api/main.py's `_require_super_admin`), for a page a restricted user reached
 * by URL rather than the nav (the nav already hides these destinations, see AppShell's
 * `role` field on NavItem). This is UX only, same caveat RequireAuth's own docstring
 * states about itself -- the API remains the actual enforcement point.
 */
export function RequireRole({ role, children }: { role: string; children: ReactNode }) {
  const { session } = useAuth();
  if (session?.role !== role) {
    return (
      <>
        <PageHeader title="Restricted" />
        <PageBody>
          <ErrorState
            message={`This page is only available to the ${role} role.`}
            hint={`You're signed in as ${session?.display_name ?? "someone else"} (${session?.role ?? "unknown role"}).`}
          />
        </PageBody>
      </>
    );
  }
  return <>{children}</>;
}
