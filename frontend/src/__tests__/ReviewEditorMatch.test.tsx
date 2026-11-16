import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import type { ApplicationResult } from "@/lib/api";

import { makeCv, makeLetter, makeReport } from "./fixtures";

function setup(report = makeReport()) {
  const onRegenerate = vi.fn();
  const user = userEvent.setup();
  const result: ApplicationResult = {
    jobTitle: "Data Engineer",
    company: "Acme",
    language: "fr",
    photoUsed: false,
    cvPdfBase64: "",
    letterPdfBase64: "",
    originalCv: makeCv(),
    cv: makeCv(),
    letter: makeLetter(),
    photoBase64: null,
    report,
  };
  render(<ReviewEditor result={result} busy={false} error={null} onRegenerate={onRegenerate} />);
  return { onRegenerate, user };
}

async function regenerate(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Regenerate PDFs" }));
}

function sentCv(onRegenerate: ReturnType<typeof vi.fn>): EditedDocuments["cv"] {
  return (onRegenerate.mock.calls.at(-1) as [EditedDocuments])[0].cv;
}

describe("Match with the offer", () => {
  it("shows the matched skills, the missing ones and what the AI changed", () => {
    setup();

    const report = screen.getByRole("region", { name: "Match with the offer" });
    expect(report).toHaveTextContent("Python");
    expect(screen.getByLabelText(/Kubernetes/)).not.toBeChecked();
    expect(report).toHaveTextContent("required");
    expect(report).toHaveTextContent("nice to have");
    expect(report).toHaveTextContent("Profile rewritten with the words of the offer.");
  });

  it("adds a ticked skill to the CV in the language of the CV", async () => {
    const { onRegenerate, user } = setup();

    await user.click(screen.getByLabelText(/Kubernetes/));
    await regenerate(user);

    expect(screen.getByLabelText(/Kubernetes/)).toBeChecked();
    expect(sentCv(onRegenerate).skills.at(-1)).toEqual({
      category: "Autres compétences",
      items: ["Kubernetes"],
    });
  });

  it("removes a skill when it is unticked", async () => {
    const { onRegenerate, user } = setup();

    await user.click(screen.getByLabelText(/Kubernetes/));
    await user.click(screen.getByLabelText(/Kubernetes/));
    await regenerate(user);

    const skills = sentCv(onRegenerate).skills.flatMap((group) => group.items);
    expect(skills).not.toContain("Kubernetes");
  });

  it("shows nothing when there is nothing to report", () => {
    setup(makeReport({ matchedSkills: [], missingSkills: [], changes: [] }));

    expect(screen.queryByRole("region", { name: "Match with the offer" })).not.toBeInTheDocument();
  });
});
