export type ApplicationRequestValues = {
  cvFile: File;
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

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const GENERIC_ERROR = "Something went wrong. Please try again.";

type ResultBody = {
  job_title: string;
  company: string;
  language: string;
  photo_used: boolean;
  cv_pdf_base64: string;
  letter_pdf_base64: string;
};

type ErrorBody = { detail?: unknown; violations?: unknown };

function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL).replace(/\/+$/, "");
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isResultBody(body: unknown): body is ResultBody {
  if (typeof body !== "object" || body === null) return false;
  const record = body as Record<string, unknown>;
  return (
    typeof record.job_title === "string" &&
    typeof record.company === "string" &&
    typeof record.language === "string" &&
    typeof record.photo_used === "boolean" &&
    typeof record.cv_pdf_base64 === "string" &&
    typeof record.letter_pdf_base64 === "string"
  );
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  try {
    const body: unknown = await response.json();
    return typeof body === "object" && body !== null ? (body as ErrorBody) : {};
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
    case 413:
      return new ApiError("The upload is too large.", 413);
    case 429:
      return new ApiError(retryMessage(response), 429);
    case 422:
    case 502:
    case 503:
      return new ApiError(detail, response.status, violations);
    default:
      return new ApiError(`${GENERIC_ERROR} (code ${response.status})`, response.status);
  }
}

export async function createApplication(
  values: ApplicationRequestValues,
  signal?: AbortSignal,
): Promise<ApplicationResult> {
  const body = new FormData();
  body.append("cv_file", values.cvFile);
  body.append("job_text", values.jobText);
  body.append("include_photo", String(values.includePhoto));

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/applications`, { method: "POST", body, signal });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError("Cannot reach the server. Check that the backend is running.", 0);
  }

  if (!response.ok) throw await toApiError(response);

  const data: unknown = await response.json().catch(() => null);
  if (!isResultBody(data)) {
    throw new ApiError("The server sent an unexpected answer.", response.status);
  }
  return {
    jobTitle: data.job_title,
    company: data.company,
    language: data.language,
    photoUsed: data.photo_used,
    cvPdfBase64: data.cv_pdf_base64,
    letterPdfBase64: data.letter_pdf_base64,
  };
}
