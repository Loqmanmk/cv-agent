import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { login } from "@/lib/authApi";
import { setCsrfToken, setUnauthorizedHandler } from "@/lib/session";
import { deleteApplication, listApplications, updateApplication } from "@/lib/trackerApi";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lastInit(): RequestInit {
  return (fetchMock.mock.calls.at(-1) as [string, RequestInit])[1];
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

describe("requests with a session", () => {
  it("always send the cookies", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await listApplications();

    expect(lastInit().credentials).toBe("include");
  });

  it("do not send the CSRF token on a read", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(jsonResponse([]));

    await listApplications();

    expect(lastInit().headers).toBeUndefined();
  });

  it("send the CSRF token on a change", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await deleteApplication(7);

    expect(lastInit().headers).toEqual({ "X-CSRF-Token": "tok" });
  });

  it("keep the other headers when the CSRF token is added", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(
      jsonResponse({
        id: 7,
        created_at: "2026-11-08T12:00:00+00:00",
        job_title: "x",
        company: "y",
        language: "fr",
        source_url: "",
        status: "applied",
        notes: "",
      }),
    );

    await updateApplication(7, { status: "applied" });

    expect(lastInit().headers).toEqual({
      "Content-Type": "application/json",
      "X-CSRF-Token": "tok",
    });
  });

  it("send no CSRF header when there is no token yet", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await deleteApplication(7);

    expect(lastInit().headers).toBeUndefined();
  });
});

describe("answers that need a login", () => {
  it("tell the session handler and keep the message of the server", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Please log in." }, 401));

    await expect(listApplications()).rejects.toMatchObject({
      message: "Please log in.",
      status: 401,
    });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("show the exact message of a refused login", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Invalid email or password." }, 401));

    const failure = await login("jane@example.com", "pw").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).message).toBe("Invalid email or password.");
  });

  it("show the message of a forbidden request", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Invalid CSRF token." }, 403));

    await expect(deleteApplication(7)).rejects.toMatchObject({
      message: "Invalid CSRF token.",
      status: 403,
    });
  });

  it("tell how long to wait when logins are limited", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "x" }), {
        status: 429,
        headers: { "Content-Type": "application/json", "Retry-After": "600" },
      }),
    );

    await expect(login("jane@example.com", "pw")).rejects.toMatchObject({
      message: "Too many requests. Please try again in about 10 minutes.",
    });
  });
});
