"use client";

import { useEffect, useState } from "react";

import type { GenerationStage } from "@/lib/api";

type Step = { stages: GenerationStage[]; label: string };

function stepsFor(includeLetter: boolean): Step[] {
  return [
    { stages: ["queued", "reading"], label: "Reading the offer and your CV" },
    { stages: ["translating"], label: "Translating your CV to the language of the offer" },
    {
      stages: ["tailoring"],
      label: includeLetter ? "Tailoring your CV and writing the letter" : "Tailoring your CV",
    },
    { stages: ["rendering", "finished"], label: "Making the PDFs" },
  ];
}

function ElapsedSeconds() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  return <>{seconds}</>;
}

type Props = {
  stage: GenerationStage;
  includeLetter: boolean;
  /** true once the server said it translates the CV: the step only shows when it happens. */
  translated: boolean;
};

/** Where the generation is. */
export function GenerationProgress({ stage, includeLetter, translated }: Props) {
  const all = stepsFor(includeLetter);
  const current = all.findIndex((step) => step.stages.includes(stage));
  const steps = all.filter((_step, index) => index !== 1 || translated || stage === "translating");

  return (
    <div role="status" className="mt-6 rounded bg-blue-50 p-4 text-sm text-blue-900">
      <p className="font-medium">
        Creating your application… <ElapsedSeconds /> s
      </p>
      <ol className="mt-2 space-y-1">
        {steps.map((step) => {
          const index = all.indexOf(step);
          const state = index < current ? "done" : index === current ? "current" : "todo";
          return (
            <li key={step.label} aria-current={state === "current" ? "step" : undefined}>
              <span aria-hidden="true" className="mr-2 inline-block w-4">
                {state === "done" ? "✓" : state === "current" ? "…" : "·"}
              </span>
              <span className={state === "todo" ? "text-blue-900/50" : ""}>{step.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-xs text-blue-900/70">
        This usually takes about a minute. You can keep this page open while it works.
      </p>
    </div>
  );
}
