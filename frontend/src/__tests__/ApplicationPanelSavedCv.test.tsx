import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationPanel } from "@/components/ApplicationPanel";
import type { SavedCv } from "@/lib/savedCvApi";

import { makeDoneJob, makeResultBody } from "./fixtures";
import { jsonResponse } from "./helpers/http";

const fetchMock = vi.fn();
const SAVED: SavedCv = { filename: "cv.docx", size: 7, uploadedAt: "2026-11-10T12:00:00Z" };
const savedBody = { filename: "cv.docx", size: 7, uploaded_at: "2026-11-10T12:00:00Z" };

function call(index: number): [string, RequestInit] {
  return fetchMock.mock.calls[index] as [string, RequestInit];
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(() => "blob:file"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("ApplicationPanel and the saved CV", () => {
  it("saves a new CV first, then creates the application from it", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(savedBody))
      .mockResolvedValueOnce(jsonResponse(makeDoneJob(makeResultBody())));
    const onSavedCvChange = vi.fn();
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel onSavedCvChange={onSavedCvChange} />);

    await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));
    await screen.findByRole("link", { name: "Download CV (PDF)" });

    expect(call(0)[0]).toBe("http://api.test/me/cv");
    expect(call(0)[1].method).toBe("PUT");
    expect(call(1)[0]).toBe("http://api.test/applications");
    expect((call(1)[1].body as FormData).has("cv_file")).toBe(false);
    expect(onSavedCvChange).toHaveBeenCalledWith(SAVED);
  });

  it("uses the saved CV without uploading anything", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeDoneJob(makeResultBody())));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel savedCv={SAVED} onSavedCvChange={vi.fn()} />);

    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));
    await screen.findByRole("link", { name: "Download CV (PDF)" });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect((call(0)[1].body as FormData).has("cv_file")).toBe(false);
  });

  it("shows why the CV could not be saved and creates nothing", async () => {
    const detail = "The file content does not match its extension.";
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail }, 422));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel onSavedCvChange={vi.fn()} />);

    await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
