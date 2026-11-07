import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApplicationForm } from "@/components/ApplicationForm";

function setup(disabled = false) {
  const onSubmit = vi.fn();
  const user = userEvent.setup({ applyAccept: false });
  render(<ApplicationForm onSubmit={onSubmit} disabled={disabled} />);
  return { onSubmit, user };
}

const cv = new File(["content"], "cv.docx");

describe("ApplicationForm", () => {
  it("shows both errors and sends nothing when the form is empty", async () => {
    const { onSubmit, user } = setup();

    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(screen.getByText("Choose your CV file.")).toBeInTheDocument();
    expect(screen.getByText("Paste the job offer.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("refuses a file with the wrong extension", async () => {
    const { onSubmit, user } = setup();

    await user.upload(screen.getByLabelText(/cv file/i), new File(["x"], "cv.txt"));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(screen.getByText("The CV must be a .docx or .pdf file.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the file, the trimmed job offer and the photo choice", async () => {
    const { onSubmit, user } = setup();

    await user.upload(screen.getByLabelText(/cv file/i), cv);
    await user.type(screen.getByLabelText("Job offer"), "  Acme seeks an intern.  ");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(onSubmit).toHaveBeenCalledWith({
      cvFile: cv,
      jobText: "Acme seeks an intern.",
      includePhoto: true,
    });
  });

  it("lets the user exclude the photo", async () => {
    const { onSubmit, user } = setup();

    await user.upload(screen.getByLabelText(/cv file/i), cv);
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByLabelText("Include my photo"));
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ includePhoto: false }));
  });

  it("shows the number of characters typed", async () => {
    const { user } = setup();

    await user.type(screen.getByLabelText("Job offer"), "abc");

    expect(screen.getByText("3 / 20000")).toBeInTheDocument();
  });

  it("disables every field while disabled", () => {
    setup(true);

    expect(screen.getByLabelText(/cv file/i)).toBeDisabled();
    expect(screen.getByLabelText("Job offer")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create my application" })).toBeDisabled();
  });
});
