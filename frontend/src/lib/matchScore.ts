import type { MatchScore, MissingSkill } from "@/lib/types";

/** A required skill counts twice as much as a nice-to-have one (same rule as the server). */
const REQUIRED_WEIGHT = 2;
const NICE_WEIGHT = 1;

export type Verdict = {
  label: string;
  advice: string;
  tone: "strong" | "good" | "partial" | "weak";
};

export function scoreOf(counts: Omit<MatchScore, "value">): number | null {
  const total = REQUIRED_WEIGHT * counts.requiredTotal + NICE_WEIGHT * counts.niceTotal;
  if (total === 0) return null;
  const matched = REQUIRED_WEIGHT * counts.requiredMatched + NICE_WEIGHT * counts.niceMatched;
  return Math.round((100 * matched) / total);
}

/** The score once the skills the user ticked (skills they really know) are counted too. */
export function scoreWithTicked(
  score: MatchScore,
  missing: MissingSkill[],
  isAdded: (skill: string) => boolean,
): number | null {
  const ticked = missing.filter((skill) => isAdded(skill.name));
  return scoreOf({
    requiredMatched: score.requiredMatched + ticked.filter((skill) => skill.required).length,
    requiredTotal: score.requiredTotal,
    niceMatched: score.niceMatched + ticked.filter((skill) => !skill.required).length,
    niceTotal: score.niceTotal,
  });
}

export function verdictOf(value: number): Verdict {
  if (value >= 75) {
    return {
      label: "Strong match",
      advice: "This offer fits your profile: apply.",
      tone: "strong",
    };
  }
  if (value >= 55) {
    return {
      label: "Good match",
      advice: "Worth applying: you have most of what they ask for.",
      tone: "good",
    };
  }
  if (value >= 35) {
    return {
      label: "Partial match",
      advice: "You can apply, but expect questions on the skills you are missing.",
      tone: "partial",
    };
  }
  return {
    label: "Weak match",
    advice: "This offer asks for many skills you do not have yet.",
    tone: "weak",
  };
}
