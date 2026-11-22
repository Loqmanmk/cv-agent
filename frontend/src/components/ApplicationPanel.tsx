"use client";

import { useEffect, useRef, useState } from "react";

import { ApplicationForm, type ApplicationFormValues } from "@/components/ApplicationForm";
import { ErrorHint } from "@/components/ErrorHint";
import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import { ApiError, createApplication, renderDocuments, type ApplicationResult } from "@/lib/api";
import { base64ToPdfBlob, documentFileName } from "@/lib/pdf";
import { uploadSavedCv, type SavedCv } from "@/lib/savedCvApi";
import { saveApplication } from "@/lib/trackerApi";

const CREATE_TIMEOUT_MS = 500_000;
const RENDER_TIMEOUT_MS = 120_000;
const TIMEOUT_MESSAGE = "The request took too long. Please try again.";
const FALLBACK_TITLE = "Application";
const LANGUAGE_NAMES: Record<string, string> = {
  fr: "French",
  en: "English",
  de: "German",
  ar: "Arabic",
};

type DoneState = {
  phase: "done";
  result: ApplicationResult;
  photoRequested: boolean;
  cvUrl: string;
  /** null when no cover letter was asked for. */
  letterUrl: string | null;
  regenerating: boolean;
  regenerateError: string | null;
  edits: number;
};

type State =
  { phase: "idle" } | { phase: "loading" } | { phase: "error"; error: ApiError } | DoneState;

type SaveState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "saved"; id: number }
  | { phase: "error"; message: string };

function ElapsedSeconds() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  return <>{seconds}</>;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError("Something went wrong. Please try again.", 0);
}

function pdfUrl(base64: string): string {
  return URL.createObjectURL(base64ToPdfBlob(base64));
}

function optionalPdfUrl(base64: string | null): string | null {
  return base64 === null ? null : pdfUrl(base64);
}

function beginRequest(timeoutMs: number) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  return {
    controller,
    timedOut: () => timedOut,
    finish: () => clearTimeout(timer),
  };
}

type Props = {
  onCreated?: () => void;
  savedCv?: SavedCv | null;
  /** Called when the user saves a new CV. Without it, CVs are never saved. */
  onSavedCvChange?: (savedCv: SavedCv) => void;
  onRemoveSavedCv?: () => void;
};

