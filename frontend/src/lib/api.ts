import { getCsrfToken, notifyUnauthorized, SAFE_METHODS } from "@/lib/session";
import type { CoverLetter, Cv, MatchReport, MatchScore, MissingSkill } from "@/lib/types";

export type ApplicationRequestValues = {
  /** null: the server uses the CV saved on the account. */
  cvFile: File | null;
  jobText: string;
  includePhoto: boolean;
  /** false: no cover letter, and a faster answer. */
  includeLetter: boolean;
};

export type ApplicationResult = {
  jobTitle: string;
  company: string;
  language: string;
  photoUsed: boolean;
  cvPdfBase64: string;
  /** null when no cover letter was asked for. */
  letterPdfBase64: string | null;
  originalCv: Cv;
  cv: Cv;
  letter: CoverLetter | null;
  photoBase64: string | null;
  report: MatchReport;
};

export type RenderRequestValues = {
  cv: Cv;
  letter: CoverLetter | null;
  language: string;
  photoBase64: string | null;
};

export type RenderedDocuments = {
  cvPdfBase64: string;
  letterPdfBase64: string | null;
};

export type FetchedJobText = {
  text: string;
  truncated: boolean;
  sourceUrl: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly violations: string[];

  constructor(message: string, status: number, violations: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.violations = violations;
  }
}

const DEFAULT_API_URL = "http://localhost:8000";
const GENERIC_ERROR = "Something went wrong. Please try again.";

type ResultBody = {
  job_title: string;
  company: string;
  language: string;
  photo_used: boolean;
  cv_pdf_base64: string;
  letter_pdf_base64: string | null;
  original_cv: Cv;
  cv: Cv;
  letter: CoverLetter | null;
  photo_base64: string | null;
};

type RenderBody = {
  cv_pdf_base64: string;
  letter_pdf_base64: string | null;
};

type JobTextBody = {
  text: string;
  truncated: boolean;
  source_url: string;
};

type ErrorBody = { detail?: unknown; violations?: unknown };

