import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterForm } from "@/components/RegisterForm";

import { jsonResponse, sentBody } from "./helpers/http";

const fetchMock = vi.fn();
const CHECK_INBOX = "Check your inbox: we sent you a link to confirm your email address.";

async function fill(user: UserEvent, password: string, confirm = password) {
  await user.type(screen.getByLabelText("Email"), " jane@example.com ");
  await user.type(screen.getByLabelText("Password"), password);
  await user.type(screen.getByLabelText("Repeat the password"), confirm);
  await user.click(screen.getByRole("button", { name: "Create my account" }));
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

describe("RegisterForm", () => {
  it("checks the form before sending anything", async () => {
    const user = userEvent.setup();
    render(<RegisterForm />);

    await fill(user, "short", "other");

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Use at least 12 characters.");
    expect(alert).toHaveTextContent("The two passwords differ.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates the account and says what to do next", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: CHECK_INBOX }, 202));
    const user = userEvent.setup();
    render(<RegisterForm />);

    await fill(user, "correct horse battery staple");

    expect(await screen.findByText(CHECK_INBOX)).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    expect(sentBody(fetchMock, "/auth/register")).toEqual({
      email: "jane@example.com",
      password: "correct horse battery staple",
    });
  });

  it("shows the problems found by the server", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: "Choose a stronger password.", problems: ["This password is too common."] },
        422,
      ),
    );
    const user = userEvent.setup();
    render(<RegisterForm />);

    await fill(user, "password12345");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Choose a stronger password.");
    expect(alert).toHaveTextContent("This password is too common.");
  });

  it("says when registration is closed", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Registration is closed." }, 403));
    const user = userEvent.setup();
    render(<RegisterForm />);

    await fill(user, "correct horse battery staple");

    expect(await screen.findByRole("alert")).toHaveTextContent("Registration is closed.");
  });
});
