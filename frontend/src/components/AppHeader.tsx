"use client";

import Link from "next/link";

import { useAuth } from "@/components/AuthProvider";

export function AppHeader() {
  const { email, logout } = useAuth();

  return (
    <header className="border-b border-gray-200">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-8 py-3 text-sm"
      >
        <div className="flex gap-4">
          <Link href="/" className="font-semibold">
            CV Agent
          </Link>
          <Link href="/applications" className="underline">
            My applications
          </Link>
          <Link href="/profile" className="underline">
            Profile
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-gray-600">{email}</span>
          <button type="button" onClick={() => void logout()} className="underline">
            Log out
          </button>
        </div>
      </nav>
    </header>
  );
}
