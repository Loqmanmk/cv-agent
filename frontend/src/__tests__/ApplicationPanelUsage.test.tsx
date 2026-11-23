import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationPanel } from "@/components/ApplicationPanel";

import { makeDoneJob, makeResultBody } from "./fixtures";

const fetchMock = vi.fn();

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

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
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
});

describe("ApplicationPanel and the plan", () => {
  it("tells the page that an application was created", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody())));
    const onCreated = vi.fn();
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel onCreated={onCreated} />);

    await fillAndSubmit(user);
    await screen.findByRole("link", { name: "Download CV (PDF)" });

    expect(onCreated).toHaveBeenCalledTimes(1);
  });

  it("explains a reached limit and does not count it as created", async () => {
    const detail = "Monthly limit reached: 3 applications on your plan.";
    fetchMock.mockResolvedValue(jsonResponse({ detail, limit: 3 }, 402));
    const onCreated = vi.fn();
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel onCreated={onCreated} />);

    await fillAndSubmit(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(detail);
    expect(alert).toHaveTextContent("monthly applications reset");
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("links to the profile when it is incomplete", async () => {
    const detail = "Complete your profile (at least your city) before creating an application.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 422));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("link", { name: "Open my profile" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });
});