export function ApplicationPanel({
  onCreated,
  savedCv = null,
  onSavedCvChange,
  onRemoveSavedCv,
}: Props = {}) {
  const [state, setState] = useState<State>({ phase: "idle" });
  const [save, setSave] = useState<SaveState>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);
  const cvUrl = state.phase === "done" ? state.cvUrl : null;
  const letterUrl = state.phase === "done" ? state.letterUrl : null;

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (cvUrl === null) return undefined;
    return () => {
      URL.revokeObjectURL(cvUrl);
      if (letterUrl !== null) URL.revokeObjectURL(letterUrl);
    };
  }, [cvUrl, letterUrl]);

  async function handleSubmit(values: ApplicationFormValues) {
    controllerRef.current?.abort();
    const request = beginRequest(CREATE_TIMEOUT_MS);
    controllerRef.current = request.controller;

    setSave({ phase: "idle" });
    setState({ phase: "loading" });
    try {
      let cvFile = values.cvFile;
      if (cvFile !== null && values.saveCv && onSavedCvChange) {
        // Saved first, so the application then uses the saved CV and the file is sent once.
        onSavedCvChange(await uploadSavedCv(cvFile, request.controller.signal));
        cvFile = null;
      }
      const result = await createApplication(
        {
          cvFile,
          jobText: values.jobText,
          includePhoto: values.includePhoto,
          includeLetter: values.includeLetter,
        },
        request.controller.signal,
      );
      setState({
        phase: "done",
        result,
        photoRequested: values.includePhoto,
        cvUrl: pdfUrl(result.cvPdfBase64),
        letterUrl: optionalPdfUrl(result.letterPdfBase64),
        regenerating: false,
        regenerateError: null,
        edits: 0,
      });
      onCreated?.();
    } catch (error) {
      if (isAbortError(error)) {
        if (request.timedOut()) {
          setState({ phase: "error", error: new ApiError(TIMEOUT_MESSAGE, 0) });
        }
        return;
      }
      setState({ phase: "error", error: toApiError(error) });
    } finally {
      request.finish();
    }
  }

  async function handleRegenerate(edited: EditedDocuments) {
    if (state.phase !== "done") return;
    const current = state;
    controllerRef.current?.abort();
    const request = beginRequest(RENDER_TIMEOUT_MS);
    controllerRef.current = request.controller;

    setState({ ...current, regenerating: true, regenerateError: null });
    try {
      const documents = await renderDocuments(
        {
          cv: edited.cv,
          letter: edited.letter,
          language: current.result.language,
          photoBase64: edited.photoBase64,
        },
        request.controller.signal,
      );
      setState({
        ...current,
        cvUrl: pdfUrl(documents.cvPdfBase64),
        letterUrl: optionalPdfUrl(documents.letterPdfBase64),
        regenerating: false,
        regenerateError: null,
        edits: current.edits + 1,
      });
    } catch (error) {
      if (isAbortError(error) && !request.timedOut()) return;
      const message = isAbortError(error) ? TIMEOUT_MESSAGE : toApiError(error).message;
      setState({ ...current, regenerating: false, regenerateError: message });
    } finally {
      request.finish();
    }
  }

  async function handleSave(edited: EditedDocuments) {
    if (state.phase !== "done") return;
    const { result } = state;
    setSave({ phase: "saving" });
    try {
      const saved = await saveApplication({
        jobTitle: result.jobTitle.trim() || FALLBACK_TITLE,
        company: edited.letter?.recipient.company || result.company,
        language: result.language,
        sourceUrl: "",
        cv: edited.cv,
        letter: edited.letter,
        photoBase64: edited.photoBase64,
      });
      setSave({ phase: "saved", id: saved.id });
    } catch (error) {
      setSave({ phase: "error", message: toApiError(error).message });
    }
  }

  return (
    <>
      <ApplicationForm
        onSubmit={(values) => void handleSubmit(values)}
        disabled={state.phase === "loading"}
        savedCv={savedCv}
        canSaveCv={onSavedCvChange !== undefined}
        onRemoveSavedCv={onRemoveSavedCv}
      />

      {state.phase === "loading" && (
        <p role="status" className="mt-6 rounded bg-blue-50 p-3 text-sm text-blue-800">
          Creating your application… this usually takes about a minute. <ElapsedSeconds /> s
        </p>
      )}

      {state.phase === "error" && (
        <div role="alert" className="mt-6 rounded bg-red-50 p-3 text-sm text-red-800">
          <p>{state.error.message}</p>
          <ErrorHint error={state.error} />
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
        <>
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
                download={documentFileName(
                  "cv",
                  state.result.cv.header.name,
                  state.result.language,
                )}
                className="font-medium underline"
              >
                Download CV (PDF)
              </a>
              {state.letterUrl !== null && (
                <a
                  href={state.letterUrl}
                  download={documentFileName(
                    "letter",
                    state.result.cv.header.name,
                    state.result.language,
                  )}
                  className="font-medium underline"
                >
                  Download cover letter (PDF)
                </a>
              )}
            </div>
            {state.edits > 0 && (
              <p role="status" className="mt-2 text-green-800">
                Documents updated from your edits.
              </p>
            )}
            <p className="mt-3 text-gray-700">
              Read your documents before you send them: the AI can make mistakes.
            </p>
            <button
              type="button"
              onClick={() => {
                setSave({ phase: "idle" });
                setState({ phase: "idle" });
              }}
              className="mt-3 text-sm underline"
            >
              Start again
            </button>
          </section>

          <ReviewEditor
            result={state.result}
            busy={state.regenerating}
            error={state.regenerateError}
            onRegenerate={(edited) => void handleRegenerate(edited)}
            onSave={(edited) => void handleSave(edited)}
            saving={save.phase === "saving"}
            saveMessage={
              save.phase === "saved"
                ? `Saved as application #${save.id}. Follow it in "My applications".`
                : null
            }
            saveError={save.phase === "error" ? save.message : null}
          />
        </>
      )}
    </>
  );
}
