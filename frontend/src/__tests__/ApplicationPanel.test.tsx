import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationPanel } from "@/components/ApplicationPanel";

const fetchMock = vi.fn();
const revokeMock = vi.fn();

const successBody = {
  job_title: "Stagiaire DataLab",
  company: "Coface",
  language: "fr",
  photo_used: true,
  cv_pdf_base64: btoa("%PDF-cv"),
  letter_pdf_base64: btoa("%PDF-letter"),
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function fillAndSubmit(user: UserEvent) {
  await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
  await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
  await user.click(screen.getByRole("button", { name: "Create my application" }));
}

function setup() {
  const user = userEvent.setup({ applyAccept: false });
  const view = render(<ApplicationPanel />);
  return { user, ...view };
}

beforeEach(() => {
  fetchMock.mockReset();
  revokeMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn().mockReturnValueOnce("blob:cv").mockReturnValueOnce("blob:letter"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: revokeMock,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApplicationPanel", () => {
  it("shows progress and locks the form while waiting", async () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByRole("status")).toHaveTextContent("Creating your application");
    expect(screen.getByLabelText("Job offer")).toBeDisabled();
  });

  it("shows the result with a download link for each PDF", async () => {
    fetchMock.mockResolvedValue(jsonResponse(successBody));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByRole("heading", { name: /Stagiaire DataLab/ })).toBeInTheDocument();
    const cvLink = screen.getByRole("link", { name: "Download CV (PDF)" });
    const letterLink = screen.getByRole("link", { name: "Download cover letter (PDF)" });
    expect(cvLink).toHaveAttribute("href", "blob:cv");
    expect(cvLink).toHaveAttribute("download", "cv-coface.pdf");
    expect(letterLink).toHaveAttribute("href", "blob:letter");
    expect(letterLink).toHaveAttribute("download", "lettre-coface.pdf");
  });

  it("warns when a photo was requested but not found", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...successBody, photo_used: false }));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByText(/No photo was found/)).toBeInTheDocument();
  });

  it("shows the message of the backend when the request fails", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "The CV file is empty." }, 422));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("The CV file is empty.");
  });

  it("lists the violations of a rejected AI result", async () => {
    const body = { detail: "Not faithful.", violations: ["skill 'Kubernetes' is not in the CV"] };
    fetchMock.mockResolvedValue(jsonResponse(body, 502));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByText("skill 'Kubernetes' is not in the CV")).toBeInTheDocument();
  });

  it("goes back to the form and releases the files on start again", async () => {
    fetchMock.mockResolvedValue(jsonResponse(successBody));
    const { user } = setup();
    await fillAndSubmit(user);

    await user.click(await screen.findByRole("button", { name: "Start again" }));

    expect(screen.queryByRole("link", { name: "Download CV (PDF)" })).not.toBeInTheDocument();
    expect(revokeMock).toHaveBeenCalledWith("blob:cv");
    expect(revokeMock).toHaveBeenCalledWith("blob:letter");
  });

  it("releases the files when the page is left", async () => {
    fetchMock.mockResolvedValue(jsonResponse(successBody));
    const { user, unmount } = setup();
    await fillAndSubmit(user);
    await screen.findByRole("link", { name: "Download CV (PDF)" });

    unmount();

    expect(revokeMock).toHaveBeenCalledTimes(2);
  });
});
