import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchProfile, fetchUsage, saveProfile } from "@/lib/accountApi";
import { createApplication } from "@/lib/api";
import { setCsrfToken } from "@/lib/session";

const fetchMock = vi.fn();

const profileBody = {
  address: "12 rue Exemple",
  city: "Oujda",
  gender: "f",
  cv_language: "de",
  is_complete: true,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lastCall(): [string, RequestInit] {
  return fetchMock.mock.calls.at(-1) as [string, RequestInit];
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
});

describe("profile", () => {
  it("reads the profile with the cookies", async () => {
    fetchMock.mockResolvedValue(jsonResponse(profileBody));

    const profile = await fetchProfile();

    expect(lastCall()[0]).toBe("http://api.test/me/profile");
    expect(lastCall()[1].method).toBe("GET");
    expect(lastCall()[1].credentials).toBe("include");
    expect(profile).toEqual({
      address: "12 rue Exemple",
      city: "Oujda",
      gender: "f",
      cvLanguage: "de",
      isComplete: true,
    });
  });

  it("saves the profile with PUT, the CSRF token and a JSON body", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(jsonResponse(profileBody));

    await saveProfile({ address: "12 rue Exemple", city: "Oujda", gender: "f", cvLanguage: "de" });

    const [url, init] = lastCall();
    expect(url).toBe("http://api.test/me/profile");
    expect(init.method).toBe("PUT");
    expect(init.headers).toEqual({ "Content-Type": "application/json", "X-CSRF-Token": "tok" });
    expect(JSON.parse(init.body as string)).toEqual({
      address: "12 rue Exemple",
      city: "Oujda",
      gender: "f",
      cv_language: "de",
    });
  });

  it("shows the message of a refused profile", async () => {
    const detail = "The city is too long (100 characters maximum).";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 422));

    await expect(
      saveProfile({ address: "", city: "x", gender: "m", cvLanguage: "fr" }),
    ).rejects.toMatchObject({ message: detail, status: 422 });
  });

  it("refuses an answer with unknown values", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...profileBody, gender: "x" }));

    await expect(fetchProfile()).rejects.toMatchObject({
      message: "The server sent an unexpected answer.",
    });
  });
});

describe("usage", () => {
  it("reads the plan and the use of the month", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ plan: "free", used: 1, limit: 3, resets_at: "2026-12-01T00:00:00Z" }),
    );

    expect(await fetchUsage()).toEqual({
      plan: "free",
      used: 1,
      limit: 3,
      resetsAt: "2026-12-01T00:00:00Z",
    });
    expect(lastCall()[0]).toBe("http://api.test/me/usage");
  });

  it("refuses an unknown plan", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ plan: "gold", used: 1, limit: 3, resets_at: "2026-12-01T00:00:00Z" }),
    );

    await expect(fetchUsage()).rejects.toMatchObject({
      message: "The server sent an unexpected answer.",
    });
  });

  it("shows the message of a reached monthly limit", async () => {
    const detail = "Monthly limit reached: 3 applications on your plan.";
    fetchMock.mockResolvedValue(
      jsonResponse({ detail, limit: 3, resets_at: "2026-12-01T00:00:00+00:00" }, 402),
    );

    await expect(
      createApplication({
        cvFile: new File(["x"], "cv.docx"),
        jobText: "Acme seeks an intern.",
        includePhoto: true,
      }),
    ).rejects.toMatchObject({ message: detail, status: 402 });
  });
});
