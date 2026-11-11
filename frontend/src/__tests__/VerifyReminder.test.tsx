import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VerifyReminder } from "@/components/VerifyReminder";

import { jsonResponse, sentBody } from "./helpers/http";

const auth = vi.hoisted(() => ({
  value: { email: "jane@example.com" as string | null, emailVerified: false as boolean | null },
}));
vi.mock("@/components/AuthProvider", () => ({ useAuth: () => auth.value }));

const fetchMock = vi.fn();
const REMINDER = { name: "Confirm your email address" };

beforeEach(() => {
  fetchMock.mockReset();
  auth.value.email = "jane@example.com";
  auth.value.emailVerified = false;
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("VerifyReminder", () => {
  it("reminds an unverified user with their address", () => {
    render(<VerifyReminder />);

    expect(screen.getByRole("region", REMINDER)).toHaveTextContent("jane@example.com");
  });

  it.each([true, null])("stays hidden when the state is %s", (verified) => {
    auth.value.emailVerified = verified;

    render(<VerifyReminder />);

    expect(screen.queryByRole("region", REMINDER)).not.toBeInTheDocument();
  });

  it("sends the link again and shows the answer", async () => {
    const detail = "Check your inbox: we sent you a link to confirm your email address.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 202));
    const user = userEvent.setup();
    render(<VerifyReminder />);

    await user.click(screen.getByRole("button", { name: "Send the link again" }));

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(sentBody(fetchMock, "/auth/resend-verification")).toEqual({
      email: "jane@example.com",
    });
  });
});
