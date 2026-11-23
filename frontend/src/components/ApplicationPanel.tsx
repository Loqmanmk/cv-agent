"use client";

import { useEffect, useRef, useState } from "react";

import { ApplicationForm, type ApplicationFormValues } from "@/components/ApplicationForm";
import { ErrorHint } from "@/components/ErrorHint";
import { ReviewEditor, type EditedDocuments } from "@/components/ReviewEditor";
import { GenerationProgress } from "@/components/GenerationProgress";
import { ScorePreview } from "@/components/ScorePreview";
import {
  ApiError,
  createApplication,
  renderDocuments,
  scoreApplication,
  type ApplicationResult,
  type GenerationStage,
  type MatchPreview,
} from "@/lib/api";
import { base64ToPdfBlob, documentFileName } from "@/lib/pdf";
import { uploadSavedCv, type SavedCv } from "@/lib/savedCvApi";
import { saveApplication } from "@/lib/trackerApi";

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
  | { phase: "idle" }
  | { phase: "loading"; stage: GenerationStage; includeLetter: boolean; translated: boolean }
  | { phase: "error"; error: ApiError }
  | DoneState;

type ScoreState =
  | { phase: "idle" }
  | { phase: "checking" }
  | { phase: "shown"; preview: MatchPreview }
  | { phase: "error"; error: ApiError };

type SaveState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "saved"; id: number }
  | { phase: "error"; message: string };

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
  const [score, setScore] = useState<ScoreState>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);
  const scoreControllerRef = useRef<AbortController | null>(null);
  const cvUrl = state.phase === "done" ? state.cvUrl : null;
  const letterUrl = state.phase === "done" ? state.letterUrl : null;

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      scoreControllerRef.current?.abort();
    },
    [],
  );

  async function handleCheckScore(values: ApplicationFormValues) {
    scoreControllerRef.current?.abort();
    const controller = new AbortController();
    scoreControllerRef.current = controller;
    setScore({ phase: "checking" });
    try {
      const preview = await scoreApplication(
        { cvFile: values.cvFile, jobText: values.jobText },
        controller.signal,
      );
      setScore({ phase: "shown", preview });
    } catch (error) {
      if (isAbortError(error)) return;
      setScore({ phase: "error", error: toApiError(error) });
    }
  }

  useEffect(() => {
    if (cvUrl === null) return undefined;
    return () => {
      URL.revokeObjectURL(cvUrl);
      if (letterUrl !== null) URL.revokeObjectURL(letterUrl);
    };
  }, [cvUrl, letterUrl]);

  async function handleSubmit(values: ApplicationFormValues) {
    controllerRef.current?.abort();
    scoreControllerRef.current?.abort();
    setScore({ phase: "idle" });
    // No time limit: the server works in the background and the page follows it.
    const controller = new AbortController();
    controllerRef.current = controller;
    const includeLetter = values.includeLetter;
    let translated = false;
    const showStage = (stage: GenerationStage) => {
      if (controller.signal.aborted) return;
      translated ||= stage === "translating";
      setState({ phase: "loading", stage, includeLetter, translated });
    };

    setSave({ phase: "idle" });
    showStage("queued");
    try {
      let cvFile = values.cvFile;
      if (cvFile !== null && values.saveCv && onSavedCvChange) {
        // Saved first, so the application then uses the saved CV and the file is sent once.
        onSavedCvChange(await uploadSavedCv(cvFile, controller.signal));
        cvFile = null;
      }
      const result = await createApplication(
        {
          cvFile,
          jobText: values.jobText,
          includePhoto: values.includePhoto,
          includeLetter,
        },
        controller.signal,
        showStage,
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
      if (isAbortError(error)) return;
      setState({ phase: "error", error: toApiError(error) });
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
        onCheckScore={(values) => void handleCheckScore(values)}
        checking={score.phase === "checking"}
        disabled={state.phase === "loading"}
        savedCv={savedCv}
        canSaveCv={onSavedCvChange !== undefined}
        onRemoveSavedCv={onRemoveSavedCv}
      />

      {score.phase === "checking" && (
        <p role="status" className="mt-6 rounded bg-blue-50 p-3 text-sm text-blue-800">
          Reading the offer and your CV to compute your match score…
        </p>
      )}
      {score.phase === "shown" && <ScorePreview preview={score.preview} />}
      {score.phase === "error" && (
        <div role="alert" className="mt-6 rounded bg-red-50 p-3 text-sm text-red-800">
          <p>{score.error.message}</p>
          <ErrorHint error={score.error} />
        </div>
      )}

      {state.phase === "loading" && (
        <GenerationProgress
          stage={state.stage}
          includeLetter={state.includeLetter}
          translated={state.translated}
        />
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
