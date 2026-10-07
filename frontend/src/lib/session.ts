import type { Difficulty, Message, Report } from "./api";

// The backend is stateless, so the browser keeps the interview in sessionStorage.
export type InterviewSession = {
  topic: string;
  difficulty: Difficulty;
  history: Message[];
  complete: boolean;
  report?: Report; // cached so a refresh doesn't regenerate it
};

const KEY = "interview-session";

export function saveSession(s: InterviewSession) {
  sessionStorage.setItem(KEY, JSON.stringify(s));
}

export function loadSessionRaw(): string | null {
  return sessionStorage.getItem(KEY);
}

export function parseSession(raw: string | null): InterviewSession | null {
  try {
    return raw ? (JSON.parse(raw) as InterviewSession) : null;
  } catch {
    return null;
  }
}

export function loadSession(): InterviewSession | null {
  return parseSession(loadSessionRaw());
}

export function clearSession() {
  sessionStorage.removeItem(KEY);
}
