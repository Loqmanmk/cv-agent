"use client";

import { MatchScoreCard } from "@/components/MatchScoreCard";
import type { MatchPreview } from "@/lib/api";

const NOTHING_ADDED = () => false;

/** The match score of the CV for the offer, shown before the user decides to create. */
export function ScorePreview({ preview }: { preview: MatchPreview }) {
  const { jobTitle, company, report } = preview;
  const required = report.missingSkills.filter((skill) => skill.required);
  const nice = report.missingSkills.filter((skill) => !skill.required);

  return (
    <section aria-label="Match score" className="mt-6 rounded border p-4 text-sm">
      <h2 className="text-base font-semibold">
        Your match with {jobTitle || "this offer"}
        {company ? ` — ${company}` : ""}
      </h2>
      {report.score.value === null ? (
        <p className="mt-2 text-gray-700">
          The offer names no skills, so there is no score to give. You can still create the
          application.
        </p>
      ) : (
        <MatchScoreCard
          score={report.score}
          missingSkills={report.missingSkills}
          isAdded={NOTHING_ADDED}
        />
      )}
      {report.matchedSkills.length > 0 && (
        <p className="mt-3">
          <span className="font-medium">You have:</span> {report.matchedSkills.join(", ")}
        </p>
      )}
      {required.length > 0 && (
        <p className="mt-1">
          <span className="font-medium">Required, not in your CV:</span>{" "}
          {required.map((skill) => skill.name).join(", ")}
        </p>
      )}
      {nice.length > 0 && (
        <p className="mt-1">
          <span className="font-medium">Nice to have, not in your CV:</span>{" "}
          {nice.map((skill) => skill.name).join(", ")}
        </p>
      )}
      <p className="mt-3 text-gray-600">
        If you create the application, you can add the skills you really know on the next screen.
      </p>
    </section>
  );
}
