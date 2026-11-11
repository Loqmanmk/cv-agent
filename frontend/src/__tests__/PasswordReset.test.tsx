import { render, screen } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ForgotPasswordForm } from "@/components/ForgotPasswordForm";
import { ResetPasswordForm } from "@/components/ResetPasswordForm";

import { jsonResponse, sentBody } from "./helpers/http";

const fetchMock = vi.fn();
const NEW_PASSWORD = "a brand new long passphrase";

async function choose(user: UserEvent, password: string, confirm = password) {
  await user.type(screen.getByLabelText("New password"), password);
  await user.type(screen.getByLabelText("Repeat the password"), confirm);
  await user.click(screen.getByRole("button", { name: "Choose this password" }));
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
  window.history.replaceState(null, "", "/reset-password#token=reset123");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("ForgotPasswordForm", () => {
  it("sends the address and shows the answer of the server", async () => {
    const detail = "If an account exists for this address, we sent a link to reset your password.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 202));
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    await user.type(screen.getByLabelText("Email"), " jane@example.com ");
    await user.click(screen.getByRole("button", { name: "Send me a link" }));

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(sentBody(fetchMock, "/auth/forgot-password")).toEqual({ email: "jane@example.com" });
  });

  it("asks for an address first", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    await user.click(screen.getByRole("button", { name: "Send me a link" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter your email address.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("tells how long to wait when too many emails were asked for", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "x" }, 429, { "Retry-After": "1200" }));
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);

    await user.type(screen.getByLabelText("Email"), "jane@example.com");
    await user.click(screen.getByRole("button", { name: "Send me a link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("about 20 minutes");
  });
});

describe("ResetPasswordForm", () => {
  it("removes the token from the address bar", () => {
    render(<ResetPasswordForm />);

    expect(window.location.hash).toBe("");
  });

  it("changes the password with the token of the link", async () => {
    const detail = "Your password was changed and every device was logged out. Log in again.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }));
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await choose(user, NEW_PASSWORD);

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(sentBody(fetchMock, "/auth/reset-password")).toEqual({
      token: "reset123",
      password: NEW_PASSWORD,
    });
  });

  it("checks the two passwords before sending", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await choose(user, NEW_PASSWORD, "something else entirely");

    expect(screen.getByRole("alert")).toHaveTextContent("The two passwords differ.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the problems found by the server", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: "Choose a stronger password.", problems: ["This password is too common."] },
        422,
      ),
    );
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await choose(user, "password12345");

    expect(await screen.findByRole("alert")).toHaveTextContent("This password is too common.");
  });

  it("explains an expired link and offers a new one", async () => {
    const detail = "This link is invalid or has expired. Ask for a new one.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 400));
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await choose(user, NEW_PASSWORD);

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    expect(screen.getByRole("link", { name: "Ask for a new link" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("explains an incomplete link without calling the server", async () => {
    window.history.replaceState(null, "", "/reset-password");
    const user = userEvent.setup();
    render(<ResetPasswordForm />);

    await choose(user, NEW_PASSWORD);

    expect(screen.getByRole("alert")).toHaveTextContent("This link is incomplete.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
