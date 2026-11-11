import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VerifyEmail } from "@/components/VerifyEmail";

import { jsonResponse, sentBody } from "./helpers/http";

const auth = vi.hoisted(() => ({
  value: { status: "anonymous" as "anonymous" | "authenticated", refresh: vi.fn() },
}));
vi.mock("@/components/AuthProvider", () => ({ useAuth: () => auth.value }));

const fetchMock = vi.fn();
const CONFIRM = { name: "Confirm my email address" };

beforeEach(() => {
  fetchMock.mockReset();
  auth.value.refresh.mockReset();
  auth.value.status = "anonymous";
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
  window.history.replaceState(null, "", "/verify-email#token=abc123");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("VerifyEmail", () => {
  it("removes the token from the address bar and waits for a click", () => {
    render(<VerifyEmail />);

    expect(window.location.hash).toBe("");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("confirms the address with the token of the link", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Your email address is verified." }));
    const user = userEvent.setup();
    render(<VerifyEmail />);

    await user.click(screen.getByRole("button", CONFIRM));

    expect(await screen.findByText("Your email address is verified.")).toBeInTheDocument();
    expect(sentBody(fetchMock, "/auth/verify-email")).toEqual({ token: "abc123" });
    expect(auth.value.refresh).not.toHaveBeenCalled();
  });

  it("updates the session of a logged-in user", async () => {
    auth.value.status = "authenticated";
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Your email address is verified." }));
    const user = userEvent.setup();
    render(<VerifyEmail />);

    await user.click(screen.getByRole("button", CONFIRM));

    await screen.findByText("Your email address is verified.");
    expect(auth.value.refresh).toHaveBeenCalledTimes(1);
  });

  it("explains an expired link", async () => {
    const detail = "This link is invalid or has expired. Ask for a new one.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 400));
    const user = userEvent.setup();
    render(<VerifyEmail />);

    await user.click(screen.getByRole("button", CONFIRM));

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });

  it("explains an incomplete link without calling the server", async () => {
    window.history.replaceState(null, "", "/verify-email");
    const user = userEvent.setup();
    render(<VerifyEmail />);

    await user.click(screen.getByRole("button", CONFIRM));

    expect(screen.getByRole("alert")).toHaveTextContent("This link is incomplete.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
