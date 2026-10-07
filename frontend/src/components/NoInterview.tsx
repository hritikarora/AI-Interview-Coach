import Link from "next/link";

export function NoInterview() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-zinc-400">No interview in progress.</p>
      <Link href="/" className="text-indigo-400 hover:text-indigo-300">
        Start a new interview →
      </Link>
    </main>
  );
}
