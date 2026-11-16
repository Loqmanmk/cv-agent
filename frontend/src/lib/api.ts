import { getCsrfToken, notifyUnauthorized, SAFE_METHODS } from "@/lib/session";
import type { CoverLetter, Cv, MatchReport, MissingSkill } from "@/lib/types";

export type ApplicationRequestValues = {
  /** null: the server uses the CV saved on the account. */
  cvFile: File | null;
  jobText: string;
  includePhoto: boolean;
};

export type ApplicationResult = {
  jobTitle: string;
  company: string;
  language: string;
  photoUsed: boolean;
  cvPdfBase64: string;
  letterPdfBase64: string;
  originalCv: Cv;
  cv: Cv;
  letter: CoverLetter;
  photoBase64: string | null;
  report: MatchReport;
};

export type RenderRequestValues = {
  cv: Cv;
  letter: CoverLetter;
  language: string;
  photoBase64: string | null;
};

export type RenderedDocuments = {
  cvPdfBase64: string;
  letterPdfBase64: string;
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
  letter_pdf_base64: string;
  original_cv: Cv;
  cv: Cv;
  letter: CoverLetter;
  photo_base64: string | null;
};

type RenderBody = {
  cv_pdf_base64: string;
  letter_pdf_base64: string;
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

function isResultBody(body: unknown): body is ResultBody {
  if (!isObject(body)) return false;
  return (
    typeof body.job_title === "string" &&
    typeof body.company === "string" &&
    typeof body.language === "string" &&
    typeof body.photo_used === "boolean" &&
    typeof body.cv_pdf_base64 === "string" &&
    typeof body.letter_pdf_base64 === "string" &&
    isObject(body.original_cv) &&
    isObject(body.cv) &&
    isObject(body.letter) &&
    (body.photo_base64 === null || typeof body.photo_base64 === "string")
  );
}

const EMPTY_REPORT: MatchReport = { matchedSkills: [], missingSkills: [], changes: [] };

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
    missingSkills: missing
      .filter(isMissingSkill)
      .map((skill) => ({ name: skill.name, required: skill.required })),
    changes: strings(value.changes),
  };
}

function isRenderBody(body: unknown): body is RenderBody {
  return (
    isObject(body) &&
    typeof body.cv_pdf_base64 === "string" &&
    typeof body.letter_pdf_base64 === "string"
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

async function toApiError(response: Response): Promise<ApiError> {
  const body = await readErrorBody(response);
  const detail = typeof body.detail === "string" ? body.detail : GENERIC_ERROR;
  const violations = Array.isArray(body.violations)
    ? body.violations.filter((item): item is string => typeof item === "string")
    : [];

  switch (response.status) {
    case 400:
    case 401:
    case 403:
      return new ApiError(detail, response.status);
    case 413:
      return new ApiError("The upload is too large.", 413);
    case 429:
      return new ApiError(retryMessage(response), 429);
    case 402:
    case 422:
    case 502:
    case 503:
      return new ApiError(detail, response.status, violations);
    default:
      return new ApiError(`${GENERIC_ERROR} (code ${response.status})`, response.status);
  }
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

export async function createApplication(
  values: ApplicationRequestValues,
  signal?: AbortSignal,
): Promise<ApplicationResult> {
  const body = new FormData();
  if (values.cvFile !== null) body.append("cv_file", values.cvFile);
  body.append("job_text", values.jobText);
  body.append("include_photo", String(values.includePhoto));

  const data = await post("/applications", { body }, signal);
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
