import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createApplication,
  renderDocuments,
  type ApplicationRequestValues,
  type RenderRequestValues,
} from "@/lib/api";

import { makeCv, makeLetter, makeDoneJob, makeResultBody } from "./fixtures";

const fetchMock = vi.fn();

const values: ApplicationRequestValues = {
  cvFile: new File(["content"], "cv.docx"),
  jobText: "Acme seeks an intern.",
  includePhoto: true,
  includeLetter: true,
};

const renderValues: RenderRequestValues = {
  cv: makeCv(),
  letter: makeLetter(),
  language: "fr",
  photoBase64: "abc",
};

const renderBody = { cv_pdf_base64: "Y3Y=", letter_pdf_base64: "bGV0dGVy" };

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

async function failureOf(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error("Expected an ApiError");
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

describe("createApplication", () => {
  it("posts the CV, the job offer and the photo choice as a form", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody())));

    await createApplication(values);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = init.body as FormData;
    expect(url).toBe("http://api.test/applications");
    expect(init.method).toBe("POST");
    expect((body.get("cv_file") as File).name).toBe("cv.docx");
    expect(body.get("job_text")).toBe("Acme seeks an intern.");
    expect(body.get("include_photo")).toBe("true");
  });

  it("ignores a trailing slash in the API address", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody())));

    await createApplication(values);

    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("http://api.test/applications");
  });

  it("returns the result with camelCase names and the editable data", async () => {
    const body = makeResultBody();
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(body)));

    expect(await createApplication(values)).toEqual({
      jobTitle: "Stagiaire DataLab",
      company: "Coface",
      language: "fr",
      photoUsed: true,
      cvPdfBase64: body.cv_pdf_base64,
      letterPdfBase64: body.letter_pdf_base64,
      originalCv: body.original_cv,
      cv: body.cv,
      letter: body.letter,
      photoBase64: body.photo_base64,
      report: {
        matchedSkills: ["Python"],
        missingSkills: [
          { name: "Django", required: true, group: "Back-end" },
          { name: "Kubernetes", required: true, group: null },
          { name: "Terraform", required: false, group: null },
        ],
        changes: ["Profile rewritten with the words of the offer."],
        score: { value: 29, requiredMatched: 1, requiredTotal: 3, niceMatched: 0, niceTotal: 1 },
      },
    });
  });

  it("keeps only the valid parts of the match report", async () => {
    const report = {
      matched_skills: ["Python", 3],
      missing_skills: [{ name: "Go", required: true }, { name: "Rust" }, "Kotlin"],
      changes: "not a list",
    };
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody({ report }))));

    expect((await createApplication(values)).report).toEqual({
      matchedSkills: ["Python"],
      missingSkills: [{ name: "Go", required: true, group: null }],
      changes: [],
      score: { value: null, requiredMatched: 0, requiredTotal: 0, niceMatched: 0, niceTotal: 0 },
    });
  });

  it("shows no report when the server sends none", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody({ report: undefined }))));

    expect((await createApplication(values)).report).toEqual({
      matchedSkills: [],
      missingSkills: [],
      changes: [],
      score: { value: null, requiredMatched: 0, requiredTotal: 0, niceMatched: 0, niceTotal: 0 },
    });
  });

  it("refuses a score outside 0 to 100 and broken counts", async () => {
    const report = {
      matched_skills: [],
      missing_skills: [],
      changes: [],
      score: { value: 140, required_matched: -1, required_total: "3", nice_matched: 1.5 },
    };
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(makeResultBody({ report }))));

    expect((await createApplication(values)).report.score).toEqual({
      value: null,
      requiredMatched: 0,
      requiredTotal: 0,
      niceMatched: 0,
      niceTotal: 0,
    });
  });

  it("accepts an answer without a photo", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(makeDoneJob(makeResultBody({ photo_used: false, photo_base64: null }))),
    );

    expect((await createApplication(values)).photoBase64).toBeNull();
  });

  it("shows the message of a 422 answer", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "The CV file is empty." }, 422));

    const error = await failureOf(createApplication(values));

    expect(error.message).toBe("The CV file is empty.");
    expect(error.status).toBe(422);
  });

  it("uses a generic message when the detail is not text", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: [{ msg: "field required" }] }, 422));

    const error = await failureOf(createApplication(values));

    expect(error.message).toBe("Something went wrong. Please try again.");
  });

  it("tells how long to wait after a 429 answer", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "x" }, 429, { "Retry-After": "120" }));

    const error = await failureOf(createApplication(values));

    expect(error.message).toBe("Too many requests. Please try again in about 2 minutes.");
  });

  it("explains an oversized upload", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "x" }, 413));

    expect((await failureOf(createApplication(values))).message).toBe("The upload is too large.");
  });

  it("returns the busy message of a 503 answer", async () => {
    const detail = "The AI service is busy or out of quota. Please try again later.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 503));

    expect((await failureOf(createApplication(values))).message).toBe(detail);
  });

  it("keeps the violations of a rejected AI result", async () => {
    const body = { detail: "Not faithful.", violations: ["skill 'Kubernetes' is not in the CV"] };
    fetchMock.mockResolvedValue(jsonResponse(body, 502));

    const error = await failureOf(createApplication(values));

    expect(error.violations).toEqual(["skill 'Kubernetes' is not in the CV"]);
  });

  it("includes the status code for other errors", async () => {
    fetchMock.mockResolvedValue(new Response("oops", { status: 500 }));

    expect((await failureOf(createApplication(values))).message).toContain("code 500");
  });

  it("explains that the server cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await failureOf(createApplication(values));

    expect(error.message).toContain("Cannot reach the server");
  });

  it("refuses an answer with an unexpected shape", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ job_title: "x" }));

    const error = await failureOf(createApplication(values));

    expect(error.message).toBe("The server sent an unexpected answer.");
  });

  it("refuses an answer without the editable data", async () => {
    const withoutCv: Record<string, unknown> = { ...makeResultBody() };
    delete withoutCv.cv;
    fetchMock.mockResolvedValue(jsonResponse(makeDoneJob(withoutCv)));

    const error = await failureOf(createApplication(values));

    expect(error.message).toBe("The server sent an unexpected answer.");
  });

  it("lets a cancelled request propagate as it is", async () => {
    const abort = new DOMException("aborted", "AbortError");
    fetchMock.mockRejectedValue(abort);

    await expect(createApplication(values)).rejects.toBe(abort);
  });
});