export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL).replace(/\/+$/, "");
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringOrNull(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isResultBody(body: unknown): body is ResultBody {
  if (!isObject(body)) return false;
  return (
    typeof body.job_title === "string" &&
    typeof body.company === "string" &&
    typeof body.language === "string" &&
    typeof body.photo_used === "boolean" &&
    typeof body.cv_pdf_base64 === "string" &&
    isStringOrNull(body.letter_pdf_base64) &&
    isObject(body.original_cv) &&
    isObject(body.cv) &&
    (body.letter === null || isObject(body.letter)) &&
    (body.letter === null) === (body.letter_pdf_base64 === null) &&
    isStringOrNull(body.photo_base64)
  );
}

const NO_SCORE: MatchScore = {
  value: null,
  requiredMatched: 0,
  requiredTotal: 0,
  niceMatched: 0,
  niceTotal: 0,
};

const EMPTY_REPORT: MatchReport = {
  matchedSkills: [],
  missingSkills: [],
  changes: [],
  score: NO_SCORE,
};

function count(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : 0;
}

/** A missing or broken score only hides the score. */
function toScore(value: unknown): MatchScore {
  if (!isObject(value)) return NO_SCORE;
  const score = value.value;
  return {
    value: typeof score === "number" && score >= 0 && score <= 100 ? Math.round(score) : null,
    requiredMatched: count(value.required_matched),
    requiredTotal: count(value.required_total),
    niceMatched: count(value.nice_matched),
    niceTotal: count(value.nice_total),
  };
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function isMissingSkill(value: unknown): value is MissingSkill {
  return isObject(value) && typeof value.name === "string" && typeof value.required === "boolean";
}

/** The report of the server. A missing or broken report only hides the report. */
function toReport(value: unknown): MatchReport {
  if (!isObject(value)) return EMPTY_REPORT;
  const missing = Array.isArray(value.missing_skills) ? value.missing_skills : [];
  return {
    matchedSkills: strings(value.matched_skills),
    missingSkills: missing.filter(isMissingSkill).map((skill) => ({
      name: skill.name,
      required: skill.required,
      group: typeof skill.group === "string" ? skill.group : null,
    })),
    changes: strings(value.changes),
    score: toScore(value.score),
  };
}

function isRenderBody(body: unknown): body is RenderBody {
  return (
    isObject(body) &&
    typeof body.cv_pdf_base64 === "string" &&
    isStringOrNull(body.letter_pdf_base64)
  );
}

function isJobTextBody(body: unknown): body is JobTextBody {
  return (
    isObject(body) &&
    typeof body.text === "string" &&
    typeof body.truncated === "boolean" &&
    typeof body.source_url === "string"
  );
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  try {
    const body: unknown = await response.json();
    if (!isObject(body)) return {};
    // A refused password lists its "problems": they are shown like the other details.
    if (body.violations === undefined && body.problems !== undefined) {
      return { ...body, violations: body.problems };
    }
    return body;
  } catch {
    return {};
  }
}

function retryMessage(response: Response): string {
  const seconds = Number(response.headers.get("Retry-After"));
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "Too many requests. Please try again later.";
  }
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  return `Too many requests. Please try again in about ${minutes} minute${minutes > 1 ? "s" : ""}.`;
}

/** The error the user sees for a status and the body of the server's answer. */
function errorFor(status: number, body: ErrorBody, tooMany: () => string): ApiError {
  const detail = typeof body.detail === "string" ? body.detail : GENERIC_ERROR;
  const violations = Array.isArray(body.violations)
    ? body.violations.filter((item): item is string => typeof item === "string")
    : [];

  switch (status) {
    case 400:
    case 401:
    case 403:
    case 404:
    case 409:
      return new ApiError(detail, status);
    case 413:
      return new ApiError("The upload is too large.", 413);
    case 429:
      return new ApiError(tooMany(), 429);
    case 402:
    case 422:
    case 502:
    case 503:
      return new ApiError(detail, status, violations);
    default:
      return new ApiError(`${GENERIC_ERROR} (code ${status})`, status);
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const body = await readErrorBody(response);
  return errorFor(response.status, body, () => retryMessage(response));
}

function headersFor(init: RequestInit): Record<string, string> | undefined {
  // Our callers only pass plain objects, never a Headers instance or an array.
  const existing = init.headers as Record<string, string> | undefined;
  const token = getCsrfToken();
  const method = (init.method ?? "POST").toUpperCase();
  if (token === null || SAFE_METHODS.includes(method)) return existing;
  return { ...existing, "X-CSRF-Token": token };
}

export async function post(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      ...init,
      headers: headersFor(init),
      credentials: "include",
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError("Cannot reach the server. Check that the backend is running.", 0);
  }
  if (response.status === 401) notifyUnauthorized();
  if (!response.ok) throw await toApiError(response);
  return response.json().catch(() => null);
}

/** The steps of a generation, in order, as the server reports them. */
export const GENERATION_STAGES = [
  "queued",
  "reading",
  "translating",
  "tailoring",
  "rendering",
  "finished",
] as const;
export type GenerationStage = (typeof GENERATION_STAGES)[number];

/** How often the page asks the server where the generation is. */
export const POLL_INTERVAL_MS = 2000;
/** Past this, the page stops waiting: the server gives up a stuck generation by then too. */
export const MAX_WAIT_MS = 15 * 60 * 1000;
/** A few failed checks in a row (a network blip) are retried: the generation goes on. */
const MAX_FAILED_CHECKS = 5;

type JobBody = {
  job_id: string;
  status: "running" | "done" | "failed";
  stage: GenerationStage;
  result: unknown;
  error: unknown;
};

function isJobBody(body: unknown): body is JobBody {
  return (
    isObject(body) &&
    typeof body.job_id === "string" &&
    (body.status === "running" || body.status === "done" || body.status === "failed") &&
    GENERATION_STAGES.includes(body.stage as GenerationStage)
  );
}

function toResult(data: unknown): ApplicationResult {
  if (!isResultBody(data)) {
    throw new ApiError("The server sent an unexpected answer.", 200);
  }
  return {
    jobTitle: data.job_title,
    company: data.company,
    language: data.language,
    photoUsed: data.photo_used,
    cvPdfBase64: data.cv_pdf_base64,
    letterPdfBase64: data.letter_pdf_base64,
    originalCv: data.original_cv,
    cv: data.cv,
    letter: data.letter,
    photoBase64: data.photo_base64,
    report: toReport((data as Record<string, unknown>).report),
  };
}

function jobFailure(error: unknown): ApiError {
  const failure = isObject(error) ? error : {};
  const status = typeof failure.status === "number" ? failure.status : 500;
  const tooMany = () => "Too many requests. Please try again later.";
  return errorFor(status, failure, tooMany);
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", stop);
      resolve();
    }, ms);
    function stop() {
      clearTimeout(timer);
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    }
    signal?.addEventListener("abort", stop, { once: true });
  });
}

