"use client";

import { useEffect, useState } from "react";

import { AccountSummary } from "@/components/AccountSummary";
import { ApplicationPanel } from "@/components/ApplicationPanel";
import { ApiError } from "@/lib/api";
import { deleteSavedCv, fetchSavedCv, type SavedCv } from "@/lib/savedCvApi";

const DELETE_ERROR = "Your saved CV could not be deleted. Please try again.";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function NewApplication() {
  const [version, setVersion] = useState(0);
  const [savedCv, setSavedCv] = useState<SavedCv | null>(null);
  const [savedCvError, setSavedCvError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchSavedCv(controller.signal)
      .then(setSavedCv)
      .catch((error: unknown) => {
        // Without the saved CV the user can still upload a file, so nothing is shown.
        if (!isAbortError(error)) setSavedCv(null);
      });
    return () => controller.abort();
  }, []);

  async function handleRemove() {
    try {
      await deleteSavedCv();
      setSavedCv(null);
      setSavedCvError(null);
    } catch (error) {
      setSavedCvError(error instanceof ApiError ? error.message : DELETE_ERROR);
    }
  }

  return (
    <>
      <AccountSummary version={version} />
      {savedCvError && (
        <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-sm text-red-800">
          {savedCvError}
        </p>
      )}
      <ApplicationPanel
        onCreated={() => setVersion((value) => value + 1)}
        savedCv={savedCv}
        onSavedCvChange={setSavedCv}
        onRemoveSavedCv={() => void handleRemove()}
      />
    </>
  );
}
