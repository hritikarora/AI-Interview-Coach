"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { startInterview, type Difficulty } from "@/lib/api";
import { saveSession } from "@/lib/session";

const DIFFICULTIES: { value: Difficulty; label: string; hint: string }[] = [
  { value: "easy", label: "Easy", hint: "Definitions & recall" },
  { value: "medium", label: "Medium", hint: "Applied problems" },
  { value: "hard", label: "Hard", hint: "Trade-offs & systems" },
];

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    if (loading) return;

    const t = topic.trim();
    const missing = [!t && "a topic", !difficulty && "a difficulty"].filter(Boolean);
    if (missing.length) {
      setError(`Please enter ${missing.join(" and ")}.`);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const res = await startInterview(t, difficulty!);
      saveSession({ topic: t, difficulty: difficulty!, history: res.history, complete: res.interview_complete });
      router.push("/interview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <div className="w-full max-w-lg">
        <header className="mb-10 text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-white">AI Interview Coach</h1>
          <p className="mt-3 text-zinc-400">
            Practice a technical interview, one question at a time — then get a scored report.
          </p>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void start();
          }}
          noValidate
          className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl shadow-black/40"
        >
          <label htmlFor="topic" className="block text-sm font-medium text-zinc-300">
            Topic
          </label>
          <input
            id="topic"
            type="text"
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value);
              if (error) setError(null);
            }}
            placeholder="e.g. React hooks, SQL indexing, Kubernetes"
            maxLength={200}
            disabled={loading}
            className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-4 py-3 text-zinc-100 placeholder-zinc-500 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-60"
          />

          <fieldset className="mt-6" disabled={loading}>
            <legend className="text-sm font-medium text-zinc-300">Difficulty</legend>
            <div className="mt-2 grid grid-cols-3 gap-3">
              {DIFFICULTIES.map((d) => {
                const selected = difficulty === d.value;
                return (
                  <button
                    key={d.value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => {
                      setDifficulty(d.value);
                      if (error) setError(null);
                    }}
                    className={`rounded-lg border px-3 py-3 text-left transition disabled:opacity-60 ${
                      selected
                        ? "border-indigo-500 bg-indigo-500/10 ring-2 ring-indigo-500/30"
                        : "border-zinc-700 bg-zinc-950 hover:border-zinc-500"
                    }`}
                  >
                    <span className={`block font-medium ${selected ? "text-indigo-300" : "text-zinc-100"}`}>
                      {d.label}
                    </span>
                    <span className="mt-0.5 block text-xs text-zinc-500">{d.hint}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {error && (
            <div
              role="alert"
              className="mt-6 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-indigo-600/60"
          >
            {loading && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden />
            )}
            {loading ? "Preparing your interview…" : "Start Interview"}
          </button>
        </form>
      </div>
    </main>
  );
}
