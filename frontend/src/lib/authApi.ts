import { ApiError, post } from "@/lib/api";

export type AuthUser = { email: string; csrfToken: string; emailVerified: boolean };

type SessionBody = { email: string; csrf_token: string; email_verified: boolean };

const JSON_HEADERS = { "Content-Type": "application/json" };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSessionBody(value: unknown): value is SessionBody {
  return (
    isObject(value) &&
    typeof value.email === "string" &&
    typeof value.csrf_token === "string" &&
    typeof value.email_verified === "boolean"
  );
}

function unexpected(): ApiError {
  return new ApiError("The server sent an unexpected answer.", 200);
}

function toUser(data: unknown): AuthUser {
  if (!isSessionBody(data)) throw unexpected();
  return { email: data.email, csrfToken: data.csrf_token, emailVerified: data.email_verified };
}

function toMessage(data: unknown): string {
  if (isObject(data) && typeof data.detail === "string") return data.detail;
  throw unexpected();
}

function postJson(path: string, payload: object, signal?: AbortSignal): Promise<unknown> {
  return post(path, { headers: JSON_HEADERS, body: JSON.stringify(payload) }, signal);
}

export async function login(
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<AuthUser> {
  return toUser(await postJson("/auth/login", { email, password }, signal));
}

export async function fetchMe(signal?: AbortSignal): Promise<AuthUser> {
  return toUser(await post("/auth/me", { method: "GET" }, signal));
}

export async function logout(signal?: AbortSignal): Promise<void> {
  await post("/auth/logout", {}, signal);
}

export async function register(
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<string> {
  return toMessage(await postJson("/auth/register", { email, password }, signal));
}

export async function resendVerification(email: string, signal?: AbortSignal): Promise<string> {
  return toMessage(await postJson("/auth/resend-verification", { email }, signal));
}

export async function verifyEmail(token: string, signal?: AbortSignal): Promise<string> {
  return toMessage(await postJson("/auth/verify-email", { token }, signal));
}

export async function forgotPassword(email: string, signal?: AbortSignal): Promise<string> {
  return toMessage(await postJson("/auth/forgot-password", { email }, signal));
}

export async function resetPassword(
  token: string,
  password: string,
  signal?: AbortSignal,
): Promise<string> {
  return toMessage(await postJson("/auth/reset-password", { token, password }, signal));
}
