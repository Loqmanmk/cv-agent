"use client";

import { MatchScoreCard } from "@/components/MatchScoreCard";
import type { MatchReport, MissingSkill } from "@/lib/types";

type Props = {
  report: MatchReport;
  isAdded: (skill: string) => boolean;
  onToggle: (skill: MissingSkill, added: boolean) => void;
};

export function MatchReportPanel({ report, isAdded, onToggle }: Props) {
  const { matchedSkills, missingSkills, changes, score } = report;
  const empty = matchedSkills.length === 0 && missingSkills.length === 0 && changes.length === 0;
  if (empty && score.value === null) {
    return null;
  }

  return (
    <section aria-label="Match with the offer" className="mt-6 rounded border p-4 text-sm">
      <h3 className="text-base font-semibold">Match with the offer</h3>
      <MatchScoreCard score={score} missingSkills={missingSkills} isAdded={isAdded} />

      {matchedSkills.length > 0 && (
        <div className="mt-3">
          <p className="font-medium">Asked by the offer and already in your CV</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {matchedSkills.map((skill) => (
              <li key={skill} className="rounded bg-green-100 px-2 py-0.5 text-green-900">
                {skill}
              </li>
            ))}
          </ul>
        </div>
      )}

      {missingSkills.length > 0 && (
        <fieldset className="mt-4">
          <legend className="font-medium">Asked by the offer but not in your CV</legend>
          <p className="mt-1 text-gray-600">
            Tick only what you really know: the recruiter may ask about it in the interview. Each
            ticked skill joins the group of related skills, for example Kubernetes with your DevOps
            skills. Then click &quot;Regenerate PDFs&quot;.
          </p>
          <ul className="mt-2 space-y-1">
            {missingSkills.map((skill) => {
              const id = `missing-skill-${skill.name}`;
              return (
                <li key={skill.name} className="flex items-center gap-2">
                  <input
                    id={id}
                    type="checkbox"
                    checked={isAdded(skill.name)}
                    onChange={(event) => onToggle(skill, event.target.checked)}
                  />
                  <label htmlFor={id}>
                    {skill.name}
                    <span className="ml-2 text-xs text-gray-500">
                      {skill.required ? "required" : "nice to have"}
                      {skill.group && ` · goes to ${skill.group}`}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>
      )}

      {changes.length > 0 && (
        <div className="mt-4">
          <p className="font-medium">What the AI changed</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-gray-700">
            {changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
