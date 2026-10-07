"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { NoInterview } from "@/components/NoInterview";
import { DifficultyBadge } from "@/components/DifficultyBadge";
import { submitAnswer, type Message } from "@/lib/api";
import { saveSession, type InterviewSession } from "@/lib/session";
import { useStoredSession } from "@/lib/useStoredSession";

const REDIRECT_DELAY_MS = 2500; // time to read the closing message before the report

export default function InterviewPage() {
  const session = useStoredSession();
  if (session === undefined) return null;
  if (!session) return <NoInterview />;
  return <Chat initial={session} />;
}

function Chat({ initial }: { initial: InterviewSession }) {
  const router = useRouter();
  const [history, setHistory] = useState<Message[]>(initial.history);
  const [complete, setComplete] = useState(initial.complete);
  const [answer, setAnswer] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll new messages (and the thinking indicator) into view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, thinking, error]);

  // Go to the report once the interviewer has ended the interview.
  useEffect(() => {
    if (!complete) return;
    const t = setTimeout(() => router.push("/report"), REDIRECT_DELAY_MS);
    return () => clearTimeout(t);
  }, [complete, router]);

  // Return focus to the box after each AI reply.
  useEffect(() => {
    if (!thinking && !complete) inputRef.current?.focus();
  }, [thinking, complete]);

  async function send() {
    const text = answer.trim();
    if (!text || thinking || complete) return;

    const previous = history;
    setHistory([...previous, { role: "candidate", content: text }]); // show my answer immediately
    setAnswer("");
    setError(null);
    setThinking(true);

    try {
      const res = await submitAnswer(initial.topic, initial.difficulty, previous, text);
      setHistory(res.history);
      setComplete(res.interview_complete);
      saveSession({ ...initial, history: res.history, complete: res.interview_complete });
    } catch (err) {
      // Roll back so the answer can be resent.
      setHistory(previous);
      setAnswer(text);
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setThinking(false);
    }
  }

  const inputDisabled = thinking || complete;
  let placeholder = "Type your answer…";
  if (thinking) placeholder = "Interviewer is thinking…";
  if (complete) placeholder = "The interview has ended.";

  return (
    <div className="flex h-dvh flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wider text-zinc-500">Interview</p>
            <h1 className="truncate font-semibold text-zinc-100">{initial.topic}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <DifficultyBadge difficulty={initial.difficulty} />
            <Link href="/" className="text-sm text-zinc-500 transition hover:text-zinc-300">
              Exit
            </Link>
          </div>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6" aria-live="polite">
          {history.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}

          {thinking && <ThinkingBubble />}

          {complete && (
            <p className="mt-2 flex items-center justify-center gap-2 text-sm text-zinc-400">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-300" aria-hidden />
              <span>Interview complete — preparing your report…</span>
            </p>
          )}

          <div ref={bottomRef} />
        </div>
      </main>

      {/* Composer */}
      <footer className="border-t border-zinc-800 bg-zinc-950">
        <form
          className="mx-auto w-full max-w-3xl px-4 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          {error && (
            <div role="alert" className="mb-3 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
              {error}
            </div>
          )}
          <div className="flex items-end gap-3">
            <label htmlFor="answer" className="sr-only">
              Your answer
            </label>
            <textarea
              id="answer"
              ref={inputRef}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends; Shift+Enter inserts a newline; ignore while composing (IME).
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void send();
                }
              }}
              disabled={inputDisabled}
              rows={3}
              maxLength={5000}
              placeholder={placeholder}
              className="max-h-48 min-h-[3rem] flex-1 resize-y rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-zinc-100 placeholder-zinc-500 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={inputDisabled || !answer.trim()}
              className="h-12 shrink-0 rounded-xl bg-indigo-600 px-5 font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              Send
            </button>
          </div>
          <p className="mt-2 text-xs text-zinc-600">
            <kbd className="font-sans">Enter</kbd> to send · <kbd className="font-sans">Shift</kbd>+<kbd className="font-sans">Enter</kbd> for a new line
          </p>
        </form>
      </footer>
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const mine = message.role === "candidate";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] sm:max-w-[75%] ${mine ? "items-end" : "items-start"} flex flex-col`}>
        <span className="mb-1 px-1 text-xs text-zinc-500">{mine ? "You" : "Interviewer"}</span>
        <div
          className={`whitespace-pre-wrap break-words rounded-2xl px-4 py-3 leading-relaxed ${
            mine
              ? "rounded-br-md bg-indigo-600 text-white"
              : "rounded-bl-md border border-zinc-800 bg-zinc-900 text-zinc-100"
          }`}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex flex-col items-start">
        <span className="mb-1 px-1 text-xs text-zinc-500">Interviewer</span>
        <div
          className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-zinc-800 bg-zinc-900 px-4 py-4"
          role="status"
          aria-label="Interviewer is thinking"
        >
          <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.3s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.15s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500" />
        </div>
      </div>
    </div>
  );
}
