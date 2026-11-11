import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountSummary } from "@/components/AccountSummary";

const fetchMock = vi.fn();

const usageBody = { plan: "plus", used: 2, limit: 15, resets_at: "2026-12-01T00:00:00Z" };
const profileBody = {
  address: "",
  city: "Oujda",
  gender: "m",
  cv_language: "fr",
  is_complete: true,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function serve(usage: object, profile: object) {
  fetchMock.mockImplementation((url: string) => {
    const path = new URL(url).pathname;
    return Promise.resolve(jsonResponse(path === "/me/usage" ? usage : profile));
  });
}

function usageCalls(): number {
  return fetchMock.mock.calls.filter(([url]) => (url as string).endsWith("/me/usage")).length;
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

describe("AccountSummary", () => {
  it("shows the plan, the use of the month and the reset date", async () => {
    serve(usageBody, profileBody);
    render(<AccountSummary />);

    const summary = await screen.findByRole("region", { name: "Your plan" });

    expect(summary).toHaveTextContent("Plus plan");
    expect(summary).toHaveTextContent("2 of 15 applications used this month");
    expect(summary).toHaveTextContent("resets on 1 December 2026");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    expect(screen.queryByRole("link", { name: "Complete my profile" })).not.toBeInTheDocument();
  });

  it("warns when the monthly limit is reached", async () => {
    serve({ ...usageBody, used: 15 }, profileBody);
    render(<AccountSummary />);

    expect(await screen.findByText(/used all the applications of your plan/)).toBeInTheDocument();
  });

  it("asks to complete the profile with a link to it", async () => {
    serve(usageBody, { ...profileBody, city: "", is_complete: false });
    render(<AccountSummary />);

    const link = await screen.findByRole("link", { name: "Complete my profile" });

    expect(link).toHaveAttribute("href", "/profile");
  });

  it("loads again when the version changes", async () => {
    serve(usageBody, profileBody);
    const { rerender } = render(<AccountSummary version={0} />);
    await screen.findByRole("region", { name: "Your plan" });

    serve({ ...usageBody, used: 3 }, profileBody);
    rerender(<AccountSummary version={1} />);

    expect(await screen.findByText(/3 of 15 applications/)).toBeInTheDocument();
    expect(usageCalls()).toBe(2);
  });

  it("says when the plan cannot be loaded", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<AccountSummary />);

    expect(await screen.findByText(/Could not load your plan/)).toBeInTheDocument();
  });
});
