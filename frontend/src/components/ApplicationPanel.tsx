"use client";

import { useState } from "react";

import { ApplicationForm, type ApplicationFormValues } from "@/components/ApplicationForm";

export function ApplicationPanel() {
  const [submitted, setSubmitted] = useState<ApplicationFormValues | null>(null);

  return (
    <>
      <ApplicationForm onSubmit={setSubmitted} />
      {submitted && (
        <p role="status" className="mt-6 rounded bg-green-50 p-3 text-sm text-green-800">
          Ready to send: {submitted.cvFile.name} (
          {submitted.includePhoto ? "with photo" : "without photo"}). Sending comes in the next
          step.
        </p>
      )}
    </>
  );
}
