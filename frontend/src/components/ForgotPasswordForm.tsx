"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorBox } from "@/components/ErrorBox";
import { forgotPassword } from "@/lib/authApi";
import { toShownError, type ShownError } from "@/lib/errors";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ShownError | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setError({ message: "Enter your email address.", details: [] });
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      setDone(await forgotPassword(email.trim()));
    } catch (caught) {
      setError(toShownError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  if (done !== null) {
    return (
      <div role="status" className="mt-6 rounded bg-green-50 p-3 text-sm text-green-800">
        <p>{done}</p>
        <p className="mt-2">
          The link works for 30 minutes. Check your spam folder if you miss it.
        </p>
        <p className="mt-2">
          <Link href="/login" className="font-medium underline">
            Back to log in
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} noValidate className="mt-6 space-y-4">
      <div>
        <label htmlFor="forgot-email" className="block text-sm font-medium">
          Email
        </label>
        <input
          id="forgot-email"
          type="email"
          autoComplete="email"
          value={email}
          disabled={submitting}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
        />
      </div>
      {error && <ErrorBox error={error} />}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Sending…" : "Send me a link"}
      </button>
    </form>
  );
}
