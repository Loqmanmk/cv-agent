import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TrackerList } from "@/components/TrackerList";

const fetchMock = vi.fn();

const summary = {
  id: 7,
  created_at: "2026-11-08T12:00:00+00:00",
  job_title: "Stagiaire DataLab",
  company: "Coface",
  language: "fr",
  source_url: "",
  status: "saved",
  notes: "",
};

type Handlers = Record<string, () => Response>;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function route(handlers: Handlers) {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(url).pathname}`;
    const handler = handlers[key];
    return Promise.resolve(handler ? handler() : new Response("missing", { status: 404 }));
  });
}

function bodyOf(method: string): unknown {
  const call = fetchMock.mock.calls.find(
    (item) => (item[1] as RequestInit | undefined)?.method === method,
  ) as [string, RequestInit] | undefined;
  return call ? JSON.parse(call[1].body as string) : undefined;
}

function calls(method: string): number {
  return fetchMock.mock.calls.filter(
    (item) => (item[1] as RequestInit | undefined)?.method === method,
  ).length;
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

describe("TrackerList", () => {
  it("shows a loading message first", () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    render(<TrackerList />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading your applications");
  });

  it("lists the applications with their date, status and downloads", async () => {
    route({ "GET /tracker/applications": () => jsonResponse([summary]) });
    render(<TrackerList />);

    expect(
      await screen.findByRole("heading", { name: "Stagiaire DataLab — Coface" }),
    ).toBeVisible();
    expect(screen.getByText(/2026-11-08 · FR/)).toBeInTheDocument();
    expect(screen.getByLabelText("Status of Stagiaire DataLab")).toHaveValue("saved");
    expect(screen.getByRole("link", { name: "CV (PDF)" })).toHaveAttribute(
      "href",
      "http://api.test/tracker/applications/7/cv.pdf",
    );
    expect(screen.getByRole("link", { name: "Letter (PDF)" })).toHaveAttribute(
      "href",
      "http://api.test/tracker/applications/7/letter.pdf",
    );
  });

  it("explains what to do when there is nothing yet", async () => {
    route({ "GET /tracker/applications": () => jsonResponse([]) });
    render(<TrackerList />);

    expect(await screen.findByText(/No saved applications yet/)).toBeInTheDocument();
  });

  it("shows an error when the list cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<TrackerList />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("changes the status", async () => {
    route({
      "GET /tracker/applications": () => jsonResponse([summary]),
      "PATCH /tracker/applications/7": () => jsonResponse({ ...summary, status: "applied" }),
    });
    const user = userEvent.setup();
    render(<TrackerList />);

    await user.selectOptions(
      await screen.findByLabelText("Status of Stagiaire DataLab"),
      "applied",
    );

    expect(bodyOf("PATCH")).toEqual({ status: "applied" });
    expect(await screen.findByDisplayValue("Applied")).toBeInTheDocument();
  });

  it("saves the notes, and only when they changed", async () => {
    route({
      "GET /tracker/applications": () => jsonResponse([summary]),
      "PATCH /tracker/applications/7": () => jsonResponse({ ...summary, notes: "Call on Monday" }),
    });
    const user = userEvent.setup();
    render(<TrackerList />);
    const save = await screen.findByRole("button", { name: "Save notes" });
    expect(save).toBeDisabled();

    await user.type(screen.getByLabelText("Notes for Stagiaire DataLab"), "Call on Monday");
    await user.click(save);

    expect(bodyOf("PATCH")).toEqual({ notes: "Call on Monday" });
    expect(await screen.findByRole("button", { name: "Save notes" })).toBeDisabled();
  });

  it("asks for a confirmation before deleting, and can be cancelled", async () => {
    route({
      "GET /tracker/applications": () => jsonResponse([summary]),
      "DELETE /tracker/applications/7": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    render(<TrackerList />);

    await user.click(await screen.findByRole("button", { name: "Delete Stagiaire DataLab" }));
    expect(screen.getByText("Delete this application?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByText("Delete this application?")).not.toBeInTheDocument();
    expect(calls("DELETE")).toBe(0);
  });

  it("deletes an application after the confirmation", async () => {
    route({
      "GET /tracker/applications": () => jsonResponse([summary]),
      "DELETE /tracker/applications/7": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    render(<TrackerList />);

    await user.click(await screen.findByRole("button", { name: "Delete Stagiaire DataLab" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByText(/No saved applications yet/)).toBeInTheDocument();
    expect(calls("DELETE")).toBe(1);
  });

  it("shows the error of a failed change and keeps the application", async () => {
    route({
      "GET /tracker/applications": () => jsonResponse([summary]),
      "PATCH /tracker/applications/7": () =>
        jsonResponse({ detail: "The notes are too long." }, 422),
    });
    const user = userEvent.setup();
    render(<TrackerList />);

    await user.type(await screen.findByLabelText("Notes for Stagiaire DataLab"), "x");
    await user.click(screen.getByRole("button", { name: "Save notes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The notes are too long.");
    expect(screen.getByRole("heading", { name: "Stagiaire DataLab — Coface" })).toBeVisible();
  });

  it("links to the job offer only when there is a link", async () => {
    route({
      "GET /tracker/applications": () =>
        jsonResponse([{ ...summary, source_url: "https://example.com/job" }]),
    });
    render(<TrackerList />);

    const link = await screen.findByRole("link", { name: "Job offer" });

    expect(link).toHaveAttribute("href", "https://example.com/job");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
