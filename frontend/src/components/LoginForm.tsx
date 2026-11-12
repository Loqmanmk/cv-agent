"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/AuthProvider";
import { GoogleButton } from "@/components/GoogleButton";
import { ApiError } from "@/lib/api";
import { useGoogleError } from "@/lib/googleSignIn";

const GENERIC_ERROR = "Something went wrong. Please try again.";

export function LoginForm() {
  const { status, startupError, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const googleError = useGoogleError();

  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError("Enter your email and your password.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : GENERIC_ERROR);
    } finally {
      setSubmitting(false);
    }
  }

  if (status !== "anonymous") {
    return (
      <p role="status" className="mt-6 text-sm text-gray-600">
        Loading…
      </p>
    );
  }

  const message = error ?? googleError ?? startupError;

  return (
    <form onSubmit={(event) => void handleSubmit(event)} noValidate className="mt-6 space-y-4">
      <GoogleButton />
      <div>
        <label htmlFor="login-email" className="block text-sm font-medium">
          Email
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          value={email}
          disabled={submitting}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
        />
      </div>
      <div>
        <label htmlFor="login-password" className="block text-sm font-medium">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          disabled={submitting}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
        />
      </div>
      {message && (
        <p role="alert" className="text-sm text-red-700">
          {message}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {submitting ? "Logging in…" : "Log in"}
      </button>
      <p className="text-sm">
        <Link href="/forgot-password" className="underline">
          Forgot your password?
        </Link>
      </p>
      <p className="text-sm text-gray-600">
        No account yet?{" "}
        <Link href="/register" className="underline">
          Create one
        </Link>
      </p>
    </form>
  );
}
