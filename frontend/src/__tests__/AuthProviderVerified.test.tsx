import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { setCsrfToken, setUnauthorizedHandler } from "@/lib/session";

import { jsonResponse } from "./helpers/http";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const fetchMock = vi.fn();

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p data-testid="verified">{String(auth.emailVerified)}</p>
      <button type="button" onClick={() => void auth.refresh()}>
        refresh
      </button>
    </div>
  );
}

function answerMe(verified: boolean) {
  fetchMock.mockResolvedValue(
    jsonResponse({ email: "jane@example.com", csrf_token: "tok", email_verified: verified }),
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  setCsrfToken(null);
  setUnauthorizedHandler(null);
});

describe("AuthProvider and email verification", () => {
  it("knows whether the address is confirmed and refreshes it on demand", async () => {
    answerMe(false);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("verified")).toHaveTextContent("false"));

    answerMe(true);
    await user.click(screen.getByRole("button", { name: "refresh" }));

    await waitFor(() => expect(screen.getByTestId("verified")).toHaveTextContent("true"));
  });
});
