"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorBox } from "@/components/ErrorBox";
import { PasswordFields } from "@/components/PasswordFields";
import { resetPassword } from "@/lib/authApi";
import { toShownError, type ShownError } from "@/lib/errors";
import { useLinkToken } from "@/lib/linkToken";
import { newPasswordProblems } from "@/lib/passwordRules";

const INCOMPLETE = "This link is incomplete. Open the latest link from your email.";

export function ResetPasswordForm() {
  const readToken = useLinkToken();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ShownError | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problems = newPasswordProblems(password, confirm);
    if (problems.length > 0) {
      setError({ message: "Check the form.", details: problems });
      return;
    }
    const token = readToken();
    if (token === null) {
      setError({ message: INCOMPLETE, details: [] });
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      setDone(await resetPassword(token, password));
      setPassword("");
      setConfirm("");
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
          <Link href="/login" className="font-medium underline">
            Log in
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} noValidate className="mt-6 space-y-4">
      <PasswordFields
        password={password}
        confirm={confirm}
        onPassword={setPassword}
        onConfirm={setConfirm}
        disabled={submitting}
        label="New password"
      />
      {error && <ErrorBox error={error} />}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Saving…" : "Choose this password"}
      </button>
      <p className="text-sm text-gray-600">
        Link expired?{" "}
        <Link href="/forgot-password" className="underline">
          Ask for a new link
        </Link>
      </p>
    </form>
  );
}
