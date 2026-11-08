import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationPanel } from "@/components/ApplicationPanel";

import { makeResultBody } from "./fixtures";

const fetchMock = vi.fn();

const savedBody = {
  id: 7,
  created_at: "2026-11-08T12:00:00+00:00",
  job_title: "Stagiaire DataLab",
  company: "Acme",
  language: "fr",
  source_url: "",
  status: "saved",
  notes: "",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function createAndOpenReview(user: UserEvent) {
  await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
  await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
  await user.click(screen.getByRole("button", { name: "Create my application" }));
  await screen.findByLabelText("Profile");
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn().mockReturnValueOnce("blob:cv").mockReturnValueOnce("blob:letter"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Saving from the review screen", () => {
  it("saves the edited documents to the tracker and confirms", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse(savedBody, 201));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);
    await createAndOpenReview(user);

    const profile = screen.getByLabelText("Profile");
    await user.clear(profile);
    await user.type(profile, "My own profile.");
    await user.click(screen.getByRole("button", { name: "Save to my applications" }));

    expect(await screen.findByText(/Saved as application #7/)).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    const sent = JSON.parse(init.body as string) as {
      job_title: string;
      company: string;
      language: string;
      cv: { profile: string };
      photo_base64: string | null;
    };
    expect(url).toContain("/tracker/applications");
    expect(init.method).toBe("POST");
    expect(sent.job_title).toBe("Stagiaire DataLab");
    expect(sent.company).toBe("Acme");
    expect(sent.language).toBe("fr");
    expect(sent.cv.profile).toBe("My own profile.");
    expect(sent.photo_base64).toBe("iVBORw0KGgo=");
  });

  it("shows the message of the server when saving fails", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse({ detail: "The job title is required." }, 422));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);
    await createAndOpenReview(user);

    await user.click(screen.getByRole("button", { name: "Save to my applications" }));

    expect(await screen.findByText("The job title is required.")).toBeInTheDocument();
    expect(screen.queryByText(/Saved as application/)).not.toBeInTheDocument();
  });

  it("forgets the confirmation when the user starts again", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse(savedBody, 201));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);
    await createAndOpenReview(user);
    await user.click(screen.getByRole("button", { name: "Save to my applications" }));
    await screen.findByText(/Saved as application #7/);

    await user.click(screen.getByRole("button", { name: "Start again" }));

    expect(screen.queryByText(/Saved as application/)).not.toBeInTheDocument();
  });
});
