import { ApiError, post } from "@/lib/api";

export type AuthUser = { email: string; csrfToken: string };

type SessionBody = { email: string; csrf_token: string };

const JSON_HEADERS = { "Content-Type": "application/json" };

function isSessionBody(value: unknown): value is SessionBody {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return typeof record.email === "string" && typeof record.csrf_token === "string";
}

function toUser(data: unknown): AuthUser {
  if (!isSessionBody(data)) throw new ApiError("The server sent an unexpected answer.", 200);
  return { email: data.email, csrfToken: data.csrf_token };
}

export async function login(
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<AuthUser> {
  const data = await post(
    "/auth/login",
    { headers: JSON_HEADERS, body: JSON.stringify({ email, password }) },
    signal,
  );
  return toUser(data);
}

export async function fetchMe(signal?: AbortSignal): Promise<AuthUser> {
  return toUser(await post("/auth/me", { method: "GET" }, signal));
}

export async function logout(signal?: AbortSignal): Promise<void> {
  await post("/auth/logout", {}, signal);
}
