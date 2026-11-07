"use client";

import { useEffect, useRef, useState } from "react";

import { ApplicationForm, type ApplicationFormValues } from "@/components/ApplicationForm";
import { ApiError, createApplication, type ApplicationResult } from "@/lib/api";
import { base64ToPdfBlob, fileSlug } from "@/lib/pdf";

const REQUEST_TIMEOUT_MS = 420_000;
const LANGUAGE_NAMES: Record<string, string> = {
  fr: "French",
  en: "English",
  de: "German",
  ar: "Arabic",
};

type State =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; error: ApiError }
  | {
      phase: "done";
      result: ApplicationResult;
      photoRequested: boolean;
      cvUrl: string;
      letterUrl: string;
    };

function ElapsedSeconds() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  return <>{seconds}</>;
}

export function ApplicationPanel() {
  const [state, setState] = useState<State>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (state.phase !== "done") return undefined;
    const { cvUrl, letterUrl } = state;
    return () => {
      URL.revokeObjectURL(cvUrl);
      URL.revokeObjectURL(letterUrl);
    };
  }, [state]);

  async function handleSubmit(values: ApplicationFormValues) {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);

    setState({ phase: "loading" });
    try {
      const result = await createApplication(values, controller.signal);
      setState({
        phase: "done",
        result,
        photoRequested: values.includePhoto,
        cvUrl: URL.createObjectURL(base64ToPdfBlob(result.cvPdfBase64)),
        letterUrl: URL.createObjectURL(base64ToPdfBlob(result.letterPdfBase64)),
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        if (timedOut) {
          const message = "The request took too long. Please try again.";
          setState({ phase: "error", error: new ApiError(message, 0) });
        }
        return;
      }
      const failure =
        error instanceof ApiError
          ? error
          : new ApiError("Something went wrong. Please try again.", 0);
      setState({ phase: "error", error: failure });
    } finally {
      clearTimeout(timer);
    }
  }

  return (
    <>
      <ApplicationForm
        onSubmit={(values) => void handleSubmit(values)}
        disabled={state.phase === "loading"}
      />

      {state.phase === "loading" && (
        <p role="status" className="mt-6 rounded bg-blue-50 p-3 text-sm text-blue-800">
          Creating your application… this usually takes about a minute. <ElapsedSeconds /> s
        </p>
      )}

      {state.phase === "error" && (
        <div role="alert" className="mt-6 rounded bg-red-50 p-3 text-sm text-red-800">
          <p>{state.error.message}</p>
          {state.error.violations.length > 0 && (
            <ul className="mt-2 list-disc pl-5">
              {state.error.violations.map((violation, index) => (
                <li key={`${index}-${violation}`}>{violation}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {state.phase === "done" && (
        <section
          aria-label="Result"
          className="mt-6 rounded border border-green-200 bg-green-50 p-4 text-sm"
        >
          <h2 className="text-lg font-semibold">
            {state.result.jobTitle}
            {state.result.company ? ` — ${state.result.company}` : ""}
          </h2>
          <p>Language: {LANGUAGE_NAMES[state.result.language] ?? state.result.language}</p>
          {state.photoRequested && !state.result.photoUsed && (
            <p className="mt-1 text-amber-700">
              No photo was found in your file, so the CV has no photo.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-4">
            <a
              href={state.cvUrl}
              download={`cv-${fileSlug(state.result.company)}.pdf`}
              className="font-medium underline"
            >
              Download CV (PDF)
            </a>
            <a
              href={state.letterUrl}
              download={`lettre-${fileSlug(state.result.company)}.pdf`}
              className="font-medium underline"
            >
              Download cover letter (PDF)
            </a>
          </div>
          <p className="mt-3 text-gray-700">
            Read both documents before you send them: the AI can make mistakes.
          </p>
          <button
            type="button"
            onClick={() => setState({ phase: "idle" })}
            className="mt-3 text-sm underline"
          >
            Start again
          </button>
        </section>
      )}
    </>
  );
}
