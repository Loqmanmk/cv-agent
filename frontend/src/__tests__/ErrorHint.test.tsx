import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorHint } from "@/components/ErrorHint";
import { ApiError } from "@/lib/api";

describe("ErrorHint", () => {
  it("explains a reached monthly limit", () => {
    render(<ErrorHint error={new ApiError("Monthly limit reached: 3 applications.", 402)} />);

    expect(screen.getByText(/monthly applications reset/)).toBeInTheDocument();
  });

  it("links to the profile when it is incomplete", () => {
    const error = new ApiError(
      "Complete your profile (at least your city) before creating an application.",
      422,
    );

    render(<ErrorHint error={error} />);

    expect(screen.getByRole("link", { name: "Open my profile" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });

  it("adds nothing to other errors", () => {
    const { container } = render(<ErrorHint error={new ApiError("The CV file is empty.", 422)} />);

    expect(container).toBeEmptyDOMElement();
  });
});