async function checkJob(jobId: string, signal?: AbortSignal): Promise<JobBody> {
  const path = `/applications/jobs/${encodeURIComponent(jobId)}`;
  let failed = 0;
  for (;;) {
    try {
      const data = await post(path, { method: "GET" }, signal);
      if (!isJobBody(data)) throw new ApiError("The server sent an unexpected answer.", 200);
      return data;
    } catch (error) {
      // Only an unreachable server is retried; a real answer (expired, signed out) is final.
      const unreachable = error instanceof ApiError && error.status === 0;
      failed += 1;
      if (!unreachable || failed >= MAX_FAILED_CHECKS) throw error;
      await wait(POLL_INTERVAL_MS, signal);
    }
  }
}

/**
 * Starts the generation, then follows it until it ends. The server works in the background,
 * so a slow AI never times out the request; onStage is told each step as it starts.
 */
export async function createApplication(
  values: ApplicationRequestValues,
  signal?: AbortSignal,
  onStage?: (stage: GenerationStage) => void,
  now: () => number = Date.now,
): Promise<ApplicationResult> {
  const body = new FormData();
  if (values.cvFile !== null) body.append("cv_file", values.cvFile);
  body.append("job_text", values.jobText);
  body.append("include_photo", String(values.includePhoto));
  body.append("include_letter", String(values.includeLetter));

  const started = await post("/applications", { body }, signal);
  if (!isJobBody(started)) throw new ApiError("The server sent an unexpected answer.", 200);
  const deadline = now() + MAX_WAIT_MS;
  let job = started;
  for (;;) {
    onStage?.(job.stage);
    if (job.status === "done") return toResult(job.result);
    if (job.status === "failed") throw jobFailure(job.error);
    if (now() > deadline) {
      throw new ApiError(
        "Your application is taking much longer than usual. Please try again later.",
        0,
      );
    }
    await wait(POLL_INTERVAL_MS, signal);
    job = await checkJob(started.job_id, signal);
  }
}

export async function renderDocuments(
  values: RenderRequestValues,
  signal?: AbortSignal,
): Promise<RenderedDocuments> {
  const data = await post(
    "/render",
    {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cv: values.cv,
        letter: values.letter,
        language: values.language,
        photo_base64: values.photoBase64,
      }),
    },
    signal,
  );
  if (!isRenderBody(data)) {
    throw new ApiError("The server sent an unexpected answer.", 200);
  }
  return { cvPdfBase64: data.cv_pdf_base64, letterPdfBase64: data.letter_pdf_base64 };
}

export async function fetchJobText(url: string, signal?: AbortSignal): Promise<FetchedJobText> {
  const data = await post(
    "/job-offers/fetch",
    {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    },
    signal,
  );
  if (!isJobTextBody(data)) {
    throw new ApiError("The server sent an unexpected answer.", 200);
  }
  return { text: data.text, truncated: data.truncated, sourceUrl: data.source_url };
}
