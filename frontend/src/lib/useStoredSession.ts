"use client";

import { useMemo, useSyncExternalStore } from "react";
import { loadSessionRaw, parseSession, type InterviewSession } from "./session";

const noop = () => () => {};

/**
 * Reads the interview from sessionStorage on the client.
 * Returns `undefined` during server render / first paint, `null` if there's no interview.
 */
export function useStoredSession(): InterviewSession | null | undefined {
  const raw = useSyncExternalStore(noop, loadSessionRaw, () => undefined);
  return useMemo(() => (raw === undefined ? undefined : parseSession(raw)), [raw]);
}
