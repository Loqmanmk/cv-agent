"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PLAN_LABELS, fetchProfile, fetchUsage, type Profile, type Usage } from "@/lib/accountApi";
import { ApiError } from "@/lib/api";
import { formatResetDate } from "@/lib/format";

type State =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; usage: Usage; profile: Profile };

const GENERIC_ERROR = "Something went wrong. Please try again.";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function percentUsed(usage: Usage): number {
  if (usage.limit <= 0) return 100;
  return Math.min(100, Math.round((usage.used / usage.limit) * 100));
}

type Props = { version?: number };

export function AccountSummary({ version = 0 }: Props) {
  const [state, setState] = useState<State>({ phase: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchUsage(controller.signal), fetchProfile(controller.signal)])
      .then(([usage, profile]) => setState({ phase: "ready", usage, profile }))
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        const message = error instanceof ApiError ? error.message : GENERIC_ERROR;
        setState({ phase: "error", message });
      });
    return () => controller.abort();
  }, [version]);

  if (state.phase === "loading") {
    return (
      <p role="status" className="mt-6 text-sm text-gray-500">
        Loading your plan…
      </p>
    );
  }
  if (state.phase === "error") {
    return <p className="mt-6 text-sm text-gray-500">Could not load your plan: {state.message}</p>;
  }

  const { usage, profile } = state;
  const reached = usage.used >= usage.limit;

  return (
    <section
      aria-label="Your plan"
      className="mt-6 rounded border border-gray-200 bg-gray-50 p-4 text-sm"
    >
      <p>
        <strong>{PLAN_LABELS[usage.plan]} plan</strong> · {usage.used} of {usage.limit} applications
        used this month · resets on {formatResetDate(usage.resetsAt)}
      </p>
      <div
        role="progressbar"
        aria-label="Applications used this month"
        aria-valuemin={0}
        aria-valuemax={usage.limit}
        aria-valuenow={usage.used}
        className="mt-2 h-2 overflow-hidden rounded bg-gray-200"
      >
        <div
          className={`h-full ${reached ? "bg-amber-600" : "bg-black"}`}
          style={{ width: `${percentUsed(usage)}%` }}
        />
      </div>
      {reached && (
        <p className="mt-2 font-medium text-amber-800">
          You have used all the applications of your plan this month.
        </p>
      )}
      {!profile.isComplete && (
        <p className="mt-2 text-amber-800">
          Your profile is not complete yet.{" "}
          <Link href="/profile" className="font-medium underline">
            Complete my profile
          </Link>{" "}
          (at least your city) before creating an application.
        </p>
      )}
    </section>
  );
}
