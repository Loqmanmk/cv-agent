import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import type { ApplicationResult } from "@/lib/api";

import { makeCv, makeLetter, makeReport } from "./fixtures";

function setup() {
  const onRegenerate = vi.fn();
  const user = userEvent.setup();
  const result: ApplicationResult = {
    jobTitle: "Stagiaire DataLab",
    company: "",
    language: "fr",
    photoUsed: false,
    cvPdfBase64: "",
    letterPdfBase64: "",
    originalCv: makeCv(),
    cv: makeCv(),
    letter: makeLetter(),
    photoBase64: null,
    report: makeReport(),
  };
  render(<ReviewEditor result={result} busy={false} error={null} onRegenerate={onRegenerate} />);
  return { onRegenerate, user };
}

async function regenerate(
  user: ReturnType<typeof userEvent.setup>,
  onRegenerate: ReturnType<typeof vi.fn>,
): Promise<EditedDocuments> {
  await user.click(screen.getByRole("button", { name: "Regenerate PDFs" }));
  return (onRegenerate.mock.calls[0] as [EditedDocuments])[0];
}

describe("ReviewEditor letter header", () => {
  it("shows the subject and the recipient of the letter", () => {
    setup();

    expect(screen.getByLabelText("Subject")).toHaveValue(makeLetter().subject);
    expect(screen.getByLabelText("Company")).toHaveValue("Acme");
    expect(screen.getByLabelText("Recipient contact")).toHaveValue("");
    expect(screen.getByLabelText("Company address")).toHaveValue("");
  });

  it("sends a company typed by the user, trimmed", async () => {
    const { onRegenerate, user } = setup();

    const company = screen.getByLabelText("Company");
    await user.clear(company);
    await user.type(company, "  Coface  ");
    const edited = await regenerate(user, onRegenerate);

    expect(edited.letter.recipient.company).toBe("Coface");
  });

  it("sends the contact and the address", async () => {
    const { onRegenerate, user } = setup();

    await user.type(screen.getByLabelText("Recipient contact"), "Mme Martin");
    await user.type(screen.getByLabelText("Company address"), "1 rue Exemple, Paris");
    const edited = await regenerate(user, onRegenerate);

    expect(edited.letter.recipient.contact).toBe("Mme Martin");
    expect(edited.letter.recipient.address).toBe("1 rue Exemple, Paris");
  });

  it("sends an edited subject", async () => {
    const { onRegenerate, user } = setup();

    const subject = screen.getByLabelText("Subject");
    await user.clear(subject);
    await user.type(subject, "Candidature spontanée");
    const edited = await regenerate(user, onRegenerate);

    expect(edited.letter.subject).toBe("Candidature spontanée");
  });

  it("blocks regeneration when the subject is empty", async () => {
    const { user } = setup();

    await user.clear(screen.getByLabelText("Subject"));

    expect(screen.getByText("The letter needs a subject line.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate PDFs" })).toBeDisabled();
  });
});
