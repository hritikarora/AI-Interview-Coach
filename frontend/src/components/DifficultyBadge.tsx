import type { Difficulty } from "@/lib/api";

const STYLES: Record<Difficulty, string> = {
  easy: "border-emerald-800 bg-emerald-950/50 text-emerald-300",
  medium: "border-amber-800 bg-amber-950/50 text-amber-300",
  hard: "border-rose-800 bg-rose-950/50 text-rose-300",
};

export function DifficultyBadge({ difficulty }: Readonly<{ difficulty: Difficulty }>) {
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${STYLES[difficulty]}`}>
      {difficulty}
    </span>
  );
}
