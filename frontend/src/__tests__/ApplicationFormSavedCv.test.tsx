import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApplicationForm } from "@/components/ApplicationForm";
import type { SavedCv } from "@/lib/savedCvApi";

const SAVED: SavedCv = { filename: "CV_Jane.pdf", size: 1200, uploadedAt: "2026-11-10T12:00:00Z" };
const cv = new File(["content"], "new.docx");

function setup(props: Partial<Parameters<typeof ApplicationForm>[0]> = {}) {
  const onSubmit = vi.fn();
  const user = userEvent.setup({ applyAccept: false });
  render(<ApplicationForm onSubmit={onSubmit} {...props} />);
  return { onSubmit, user };
}

describe("ApplicationForm with a saved CV", () => {
  it("shows the saved CV instead of the file field", () => {
    setup({ savedCv: SAVED });

    expect(screen.getByText("CV_Jane.pdf")).toBeInTheDocument();
    expect(screen.getByText("Saved on 10 November 2026")).toBeInTheDocument();
    expect(screen.queryByLabelText(/cv file/i)).not.toBeInTheDocument();
  });

  it("creates the application from the saved CV without choosing a file", async () => {
    const { onSubmit, user } = setup({ savedCv: SAVED });

    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(onSubmit).toHaveBeenCalledWith({
      cvFile: null,
      jobText: "Acme seeks an intern.",
      includePhoto: true,
      includeLetter: true,
      saveCv: false,
    });
  });

  it("lets the user change the CV and save the new one", async () => {
    const { onSubmit, user } = setup({ savedCv: SAVED, canSaveCv: true });

    await user.click(screen.getByRole("button", { name: "Change my CV" }));
    await user.upload(screen.getByLabelText(/cv file/i), cv);
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(screen.getByLabelText("Save this CV for my next applications")).toBeChecked();
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ cvFile: cv, saveCv: true }));
  });

  it("asks for a file after Change my CV until one is chosen", async () => {
    const { onSubmit, user } = setup({ savedCv: SAVED });

    await user.click(screen.getByRole("button", { name: "Change my CV" }));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(screen.getByText("Choose your CV file.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("goes back to the saved CV", async () => {
    const { user } = setup({ savedCv: SAVED });

    await user.click(screen.getByRole("button", { name: "Change my CV" }));
    await user.click(screen.getByRole("button", { name: "Keep my saved CV (CV_Jane.pdf)" }));

    expect(screen.getByRole("button", { name: "Change my CV" })).toBeInTheDocument();
  });

  it("lets the user keep a new file only for this application", async () => {
    const { onSubmit, user } = setup({ canSaveCv: true });

    await user.upload(screen.getByLabelText(/cv file/i), cv);
    await user.click(screen.getByLabelText("Save this CV for my next applications"));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ cvFile: cv, saveCv: false }));
  });

  it("offers to delete the saved CV", async () => {
    const onRemoveSavedCv = vi.fn();
    const { user } = setup({ savedCv: SAVED, onRemoveSavedCv });

    await user.click(screen.getByRole("button", { name: "Delete my saved CV" }));

    expect(onRemoveSavedCv).toHaveBeenCalledOnce();
  });
});
