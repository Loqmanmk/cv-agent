import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationPanel } from "@/components/ApplicationPanel";

import { makeResultBody } from "./fixtures";

const fetchMock = vi.fn();
const revokeMock = vi.fn();

const renderBody = {
  cv_pdf_base64: btoa("%PDF-cv2"),
  letter_pdf_base64: btoa("%PDF-letter2"),
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

async function editProfileAndRegenerate(user: UserEvent) {
  const profile = await screen.findByLabelText("Profile");
  await user.clear(profile);
  await user.type(profile, "My own profile.");
  await user.click(screen.getByRole("button", { name: "Regenerate PDFs" }));
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
    value: vi
      .fn()
      .mockReturnValueOnce("blob:cv")
      .mockReturnValueOnce("blob:letter")
      .mockReturnValueOnce("blob:cv2")
      .mockReturnValueOnce("blob:letter2"),
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
    fetchMock.mockResolvedValue(jsonResponse(makeResultBody()));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByRole("heading", { name: /Stagiaire DataLab/ })).toBeInTheDocument();
    const cvLink = screen.getByRole("link", { name: "Download CV (PDF)" });
    const letterLink = screen.getByRole("link", { name: "Download cover letter (PDF)" });
    expect(cvLink).toHaveAttribute("href", "blob:cv");
    expect(cvLink).toHaveAttribute("download", "CV_Jane_Doe.pdf");
    expect(letterLink).toHaveAttribute("href", "blob:letter");
    expect(letterLink).toHaveAttribute("download", "Lettre_de_motivation_Jane_Doe.pdf");
  });

  it("asks for no letter and shows only the CV when the letter is unticked", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(makeResultBody({ letter: null, letter_pdf_base64: null })),
    );
    const { user } = setup();

    await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
    await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
    await user.click(screen.getByLabelText(/Also write a cover letter/));
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(await screen.findByRole("link", { name: "Download CV (PDF)" })).toBeInTheDocument();
    const sent = fetchMock.mock.calls[0][1] as RequestInit;
    expect((sent.body as FormData).get("include_letter")).toBe("false");
    expect(screen.queryByRole("link", { name: /cover letter/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Subject")).not.toBeInTheDocument();
  });

  it("shows the review screen with the tailored text", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeResultBody()));
    const { user } = setup();

    await fillAndSubmit(user);

    expect(await screen.findByLabelText("Profile")).toHaveValue("Tailored profile.");
    expect(screen.getByRole("button", { name: "Regenerate PDFs" })).toBeEnabled();
  });

  it("warns when a photo was requested but not found", async () => {
    const body = makeResultBody({ photo_used: false, photo_base64: null });
    fetchMock.mockResolvedValue(jsonResponse(body));
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

  it("regenerates the PDFs from the edited text", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse(renderBody));
    const { user } = setup();
    await fillAndSubmit(user);

    await editProfileAndRegenerate(user);

    expect(await screen.findByText("Documents updated from your edits.")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    const sent = JSON.parse(init.body as string) as {
      cv: { profile: string };
      language: string;
      photo_base64: string | null;
    };
    expect(url).toContain("/render");
    expect(sent.cv.profile).toBe("My own profile.");
    expect(sent.language).toBe("fr");
    expect(sent.photo_base64).toBe("iVBORw0KGgo=");
    expect(screen.getByRole("link", { name: "Download CV (PDF)" })).toHaveAttribute(
      "href",
      "blob:cv2",
    );
    expect(screen.getByRole("link", { name: "Download cover letter (PDF)" })).toHaveAttribute(
      "href",
      "blob:letter2",
    );
  });

  it("releases the old files only when the new ones replace them", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse(renderBody));
    const { user } = setup();
    await fillAndSubmit(user);
    await screen.findByRole("link", { name: "Download CV (PDF)" });
    expect(revokeMock).not.toHaveBeenCalled();

    await editProfileAndRegenerate(user);
    await screen.findByText("Documents updated from your edits.");

    expect(revokeMock).toHaveBeenCalledWith("blob:cv");
    expect(revokeMock).toHaveBeenCalledWith("blob:letter");
    expect(revokeMock).not.toHaveBeenCalledWith("blob:cv2");
  });

  it("keeps the previous files and shows the error when regenerating fails", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockResolvedValueOnce(jsonResponse({ detail: "The documents are too long." }, 422));
    const { user } = setup();
    await fillAndSubmit(user);

    await editProfileAndRegenerate(user);

    expect(await screen.findByText("The documents are too long.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download CV (PDF)" })).toHaveAttribute(
      "href",
      "blob:cv",
    );
    expect(revokeMock).not.toHaveBeenCalled();
  });

  it("locks the review button while regenerating", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeResultBody()))
      .mockReturnValueOnce(new Promise(() => {}));
    const { user } = setup();
    await fillAndSubmit(user);

    await editProfileAndRegenerate(user);

    expect(await screen.findByRole("button", { name: "Regenerating…" })).toBeDisabled();
  });

  it("goes back to the form and releases the files on start again", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeResultBody()));
    const { user } = setup();
    await fillAndSubmit(user);

    await user.click(await screen.findByRole("button", { name: "Start again" }));

    expect(screen.queryByRole("link", { name: "Download CV (PDF)" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Profile")).not.toBeInTheDocument();
    expect(revokeMock).toHaveBeenCalledWith("blob:cv");
    expect(revokeMock).toHaveBeenCalledWith("blob:letter");
  });

  it("releases the files when the page is left", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeResultBody()));
    const { user, unmount } = setup();
    await fillAndSubmit(user);
    await screen.findByRole("link", { name: "Download CV (PDF)" });

    unmount();

    expect(revokeMock).toHaveBeenCalledTimes(2);
  });
});
