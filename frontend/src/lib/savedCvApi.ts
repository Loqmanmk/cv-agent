import { ApiError, post } from "@/lib/api";

export type SavedCv = { filename: string; size: number; uploadedAt: string };

type SavedCvBody = { filename: string; size: number; uploaded_at: string };

function isSavedCvBody(value: unknown): value is SavedCvBody {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  return (
    typeof body.filename === "string" &&
    Number.isInteger(body.size) &&
    typeof body.uploaded_at === "string"
  );
}

function toSavedCv(body: SavedCvBody): SavedCv {
  return { filename: body.filename, size: body.size, uploadedAt: body.uploaded_at };
}

function unexpected(): ApiError {
  return new ApiError("The server sent an unexpected answer.", 200);
}

/** The CV kept on the account, or null when the user has not saved one yet. */
export async function fetchSavedCv(signal?: AbortSignal): Promise<SavedCv | null> {
  const data = await post("/me/cv", { method: "GET" }, signal);
  if (data === null) return null;
  if (!isSavedCvBody(data)) throw unexpected();
  return toSavedCv(data);
}

/** Keeps this file as the saved CV, replacing the previous one. */
export async function uploadSavedCv(file: File, signal?: AbortSignal): Promise<SavedCv> {
  const body = new FormData();
  body.append("cv_file", file);
  const data = await post("/me/cv", { method: "PUT", body }, signal);
  if (!isSavedCvBody(data)) throw unexpected();
  return toSavedCv(data);
}

export async function deleteSavedCv(signal?: AbortSignal): Promise<void> {
  await post("/me/cv", { method: "DELETE" }, signal);
}
