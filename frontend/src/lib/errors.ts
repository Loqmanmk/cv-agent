import { ApiError } from "@/lib/api";

export const GENERIC_ERROR = "Something went wrong. Please try again.";

export type ShownError = { message: string; details: string[] };

export function toShownError(error: unknown): ShownError {
  if (error instanceof ApiError) return { message: error.message, details: error.violations };
  return { message: GENERIC_ERROR, details: [] };
}
