/**
 * A tiny in-tab pub/sub for "the queue may have changed" -- not a data store, just a
 * signal. Every screen that shows a pending count (AppShell's header badge, the Overview
 * page, the Decision Queue page itself) polls independently via useApiResource, so
 * submitting a run on Workflows or deciding one on Decisions previously had no way to
 * tell the OTHER screens' polls to hurry up -- they'd sit on stale counts for up to
 * their own poll interval. This lets the action that changed the queue say so once, and
 * every subscriber (AppShell's badge in particular) refetches immediately instead of
 * waiting for its next tick.
 *
 * Same shape as NotificationBell's lastSeenListeners -- a plain Set of callbacks, no
 * library, because the whole need is "tell whoever's listening, right now."
 */

const listeners = new Set<() => void>();

export function emitQueueChanged(): void {
  for (const listener of listeners) listener();
}

export function subscribeQueueChanged(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}
