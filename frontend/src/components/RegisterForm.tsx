"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorBox } from "@/components/ErrorBox";
import { GoogleButton } from "@/components/GoogleButton";
import { PasswordFields } from "@/components/PasswordFields";
import { register } from "@/lib/authApi";
import { toShownError, type ShownError } from "@/lib/errors";
import { newPasswordProblems } from "@/lib/passwordRules";

export function RegisterForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ShownError | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problems = [
      ...(email.trim() ? [] : ["Enter your email address."]),
      ...newPasswordProblems(password, confirm),
    ];
    if (problems.length > 0) {
      setError({ message: "Check the form.", details: problems });
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      setDone(await register(email.trim(), password));
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
        <p className="mt-2">The link works for 48 hours. Check your spam folder if you miss it.</p>
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
      <GoogleButton />
      <div>
        <label htmlFor="register-email" className="block text-sm font-medium">
          Email
        </label>
        <input
          id="register-email"
          type="email"
          autoComplete="email"
          value={email}
          disabled={submitting}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
        />
      </div>
      <PasswordFields
        password={password}
        confirm={confirm}
        onPassword={setPassword}
        onConfirm={setConfirm}
        disabled={submitting}
      />
      {error && <ErrorBox error={error} />}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Create my account"}
      </button>
      <p className="text-sm text-gray-600">
        Already have an account?{" "}
        <Link href="/login" className="underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
