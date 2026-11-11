import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProfileForm } from "@/components/ProfileForm";

const fetchMock = vi.fn();

const profileBody = {
  address: "12 rue Exemple",
  city: "Oujda",
  gender: "m",
  cv_language: "fr",
  is_complete: true,
};

type Handlers = Record<string, () => Response | Promise<Response>>;

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
    return handler
      ? Promise.resolve(handler())
      : Promise.resolve(new Response("", { status: 404 }));
  });
}

function putBody(): unknown {
  const call = fetchMock.mock.calls.find(
    (item) => (item[1] as RequestInit | undefined)?.method === "PUT",
  ) as [string, RequestInit] | undefined;
  return call ? JSON.parse(call[1].body as string) : undefined;
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

describe("ProfileForm", () => {
  it("shows the saved profile", async () => {
    route({ "GET /me/profile": () => jsonResponse(profileBody) });
    render(<ProfileForm />);

    expect(await screen.findByLabelText("City")).toHaveValue("Oujda");
    expect(screen.getByLabelText("Address")).toHaveValue("12 rue Exemple");
    expect(screen.getByLabelText("Grammatical gender in letters")).toHaveValue("m");
    expect(screen.getByLabelText("Language of the CV you upload")).toHaveValue("fr");
  });

  it("saves the profile and confirms it", async () => {
    route({
      "GET /me/profile": () => jsonResponse(profileBody),
      "PUT /me/profile": () =>
        jsonResponse({ ...profileBody, city: "Rabat", gender: "f", cv_language: "en" }),
    });
    const user = userEvent.setup();
    render(<ProfileForm />);

    const city = await screen.findByLabelText("City");
    await user.clear(city);
    await user.type(city, "Rabat");
    await user.selectOptions(screen.getByLabelText("Grammatical gender in letters"), "f");
    await user.selectOptions(screen.getByLabelText("Language of the CV you upload"), "en");
    await user.click(screen.getByRole("button", { name: "Save my profile" }));

    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
    expect(putBody()).toEqual({
      address: "12 rue Exemple",
      city: "Rabat",
      gender: "f",
      cv_language: "en",
    });
  });

  it("asks for a city before saving", async () => {
    route({
      "GET /me/profile": () => jsonResponse({ ...profileBody, city: "", is_complete: false }),
    });
    const user = userEvent.setup();
    render(<ProfileForm />);

    await user.click(await screen.findByRole("button", { name: "Save my profile" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter your city");
    expect(putBody()).toBeUndefined();
  });

  it("shows the message of the server when saving is refused", async () => {
    const detail = "The address is too long (300 characters maximum).";
    route({
      "GET /me/profile": () => jsonResponse(profileBody),
      "PUT /me/profile": () => jsonResponse({ detail }, 422),
    });
    const user = userEvent.setup();
    render(<ProfileForm />);

    await user.click(await screen.findByRole("button", { name: "Save my profile" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });

  it("locks the form while saving", async () => {
    route({
      "GET /me/profile": () => jsonResponse(profileBody),
      "PUT /me/profile": () => new Promise<Response>(() => {}),
    });
    const user = userEvent.setup();
    render(<ProfileForm />);

    await user.click(await screen.findByRole("button", { name: "Save my profile" }));

    expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByLabelText("City")).toBeDisabled();
  });

  it("shows an error when the profile cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ProfileForm />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });
});
