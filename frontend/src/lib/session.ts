export const SAFE_METHODS: readonly string[] = ["GET", "HEAD", "OPTIONS"];

// The CSRF token lives in memory only: never in localStorage, never in a cookie.
// After a page reload it is fetched again from /auth/me.
let csrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.();
}
