/**
 * The single HTTP boundary between this app and the Orchestrator API.
 *
 * THE RULE THIS FILE EXISTS TO ENFORCE (Phase 24):
 *
 *   Reads may be retried. Human decisions may NEVER be retried automatically.
 *
 * An approval, rejection, or veto writes an irreversible record to an append-only audit
 * store. A retry after an ambiguous failure -- a timeout, a dropped connection, a 502 --
 * risks recording a second human action that no human took. So `mutate()` has no retry
 * path at all, and cannot acquire one by configuration: the retry logic lives in `read()`
 * and is not reachable from `mutate()`.
 *
 * This is a client-side convenience, not a control. The backend remains authoritative for
 * every governance decision; nothing here decides whether an action is permitted.
 */

import { clearSessionOnUnauthorized, currentToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeader(): Record<string, string> {
  const token = currentToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Reads that are safe to retry, and how many times. Idempotent GETs only. */
const READ_RETRIES = 2;
const RETRY_BACKOFF_MS = 400;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** The API's own explanation, when it gave one. */
    readonly detail?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /**
   * A message safe to put in front of a user.
   *
   * FastAPI's 422 bodies contain a nested validation structure, and 500s can carry
   * internals. Neither belongs on screen (Phase 26: safe errors, no stack traces), so
   * anything unrecognized collapses to a generic sentence and the raw body is dropped.
   */
  get userMessage(): string {
    if (this.status === 0) {
      return "Could not reach the Orchestrator API.";
    }
    if (this.status === 404) return this.detail || "That record no longer exists.";
    if (this.status === 409) return this.detail || "This run has already moved on.";
    if (this.status === 422) return "The request was rejected as invalid.";
    if (this.status === 503) return this.detail || "A required service is unavailable.";
    if (this.status >= 500) return "The Orchestrator API reported an internal error.";
    return this.detail || `Request failed (${this.status}).`;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail: string | undefined;
  try {
    const body = await res.json();
    // Only a plain-string `detail` is ever surfaced. FastAPI's 422 detail is an array of
    // validation objects -- structured internals, deliberately not shown.
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // Non-JSON body: nothing safe to extract.
  }
  return new ApiError(`HTTP ${res.status}`, res.status, detail);
}

/**
 * GET. Retries transient failures (network error, 502/503/504) with a short backoff.
 * Never retries a 4xx -- those are answers, not failures.
 */
export async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt <= READ_RETRIES; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        signal,
        headers: { Accept: "application/json", ...authHeader() },
        cache: "no-store",
      });
      if (res.ok) return (await res.json()) as T;
      if (res.status === 401) clearSessionOnUnauthorized();

      const error = await parseError(res);
      // A 4xx is a definitive answer. Retrying it just delays showing the user the truth.
      if (res.status < 500) throw error;
      lastError = error;
    } catch (e) {
      // An aborted request is the caller cancelling (unmount, superseded filter), not a
      // failure to report. Rethrow so the caller can ignore it.
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      if (e instanceof ApiError && e.status < 500) throw e;
      lastError = e instanceof ApiError ? e : new ApiError(String(e), 0);
    }

    if (attempt < READ_RETRIES) {
      await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS * (attempt + 1)));
    }
  }

  throw lastError ?? new ApiError("Request failed", 0);
}

/**
 * POST. Sent exactly once.
 *
 * There is no retry loop here and there must never be one. If this call fails, the caller
 * surfaces the failure and the human decides whether to act again -- because only they
 * can know whether their decision was recorded.
 */
export async function mutate<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json", ...authHeader() },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    // The request may or may not have reached the server. Say so precisely rather than
    // implying nothing happened.
    throw new ApiError(
      "The request could not be completed. It may or may not have been recorded -- " +
        "reload the queue to check before acting again.",
      0,
    );
  }

  if (!res.ok) {
    // A 401 here means the session lapsed between opening the form and submitting it --
    // NOT that the human action itself was ambiguous. Safe to clear locally; the mutate
    // itself was never sent by the server as recorded (FastAPI's dependency rejects the
    // request before the endpoint body runs), so there is no "did this record?" question.
    if (res.status === 401) clearSessionOnUnauthorized();
    throw await parseError(res);
  }
  return (await res.json()) as T;
}

/**
 * GET a file download (CSV export, etc). Not `read()`: the response body is a file, not
 * JSON, and a failed export should never retry -- same one-shot reasoning as `mutate()`,
 * just for a GET that produces a side-effect-free but potentially large file.
 */
export async function download(path: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { headers: authHeader(), cache: "no-store" });
  } catch {
    throw new ApiError("Could not reach the Orchestrator API.", 0);
  }
  if (!res.ok) {
    if (res.status === 401) clearSessionOnUnauthorized();
    throw await parseError(res);
  }
  return res.blob();
}

/** POST that must succeed WITHOUT an existing session -- login itself. */
export async function mutatePublic<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach the Orchestrator API.", 0);
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}
