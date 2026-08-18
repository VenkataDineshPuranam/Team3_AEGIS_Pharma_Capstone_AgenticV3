"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { useAuth } from "@/components/layout/AuthContext";
import { ApiError, getDemoAccounts, type DemoAccount } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { session, signIn } = useAuth();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);
  const userIdInputId = useId();
  const passwordInputId = useId();
  const accountSelectId = useId();

  const next = params.get("next") || "/";

  useEffect(() => {
    if (session) router.replace(next);
  }, [session, next, router]);

  useEffect(() => {
    let cancelled = false;
    getDemoAccounts()
      .then((list) => {
        if (!cancelled) setAccounts(list);
      })
      .catch(() => {
        // The account picker is a convenience, not a requirement -- if it can't load,
        // the User ID field below still works exactly as it always has.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(userId.trim(), password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[var(--surface-sunken)] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <span
            aria-hidden="true"
            className="grid size-9 shrink-0 place-items-center rounded-[var(--radius-md)] bg-[var(--brand)] text-[16px] font-bold text-white"
          >
            Æ
          </span>
          <span>
            <span className="block text-[15px] font-semibold leading-tight tracking-tight text-[var(--text-primary)]">
              AEGIS
            </span>
            <span className="block text-[10px] uppercase leading-tight tracking-[0.14em] text-[var(--text-tertiary)]">
              Control Center
            </span>
          </span>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--surface-raised)] p-6 shadow-[var(--shadow-md)]">
          <h1 className="text-[15px] font-semibold text-[var(--text-primary)]">Sign in</h1>
          <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-secondary)]">
            Your role determines which workflows you can view and which decisions you are
            eligible to approve — enforced by the Orchestrator API on every request, not just
            shown in this UI.
          </p>

          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            {accounts.length > 0 && (
              <div>
                <label
                  htmlFor={accountSelectId}
                  className="block text-[13px] font-medium text-[var(--text-primary)]"
                >
                  Who are you signing in as?
                </label>
                <select
                  id={accountSelectId}
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="mt-1.5 w-full rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text-primary)] hover:border-[var(--border-strong)]"
                >
                  <option value="">Choose an account, or type a User ID below</option>
                  {accounts.map((a) => (
                    <option key={a.user_id} value={a.user_id}>
                      {a.display_name} — {a.role}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                  Multiple people can be signed in at once, each with their own session —
                  picking a name here only fills in the User ID field; you still need that
                  person&apos;s password from docs/governance/demo_login_credentials.md.
                </p>
              </div>
            )}

            <div>
              <label
                htmlFor={userIdInputId}
                className="block text-[13px] font-medium text-[var(--text-primary)]"
              >
                User ID
              </label>
              <input
                id={userIdInputId}
                type="text"
                autoComplete="username"
                required
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="e.g. james.whitfield"
                className="mt-1.5 w-full rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] hover:border-[var(--border-strong)]"
              />
            </div>

            <div>
              <label
                htmlFor={passwordInputId}
                className="block text-[13px] font-medium text-[var(--text-primary)]"
              >
                Password
              </label>
              <input
                id={passwordInputId}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[var(--text-primary)]"
              />
            </div>

            {error && (
              <ErrorState
                message={
                  error.status === 401
                    ? "Invalid user ID or password."
                    : error.userMessage
                }
              />
            )}

            <Button type="submit" variant="primary" size="md" className="w-full" loading={busy} loadingLabel="Signing in…">
              Sign in
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-[11px] leading-relaxed text-[var(--text-tertiary)]">
          Synthetic demo accounts only — see docs/governance/demo_login_credentials.md.
          No real credentials, no real people.
        </p>
      </div>
    </div>
  );
}
