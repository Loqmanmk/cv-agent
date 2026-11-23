import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GenerationProgress } from "@/components/GenerationProgress";

function steps(): string[] {
  return screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
}

describe("GenerationProgress", () => {
  it("marks the steps already done and the current one", () => {
    render(<GenerationProgress stage="tailoring" includeLetter translated={false} />);

    expect(steps()).toEqual([
      "✓Reading the offer and your CV",
      "…Tailoring your CV and writing the letter",
      "·Making the PDFs",
    ]);
    expect(
      screen.getByText("Tailoring your CV and writing the letter").closest("li"),
    ).toHaveAttribute("aria-current", "step");
  });

  it("shows the translation only when it happens", () => {
    const { rerender } = render(
      <GenerationProgress stage="reading" includeLetter={false} translated={false} />,
    );
    expect(steps()).toHaveLength(3);

    rerender(<GenerationProgress stage="translating" includeLetter={false} translated />);
    expect(steps()[1]).toBe("…Translating your CV to the language of the offer");

    rerender(<GenerationProgress stage="rendering" includeLetter={false} translated />);
    expect(steps()[1]).toBe("✓Translating your CV to the language of the offer");
  });

  it("leaves out the letter when none was asked", () => {
    render(<GenerationProgress stage="queued" includeLetter={false} translated={false} />);

    expect(screen.getByText("Tailoring your CV")).toBeInTheDocument();
  });
});
