import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { deleteSavedCv, fetchSavedCv, uploadSavedCv } from "@/lib/savedCvApi";
import { setCsrfToken } from "@/lib/session";

import { jsonResponse } from "./helpers/http";

const fetchMock = vi.fn();
const body = { filename: "cv.pdf", size: 1200, uploaded_at: "2026-11-10T12:00:00Z" };

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

describe("saved CV", () => {
  it("reads the saved CV with the cookies", async () => {
    fetchMock.mockResolvedValue(jsonResponse(body));

    const saved = await fetchSavedCv();

    expect(lastCall()[0]).toBe("http://api.test/me/cv");
    expect(lastCall()[1].method).toBe("GET");
    expect(lastCall()[1].credentials).toBe("include");
    expect(saved).toEqual({ filename: "cv.pdf", size: 1200, uploadedAt: "2026-11-10T12:00:00Z" });
  });

  it("says when there is no saved CV", async () => {
    fetchMock.mockResolvedValue(jsonResponse(null));

    expect(await fetchSavedCv()).toBeNull();
  });

  it("refuses an unexpected answer", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ filename: 3 }));

    await expect(fetchSavedCv()).rejects.toBeInstanceOf(ApiError);
  });

  it("uploads the file with PUT and the CSRF token", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(jsonResponse(body));
    const file = new File(["content"], "cv.pdf");

    await uploadSavedCv(file);

    const [url, init] = lastCall();
    expect(url).toBe("http://api.test/me/cv");
    expect(init.method).toBe("PUT");
    expect(init.headers).toEqual({ "X-CSRF-Token": "tok" });
    expect((init.body as FormData).get("cv_file")).toBe(file);
  });

  it("deletes the saved CV with the CSRF token", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await deleteSavedCv();

    expect(lastCall()[1].method).toBe("DELETE");
    expect(lastCall()[1].headers).toEqual({ "X-CSRF-Token": "tok" });
  });

  it("shows why a file was refused", async () => {
    const detail = "The file content does not match its extension.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 422));

    await expect(uploadSavedCv(new File(["x"], "cv.pdf"))).rejects.toThrow(detail);
  });
});
