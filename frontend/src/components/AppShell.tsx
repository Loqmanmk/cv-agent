"use client";

import type { ReactNode } from "react";

import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";
import { VerifyReminder } from "@/components/VerifyReminder";

type Props = { children: ReactNode; wide?: boolean };

export function AppShell({ children, wide = false }: Props) {
  return (
    <AuthGate>
      <AppHeader />
      <VerifyReminder />
      <main className={`mx-auto p-8 ${wide ? "max-w-3xl" : "max-w-2xl"}`}>{children}</main>
    </AuthGate>
  );
}
