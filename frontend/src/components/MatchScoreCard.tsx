"use client";

import { scoreWithTicked, verdictOf, type Verdict } from "@/lib/matchScore";
import type { MatchScore, MissingSkill } from "@/lib/types";

type Props = {
  score: MatchScore;
  missingSkills: MissingSkill[];
  isAdded: (skill: string) => boolean;
};

const TONES: Record<Verdict["tone"], { box: string; bar: string }> = {
  strong: { box: "border-green-300 bg-green-50 text-green-900", bar: "bg-green-600" },
  good: { box: "border-lime-300 bg-lime-50 text-lime-900", bar: "bg-lime-600" },
  partial: { box: "border-amber-300 bg-amber-50 text-amber-900", bar: "bg-amber-500" },
  weak: { box: "border-red-300 bg-red-50 text-red-900", bar: "bg-red-600" },
};

function counted(matched: number, total: number, kind: string): string | null {
  return total === 0 ? null : `${matched} of ${total} ${kind} skills`;
}

/** The score of the offer for this CV, and what it becomes with the skills the user ticked. */
export function MatchScoreCard({ score, missingSkills, isAdded }: Props) {
  if (score.value === null) return null;
  const verdict = verdictOf(score.value);
  const tone = TONES[verdict.tone];
  const withTicked = scoreWithTicked(score, missingSkills, isAdded);
  const details = [
    counted(score.requiredMatched, score.requiredTotal, "required"),
    counted(score.niceMatched, score.niceTotal, "nice-to-have"),
  ].filter((part) => part !== null);

  return (
    <div className={`mt-3 rounded border p-3 ${tone.box}`}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-semibold">
          Match score: <span className="text-2xl">{score.value}</span>/100 · {verdict.label}
        </p>
      </div>
      <div
        role="meter"
        aria-label="Match score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score.value}
        className="mt-2 h-2 w-full overflow-hidden rounded bg-white/70"
      >
        <div className={`h-full ${tone.bar}`} style={{ width: `${score.value}%` }} />
      </div>
      <p className="mt-2">{verdict.advice}</p>
      <p className="mt-1 text-xs opacity-80">
        Your CV has {details.join(" and ")}. A required skill counts twice.
      </p>
      {withTicked !== null && withTicked > score.value && (
        <p role="status" className="mt-1 text-xs font-medium">
          With the skills you ticked: {withTicked}/100.
        </p>
      )}
    </div>
  );
}
