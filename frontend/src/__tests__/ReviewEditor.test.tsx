import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import type { ApplicationResult } from "@/lib/api";

import { makeCv, makeLetter, makeReport } from "./fixtures";

function makeResult(overrides: Partial<ApplicationResult> = {}): ApplicationResult {
  return {
    jobTitle: "Stagiaire DataLab",
    company: "Coface",
    language: "fr",
    photoUsed: true,
    cvPdfBase64: "",
    letterPdfBase64: "",
    originalCv: makeCv(),
    cv: makeCv({ profile: "Tailored profile." }),
    letter: makeLetter(),
    photoBase64: "iVBORw0KGgo=",
    report: makeReport(),
    ...overrides,
  };
}

function setup(props: { result?: ApplicationResult; busy?: boolean; error?: string | null } = {}) {
  const onRegenerate = vi.fn();
  const user = userEvent.setup();
  render(
    <ReviewEditor
      result={props.result ?? makeResult()}
      busy={props.busy ?? false}
      error={props.error ?? null}
      onRegenerate={onRegenerate}
    />,
  );
  return { onRegenerate, user };
}

async function regenerated(
  user: ReturnType<typeof userEvent.setup>,
  onRegenerate: ReturnType<typeof vi.fn>,
): Promise<EditedDocuments> {
  await user.click(screen.getByRole("button", { name: "Regenerate PDFs" }));
  expect(onRegenerate).toHaveBeenCalledTimes(1);
  return (onRegenerate.mock.calls[0] as [EditedDocuments])[0];
}

describe("ReviewEditor", () => {
  it("shows your original text next to the tailored text", () => {
    setup();

    expect(screen.getByText("Original profile.")).toBeInTheDocument();
    expect(screen.getByLabelText("Profile")).toHaveValue("Tailored profile.");
    expect(screen.getByText("Back-end: Python, FastAPI")).toBeInTheDocument();
  });

  it("sends the edited profile and headline", async () => {
    const { onRegenerate, user } = setup();

    const profile = screen.getByLabelText("Profile");
    await user.clear(profile);
    await user.type(profile, "My own profile.");
    const headline = screen.getByLabelText("Headline");
    await user.clear(headline);
    await user.type(headline, "Data Engineer");
    const edited = await regenerated(user, onRegenerate);

    expect(edited.cv.profile).toBe("My own profile.");
    expect(edited.cv.header.headline).toBe("Data Engineer");
    expect(edited.cv.header.email).toBe("jane@example.com");
  });

  it("removes a bullet when it is cleared", async () => {
    const { onRegenerate, user } = setup();

    await user.clear(screen.getByLabelText("Mobile Developer bullet 2"));
    const edited = await regenerated(user, onRegenerate);

    expect(edited.cv.experiences[0]?.bullets).toEqual(["Built an Android app"]);
  });

  it("edits a project bullet", async () => {
    const { onRegenerate, user } = setup();

    const bullet = screen.getByLabelText("PathFinder bullet 1");
    await user.clear(bullet);
    await user.type(bullet, "Recommendation model");
    const edited = await regenerated(user, onRegenerate);

    expect(edited.cv.projects[0]?.bullets).toEqual(["Recommendation model"]);
  });

  it("edits the skills as comma separated text", async () => {
    const { onRegenerate, user } = setup();

    const items = screen.getByLabelText("Skills group 1 items");
    await user.clear(items);
    await user.type(items, "Python, FastAPI, Docker");
    const edited = await regenerated(user, onRegenerate);

    expect(edited.cv.skills[0]).toEqual({
      category: "Back-end",
      items: ["Python", "FastAPI", "Docker"],
    });
  });

  it("removes a skills group when its skills are cleared", async () => {
    const { onRegenerate, user } = setup();

    await user.clear(screen.getByLabelText("Skills group 2 items"));
    const edited = await regenerated(user, onRegenerate);

    expect(edited.cv.skills.map((group) => group.category)).toEqual(["Back-end"]);
  });

  it("blocks regeneration when a skills group has no name", async () => {
    const { user } = setup();

    await user.clear(screen.getByLabelText("Skills group 1 name"));

    expect(screen.getByText("Every skills group that has items needs a name.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate PDFs" })).toBeDisabled();
  });

  it("edits the letter paragraphs and keeps the closing fixed", async () => {
    const { onRegenerate, user } = setup();

    const paragraph = screen.getByLabelText("Letter paragraph 1");
    await user.clear(paragraph);
    await user.type(paragraph, "My opening.");
    const edited = await regenerated(user, onRegenerate);

    expect(edited.letter?.paragraphs).toEqual([
      "My opening.",
      "Experience paragraph.",
      "Motivation paragraph.",
      "Fixed closing.",
    ]);
    expect(screen.queryByLabelText("Letter paragraph 4")).not.toBeInTheDocument();
    expect(screen.getByText(/Fixed closing\./)).toBeInTheDocument();
  });

  it("sends the photo by default and can leave it out", async () => {
    const first = setup();
    const withPhoto = await regenerated(first.user, first.onRegenerate);

    expect(withPhoto.photoBase64).toBe("iVBORw0KGgo=");
  });

  it("leaves the photo out when it is unticked", async () => {
    const { onRegenerate, user } = setup();

    await user.click(screen.getByLabelText("Keep the photo in the CV"));
    const edited = await regenerated(user, onRegenerate);

    expect(edited.photoBase64).toBeNull();
  });

  it("offers no photo option when the CV has no photo", () => {
    setup({ result: makeResult({ photoBase64: null, photoUsed: false }) });

    expect(screen.queryByLabelText("Keep the photo in the CV")).not.toBeInTheDocument();
  });

  it("locks the button while regenerating", () => {
    setup({ busy: true });

    expect(screen.getByRole("button", { name: "Regenerating…" })).toBeDisabled();
  });

  it("shows an error", () => {
    setup({ error: "The documents are too long." });

    expect(screen.getByText("The documents are too long.")).toBeInTheDocument();
  });
});
