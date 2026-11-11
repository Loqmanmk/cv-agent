"use client";

import { useState } from "react";

import { AccountSummary } from "@/components/AccountSummary";
import { ApplicationPanel } from "@/components/ApplicationPanel";

export function NewApplication() {
  const [version, setVersion] = useState(0);

  return (
    <>
      <AccountSummary version={version} />
      <ApplicationPanel onCreated={() => setVersion((value) => value + 1)} />
    </>
  );
}
