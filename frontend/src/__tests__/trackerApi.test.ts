import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import {
  applicationFileUrl,
  deleteApplication,
  listApplications,
  saveApplication,
  updateApplication,
} from "@/lib/trackerApi";

import { makeCv, makeLetter } from "./fixtures";

const fetchMock = vi.fn();

const summary = {
  id: 7,
  created_at: "2026-11-08T12:00:00+00:00",
  job_title: "Stagiaire DataLab",
  company: "Coface",
  language: "fr",
  source_url: "",
  status: "saved",
  notes: "",
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
});

describe("saveApplication", () => {
  it("posts the edited documents as JSON and returns the saved entry", async () => {
    fetchMock.mockResolvedValue(jsonResponse(summary, 201));

    const saved = await saveApplication({
      jobTitle: "Stagiaire DataLab",
      company: "Coface",
      language: "fr",
      sourceUrl: "",
      cv: makeCv(),
      letter: makeLetter(),
      photoBase64: "abc",
    });

    const [url, init] = lastCall();
    expect(url).toBe("http://api.test/tracker/applications");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      job_title: "Stagiaire DataLab",
      company: "Coface",
      language: "fr",
      source_url: "",
      status: "saved",
      cv: makeCv(),
      letter: makeLetter(),
      photo_base64: "abc",
    });
    expect(saved).toEqual({
      id: 7,
      createdAt: "2026-11-08T12:00:00+00:00",
      jobTitle: "Stagiaire DataLab",
      company: "Coface",
      language: "fr",
      sourceUrl: "",
      status: "saved",
      notes: "",
    });
  });

  it("shows the message of a refused save", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "The job title is required." }, 422));

    await expect(
      saveApplication({
        jobTitle: "",
        company: "",
        language: "fr",
        sourceUrl: "",
        cv: makeCv(),
        letter: makeLetter(),
        photoBase64: null,
      }),
    ).rejects.toMatchObject({ message: "The job title is required.", status: 422 });
  });
});

describe("listApplications", () => {
  it("reads the saved applications", async () => {
    fetchMock.mockResolvedValue(jsonResponse([summary]));

    const items = await listApplications();

    expect(lastCall()[0]).toBe("http://api.test/tracker/applications");
    expect(lastCall()[1].method).toBe("GET");
    expect(items.map((item) => item.jobTitle)).toEqual(["Stagiaire DataLab"]);
  });

  it("accepts an empty list", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    expect(await listApplications()).toEqual([]);
  });

  it("refuses an answer that is not a list of applications", async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ id: 1 }]));

    await expect(listApplications()).rejects.toMatchObject({
      message: "The server sent an unexpected answer.",
    });
  });

  it("refuses an unknown status", async () => {
    fetchMock.mockResolvedValue(jsonResponse([{ ...summary, status: "hired" }]));

    await expect(listApplications()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("updateApplication", () => {
  it("patches only what changed", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...summary, status: "applied" }));

    const updated = await updateApplication(7, { status: "applied" });

    const [url, init] = lastCall();
    expect(url).toBe("http://api.test/tracker/applications/7");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ status: "applied" });
    expect(updated.status).toBe("applied");
  });

  it("reports an application that no longer exists", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Application not found." }, 404));

    await expect(updateApplication(9, { notes: "x" })).rejects.toMatchObject({ status: 404 });
  });
});

describe("deleteApplication", () => {
  it("sends a DELETE and accepts the empty answer", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await deleteApplication(7);

    expect(lastCall()[0]).toBe("http://api.test/tracker/applications/7");
    expect(lastCall()[1].method).toBe("DELETE");
  });
});

describe("applicationFileUrl", () => {
  it("builds the download addresses", () => {
    expect(applicationFileUrl(7, "cv")).toBe("http://api.test/tracker/applications/7/cv.pdf");
    expect(applicationFileUrl(7, "letter")).toBe(
      "http://api.test/tracker/applications/7/letter.pdf",
    );
  });
});
