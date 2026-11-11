"use client";

import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { resendVerification } from "@/lib/authApi";
import { toShownError } from "@/lib/errors";

type State =
  | { phase: "idle" }
  | { phase: "sending" }
  | { phase: "sent"; message: string }
  | { phase: "error"; message: string };

export function VerifyReminder() {
  const { email, emailVerified } = useAuth();
  const [state, setState] = useState<State>({ phase: "idle" });

  if (emailVerified !== false || email === null) return null;
  const address = email;

  async function resend() {
    setState({ phase: "sending" });
    try {
      setState({ phase: "sent", message: await resendVerification(address) });
    } catch (caught) {
      setState({ phase: "error", message: toShownError(caught).message });
    }
  }

  return (
    <section
      aria-label="Confirm your email address"
      className="border-b border-amber-200 bg-amber-50"
    >
      <div className="mx-auto max-w-3xl px-8 py-3 text-sm text-amber-900">
        <p>
          Confirm your email address to create applications. We sent a link to{" "}
          <strong>{address}</strong>.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void resend()}
            disabled={state.phase === "sending"}
            className="underline disabled:opacity-50"
          >
            {state.phase === "sending" ? "Sending…" : "Send the link again"}
          </button>
          {(state.phase === "sent" || state.phase === "error") && (
            <span role="status">{state.message}</span>
          )}
        </div>
      </div>
    </section>
  );
}
