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

/**
 * The score of the offer for the CV as it is now: the skills the user ticked are in the CV,
 * so they count. The score of the CV as it was sent stays visible next to it.
 */
export function MatchScoreCard({ score, missingSkills, isAdded }: Props) {
  if (score.value === null) return null;
  const ticked = missingSkills.filter((skill) => isAdded(skill.name));
  const requiredTicked = ticked.filter((skill) => skill.required).length;
  const now = scoreWithTicked(score, missingSkills, isAdded) ?? score.value;
  const verdict = verdictOf(now);
  const tone = TONES[verdict.tone];
  const details = [
    counted(score.requiredMatched + requiredTicked, score.requiredTotal, "required"),
    counted(score.niceMatched + ticked.length - requiredTicked, score.niceTotal, "nice-to-have"),
  ].filter((part) => part !== null);

  return (
    <div className={`mt-3 rounded border p-3 ${tone.box}`}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-semibold">
          Match score: <span className="text-2xl">{now}</span>/100 · {verdict.label}
        </p>
      </div>
      <div
        role="meter"
        aria-label="Match score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={now}
        className="mt-2 h-2 w-full overflow-hidden rounded bg-white/70"
      >
        <div
          className={`h-full transition-all duration-500 ${tone.bar}`}
          style={{ width: `${now}%` }}
        />
      </div>
      <p className="mt-2">{verdict.advice}</p>
      <p className="mt-1 text-xs opacity-80">
        Your CV has {details.join(" and ")}. A required skill counts twice.
      </p>
      {now !== score.value && (
        <p role="status" className="mt-1 text-xs font-medium">
          Before your additions: {score.value}/100. Click &quot;Regenerate PDFs&quot; to put the
          ticked skills in your PDF.
        </p>
      )}
    </div>
  );
}
