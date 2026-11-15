import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NewApplication } from "@/components/NewApplication";

import { jsonResponse } from "./helpers/http";

const fetchMock = vi.fn();
const usageBody = { plan: "free", used: 0, limit: 3, resets_at: "2026-12-01T00:00:00Z" };
const savedBody = { filename: "CV_Jane.pdf", size: 7, uploaded_at: "2026-11-10T12:00:00Z" };

function answer(saved: unknown) {
  fetchMock.mockImplementation((url: string, init: RequestInit) => {
    if (url.endsWith("/me/usage")) return Promise.resolve(jsonResponse(usageBody));
    if (url.endsWith("/me/cv") && init.method === "DELETE") {
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    return Promise.resolve(jsonResponse(saved));
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("NewApplication", () => {
  it("shows the saved CV of the user", async () => {
    answer(savedBody);

    render(<NewApplication />);

    expect(await screen.findByText("CV_Jane.pdf")).toBeInTheDocument();
  });

  it("asks for a file when no CV is saved", async () => {
    answer(null);

    render(<NewApplication />);

    expect(await screen.findByLabelText(/cv file/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Save this CV for my next applications")).toBeChecked();
  });

  it("deletes the saved CV and asks for a file again", async () => {
    answer(savedBody);
    const user = userEvent.setup();
    render(<NewApplication />);

    await user.click(await screen.findByRole("button", { name: "Delete my saved CV" }));

    expect(await screen.findByLabelText(/cv file/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/me/cv",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
