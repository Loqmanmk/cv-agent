"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { verifyEmail } from "@/lib/authApi";
import { toShownError } from "@/lib/errors";
import { useLinkToken } from "@/lib/linkToken";

type State =
  | { phase: "idle" }
  | { phase: "working" }
  | { phase: "done"; message: string }
  | { phase: "error"; message: string };

const INCOMPLETE = "This link is incomplete. Open the latest link from your email.";

export function VerifyEmail() {
  const readToken = useLinkToken();
  const { status, refresh } = useAuth();
  const [state, setState] = useState<State>({ phase: "idle" });

  async function confirm() {
    const token = readToken();
    if (token === null) {
      setState({ phase: "error", message: INCOMPLETE });
      return;
    }
    setState({ phase: "working" });
    try {
      const message = await verifyEmail(token);
      setState({ phase: "done", message });
      if (status === "authenticated") await refresh();
    } catch (caught) {
      setState({ phase: "error", message: toShownError(caught).message });
    }
  }

  if (state.phase === "done") {
    return (
      <div role="status" className="mt-6 rounded bg-green-50 p-3 text-sm text-green-800">
        <p>{state.message}</p>
        <p className="mt-2">
          <Link href="/" className="font-medium underline">
            Continue
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      {state.phase === "error" && (
        <div role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          <p>{state.message}</p>
          <p className="mt-2">
            Log in to ask for a new link from the reminder at the top of the page.{" "}
            <Link href="/login" className="font-medium underline">
              Log in
            </Link>
          </p>
        </div>
      )}
      <button
        type="button"
        onClick={() => void confirm()}
        disabled={state.phase === "working"}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {state.phase === "working" ? "Confirming…" : "Confirm my email address"}
      </button>
    </div>
  );
}
