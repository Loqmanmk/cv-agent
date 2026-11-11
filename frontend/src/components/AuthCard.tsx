import Link from "next/link";
import type { ReactNode } from "react";

type Props = { title: string; intro?: string; children: ReactNode };

export function AuthCard({ title, intro, children }: Props) {
  return (
    <main className="mx-auto max-w-sm p-8">
      <Link href="/login" className="text-sm font-semibold">
        CV Agent
      </Link>
      <h1 className="mt-4 text-2xl font-bold">{title}</h1>
      {intro && <p className="mt-2 text-sm text-gray-600">{intro}</p>}
      {children}
    </main>
  );
}
