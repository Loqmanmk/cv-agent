import { ApiError, apiBaseUrl, post } from "@/lib/api";
import { isStatus, type ApplicationStatus, type TrackedApplication } from "@/lib/tracker";
import type { CoverLetter, Cv } from "@/lib/types";

export type SaveApplicationValues = {
  jobTitle: string;
  company: string;
  language: string;
  sourceUrl: string;
  cv: Cv;
  letter: CoverLetter | null;
  photoBase64: string | null;
};

type SummaryBody = {
  id: number;
  created_at: string;
  job_title: string;
  company: string;
  language: string;
  source_url: string;
  status: ApplicationStatus;
  notes: string;
  has_letter?: boolean;
};

const JSON_HEADERS = { "Content-Type": "application/json" };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSummaryBody(value: unknown): value is SummaryBody {
  return (
    isObject(value) &&
    typeof value.id === "number" &&
    typeof value.created_at === "string" &&
    typeof value.job_title === "string" &&
    typeof value.company === "string" &&
    typeof value.language === "string" &&
    typeof value.source_url === "string" &&
    typeof value.status === "string" &&
    isStatus(value.status) &&
    typeof value.notes === "string" &&
    (value.has_letter === undefined || typeof value.has_letter === "boolean")
  );
}

function toTracked(body: SummaryBody): TrackedApplication {
  return {
    id: body.id,
    createdAt: body.created_at,
    jobTitle: body.job_title,
    company: body.company,
    language: body.language,
    sourceUrl: body.source_url,
    status: body.status,
    notes: body.notes,
    hasLetter: body.has_letter ?? true,
  };
}

function unexpected(): ApiError {
  return new ApiError("The server sent an unexpected answer.", 200);
}

export async function saveApplication(
  values: SaveApplicationValues,
  signal?: AbortSignal,
): Promise<TrackedApplication> {
  const data = await post(
    "/tracker/applications",
    {
      headers: JSON_HEADERS,
      body: JSON.stringify({
        job_title: values.jobTitle,
        company: values.company,
        language: values.language,
        source_url: values.sourceUrl,
        status: "saved",
        cv: values.cv,
        letter: values.letter,
        photo_base64: values.photoBase64,
      }),
    },
    signal,
  );
  if (!isSummaryBody(data)) throw unexpected();
  return toTracked(data);
}

export async function listApplications(signal?: AbortSignal): Promise<TrackedApplication[]> {
  const data = await post("/tracker/applications", { method: "GET" }, signal);
  if (!Array.isArray(data) || !data.every(isSummaryBody)) throw unexpected();
  return data.map(toTracked);
}

export async function updateApplication(
  id: number,
  changes: { status?: ApplicationStatus; notes?: string },
  signal?: AbortSignal,
): Promise<TrackedApplication> {
  const data = await post(
    `/tracker/applications/${id}`,
    { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes) },
    signal,
  );
  if (!isSummaryBody(data)) throw unexpected();
  return toTracked(data);
}

export async function deleteApplication(id: number, signal?: AbortSignal): Promise<void> {
  await post(`/tracker/applications/${id}`, { method: "DELETE" }, signal);
}

export function applicationFileUrl(id: number, kind: "cv" | "letter"): string {
  return `${apiBaseUrl()}/tracker/applications/${id}/${kind}.pdf`;
}
