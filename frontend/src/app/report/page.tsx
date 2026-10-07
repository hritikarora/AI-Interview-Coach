"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { DifficultyBadge } from "@/components/DifficultyBadge";
import { NoInterview } from "@/components/NoInterview";
import { generateReport, type Report } from "@/lib/api";
import { clearSession, saveSession, type InterviewSession } from "@/lib/session";
import { useStoredSession } from "@/lib/useStoredSession";

export default function ReportPage() {
  const session = useStoredSession();
  if (session === undefined) return null;
  if (!session) return <NoInterview />;
  return <ReportView session={session} />;
}

// Score colours: good (70+), okay (55–69), weak (<55).
function tone(score: number) {
  if (score >= 70) return { text: "text-emerald-400", ring: "stroke-emerald-500", label: "Good" };
  if (score >= 55) return { text: "text-amber-400", ring: "stroke-amber-500", label: "Okay" };
  return { text: "text-rose-400", ring: "stroke-rose-500", label: "Weak" };
}

function ReportView({ session }: Readonly<{ session: InterviewSession }>) {
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(session.report ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!session.report);
  const started = useRef(false);

  const load = useCallback(async () => {
    try {
      const r = await generateReport(session.topic, session.difficulty, session.history);
      saveSession({ ...session, report: r });
      setReport(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [session]);

  // Generate once on arrival (guard against React dev double-run).
  useEffect(() => {
    if (session.report || started.current) return;
    started.current = true;
    void load();
  }, [session.report, load]);

  function retry() {
    setError(null);
    setLoading(true);
    void load();
  }

  function startNew() {
    clearSession();
    router.push("/");
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12">
      <header className="text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-indigo-400">Interview Complete</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">{session.topic}</h1>
        <div className="mt-3 flex justify-center">
          <DifficultyBadge difficulty={session.difficulty} />
        </div>
      </header>

      {loading && <Loading />}

      {!loading && error && (
        <div role="alert" className="mt-10 rounded-2xl border border-red-900/60 bg-red-950/30 p-6 text-center">
          <p className="font-medium text-red-300">We couldn&apos;t generate your report.</p>
          <p className="mt-1 text-sm text-red-300/80">{error}</p>
          <button
            onClick={retry}
            className="mt-4 rounded-lg bg-red-600 px-5 py-2.5 font-medium text-white transition hover:bg-red-500"
          >
            Try again
          </button>
        </div>
      )}

      {!loading && report && <ReportBody report={report} />}

      <div className="mt-10 flex justify-center">
        <button
          onClick={startNew}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Start New Interview
        </button>
      </div>
    </main>
  );
}

function Loading() {
  return (
    <div className="mt-16 flex flex-col items-center gap-4 text-zinc-400" aria-live="polite">
      <span className="h-10 w-10 animate-spin rounded-full border-4 border-zinc-800 border-t-indigo-500" aria-hidden />
      <p>Evaluating your answers and generating your report…</p>
    </div>
  );
}

function ReportBody({ report }: Readonly<{ report: Report }>) {
  const t = tone(report.score);
  const passed = report.result === "Pass";
  const r = 52;
  const circumference = 2 * Math.PI * r;

  return (
    <>
      {/* Score + result */}
      <section className="mt-10 flex flex-col items-center gap-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 sm:flex-row sm:justify-center sm:gap-12">
        <div className="relative h-36 w-36">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" aria-hidden>
            <circle cx="60" cy="60" r={r} className="fill-none stroke-zinc-800" strokeWidth="10" />
            <circle
              cx="60"
              cy="60"
              r={r}
              className={`fill-none ${t.ring} transition-all duration-700`}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - report.score / 100)}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-5xl font-bold ${t.text}`}>{report.score}</span>
            <span className="text-xs text-zinc-500">out of 100</span>
          </div>
        </div>

        <div className="flex flex-col items-center gap-3 sm:items-start">
          <span
            className={`rounded-xl px-6 py-2 text-3xl font-bold tracking-widest ${
              passed
                ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/40"
                : "bg-rose-500/15 text-rose-400 ring-1 ring-rose-500/40"
            }`}
          >
            {passed ? "PASS" : "FAIL"}
          </span>
          <span className={`text-sm font-medium ${t.text}`}>{report.band}</span>
        </div>
      </section>

      {/* Feedback */}
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <ListSection title="Strengths" items={report.strengths} accent="text-emerald-400" marker="✓" empty="No clear strengths identified." />
        <ListSection title="Areas for Improvement" items={report.weaknesses} accent="text-rose-400" marker="!" empty="No major weaknesses identified." />
      </div>
      <div className="mt-6">
        <ListSection title="Topics to Revise" items={report.topics_to_revise} accent="text-amber-400" marker="→" empty="Nothing specific to revise." />
      </div>

      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-indigo-400">Interviewer&apos;s Verdict</h2>
        <p className="mt-3 leading-relaxed text-zinc-200">{report.verdict}</p>
      </section>
    </>
  );
}

function ListSection({
  title,
  items,
  accent,
  marker,
  empty,
}: Readonly<{ title: string; items: string[]; accent: string; marker: string; empty: string }>) {
  return (
    <section className="h-full rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
      <h2 className={`text-sm font-semibold uppercase tracking-wider ${accent}`}>{title}</h2>
      {items.length ? (
        <ul className="mt-3 space-y-2.5">
          {items.map((item) => (
            <li key={item} className="flex gap-3 leading-relaxed text-zinc-200">
              <span className={`mt-0.5 shrink-0 font-bold ${accent}`} aria-hidden>
                {marker}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-zinc-500">{empty}</p>
      )}
    </section>
  );
}
