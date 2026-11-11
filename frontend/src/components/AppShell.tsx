"use client";

import type { ReactNode } from "react";

import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";

type Props = { children: ReactNode; wide?: boolean };

export function AppShell({ children, wide = false }: Props) {
  return (
    <AuthGate>
      <AppHeader />
      <main className={`mx-auto p-8 ${wide ? "max-w-3xl" : "max-w-2xl"}`}>{children}</main>
    </AuthGate>
  );
}
