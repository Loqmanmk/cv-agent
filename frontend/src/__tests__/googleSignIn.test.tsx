import { render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GoogleButton } from "@/components/GoogleButton";
import { googleErrorMessage, useGoogleError } from "@/lib/googleSignIn";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllEnvs();
  window.history.replaceState(null, "", "/");
});

describe("GoogleButton", () => {
  it("is a plain link to the backend, which sends the browser on to Google", () => {
    render(<GoogleButton />);

    expect(screen.getByRole("link", { name: "Continue with Google" })).toHaveAttribute(
      "href",
      "http://api.test/auth/google/start",
    );
  });
});

describe("googleErrorMessage", () => {
  it("gives the fixed message of a known code", () => {
    expect(googleErrorMessage("?error=google_cancelled")).toMatch(/cancelled/);
    expect(googleErrorMessage("?error=registration_closed")).toMatch(/cannot be created/);
  });

  it("shows nothing for an unknown code or a page without one", () => {
    expect(googleErrorMessage("?error=Your+account+was+hacked")).toBeNull();
    expect(googleErrorMessage("")).toBeNull();
  });
});

describe("useGoogleError", () => {
  it("reads the message once and removes only the code from the address bar", () => {
    window.history.replaceState(null, "", "/login?error=google_busy&next=1#top");

    const { result } = renderHook(() => useGoogleError());

    expect(result.current).toMatch(/Too many sign-in attempts/);
    expect(window.location.pathname).toBe("/login");
    expect(window.location.search).toBe("?next=1");
    expect(window.location.hash).toBe("#top");
  });
});