describe("renderDocuments", () => {
  it("posts the edited documents as JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse(renderBody));

    await renderDocuments(renderValues);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/render");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body as string)).toEqual({
      cv: makeCv(),
      letter: makeLetter(),
      language: "fr",
      photo_base64: "abc",
    });
  });

  it("sends null when there is no photo", async () => {
    fetchMock.mockResolvedValue(jsonResponse(renderBody));

    await renderDocuments({ ...renderValues, photoBase64: null });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((JSON.parse(init.body as string) as { photo_base64: unknown }).photo_base64).toBeNull();
  });

  it("returns the new PDFs", async () => {
    fetchMock.mockResolvedValue(jsonResponse(renderBody));

    expect(await renderDocuments(renderValues)).toEqual({
      cvPdfBase64: "Y3Y=",
      letterPdfBase64: "bGV0dGVy",
    });
  });

  it("shows the message of a 422 answer", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "The documents are too long." }, 422));

    const error = await failureOf(renderDocuments(renderValues));

    expect(error.message).toBe("The documents are too long.");
  });

  it("tells how long to wait after a 429 answer", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "x" }, 429, { "Retry-After": "30" }));

    const error = await failureOf(renderDocuments(renderValues));

    expect(error.message).toBe("Too many requests. Please try again in about 1 minute.");
  });

  it("explains that the server cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    expect((await failureOf(renderDocuments(renderValues))).message).toContain("Cannot reach");
  });

  it("refuses an answer with an unexpected shape", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ cv_pdf_base64: "x" }));

    const error = await failureOf(renderDocuments(renderValues));

    expect(error.message).toBe("The server sent an unexpected answer.");
  });
});
