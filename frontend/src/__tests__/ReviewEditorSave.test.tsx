import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import type { ApplicationResult } from "@/lib/api";

import { makeCv, makeLetter, makeReport } from "./fixtures";

const result: ApplicationResult = {
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
};

type Extra = { saving?: boolean; saveMessage?: string | null; saveError?: string | null };

function setup(withSave = true, extra: Extra = {}) {
  const onSave = vi.fn();
  const user = userEvent.setup();
  render(
    <ReviewEditor
      result={result}
      busy={false}
      error={null}
      onRegenerate={vi.fn()}
      onSave={withSave ? onSave : undefined}
      {...extra}
    />,
  );
  return { onSave, user };
}

describe("ReviewEditor save button", () => {
  it("is not shown when saving is not available", () => {
    setup(false);

    expect(
      screen.queryByRole("button", { name: "Save to my applications" }),
    ).not.toBeInTheDocument();
  });

  it("saves the text as it is currently edited", async () => {
    const { onSave, user } = setup();

    const profile = screen.getByLabelText("Profile");
    await user.clear(profile);
    await user.type(profile, "My own profile.");
    await user.click(screen.getByRole("button", { name: "Save to my applications" }));

    const saved = (onSave.mock.calls[0] as [EditedDocuments])[0];
    expect(saved.cv.profile).toBe("My own profile.");
    expect(saved.photoBase64).toBe("iVBORw0KGgo=");
  });

  it("leaves the photo out when it was unticked", async () => {
    const { onSave, user } = setup();

    await user.click(screen.getByLabelText("Keep the photo in the CV"));
    await user.click(screen.getByRole("button", { name: "Save to my applications" }));

    expect((onSave.mock.calls[0] as [EditedDocuments])[0].photoBase64).toBeNull();
  });

  it("is locked while saving", () => {
    setup(true, { saving: true });

    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });

  it("is blocked while the form has a problem", async () => {
    const { user } = setup();

    await user.clear(screen.getByLabelText("Subject"));

    expect(screen.getByRole("button", { name: "Save to my applications" })).toBeDisabled();
  });

  it("shows the confirmation and the error", () => {
    setup(true, { saveMessage: "Saved as application #7.", saveError: "The title is required." });

    expect(screen.getByText("Saved as application #7.")).toBeInTheDocument();
    expect(screen.getByText("The title is required.")).toBeInTheDocument();
  });
});
