"use client";

import { useEffect, useState } from "react";

import { apiBaseUrl } from "@/lib/api";

const ERROR_PARAM = "error";

// The backend sends only a short code. Each code has its own fixed text here, so a crafted link
// can never make the website show a message chosen by someone else. Unknown codes show nothing.
const MESSAGES = new Map<string, string>([
  ["google_failed", "Signing in with Google failed. Please try again."],
  ["google_cancelled", "Google sign-in was cancelled. You can try again or use your email."],
  [
    "google_unavailable",
    "Google sign-in is not available right now. Log in with your email and password.",
  ],
  ["google_busy", "Too many sign-in attempts. Please wait a few minutes and try again."],
  [
    "google_unverified",
    "Your Google email address is not verified yet. Verify it with Google, then try again.",
  ],
  ["account_unavailable", "This account cannot be used."],
  [
    "registration_closed",
    "New accounts cannot be created at the moment. If you already have one, log in with it.",
  ],
]);

/** The backend address that starts the sign-in. It is a normal link, not a fetch call. */
export function googleStartUrl(): string {
  return `${apiBaseUrl()}/auth/google/start`;
}

export function googleErrorMessage(search: string): string | null {
  const code = new URLSearchParams(search).get(ERROR_PARAM);
  return code === null ? null : (MESSAGES.get(code) ?? null);
}

/** The message of a failed Google sign-in, read once; the code is then removed from the URL. */
export function useGoogleError(): string | null {
  const [message] = useState(() =>
    typeof window === "undefined" ? null : googleErrorMessage(window.location.search),
  );

  useEffect(() => {
    const url = new URL(window.location.href);
    if (!url.searchParams.has(ERROR_PARAM)) return;
    url.searchParams.delete(ERROR_PARAM);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  return message;
}
