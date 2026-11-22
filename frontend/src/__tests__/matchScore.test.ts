import { describe, expect, it } from "vitest";

import { scoreOf, scoreWithTicked, verdictOf } from "@/lib/matchScore";
import type { MatchScore } from "@/lib/types";

const score: MatchScore = {
  value: 40,
  requiredMatched: 1,
  requiredTotal: 2,
  niceMatched: 0,
  niceTotal: 1,
};

describe("scoreOf", () => {
  it("counts a required skill twice as much as a nice-to-have one", () => {
    expect(scoreOf(score)).toBe(40);
  });

  it("has no score when the offer names no skills", () => {
    expect(scoreOf({ requiredMatched: 0, requiredTotal: 0, niceMatched: 0, niceTotal: 0 })).toBe(
      null,
    );
  });
});

describe("scoreWithTicked", () => {
  it("adds the ticked skills to the matched ones", () => {
    const missing = [
      { name: "Kubernetes", required: true, group: null },
      { name: "Terraform", required: false, group: null },
    ];

    expect(scoreWithTicked(score, missing, (name) => name === "Terraform")).toBe(60);
    expect(scoreWithTicked(score, missing, () => true)).toBe(100);
  });
});

describe("verdictOf", () => {
  it.each([
    [100, "Strong match"],
    [75, "Strong match"],
    [74, "Good match"],
    [55, "Good match"],
    [54, "Partial match"],
    [35, "Partial match"],
    [34, "Weak match"],
    [0, "Weak match"],
  ])("gives %i the verdict %s", (value, label) => {
    expect(verdictOf(value).label).toBe(label);
  });
});
