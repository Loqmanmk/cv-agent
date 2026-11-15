"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, fetchJobText } from "@/lib/api";
import { formatDay } from "@/lib/format";
import type { SavedCv } from "@/lib/savedCvApi";
import { MAX_JOB_CHARS, validateApplication, type ValidationErrors } from "@/lib/validation";

export type ApplicationFormValues = {
  /** null: use the CV saved on the account. */
  cvFile: File | null;
  jobText: string;
  includePhoto: boolean;
  /** Keep the chosen file as the saved CV for the next applications. */
  saveCv: boolean;
};

type Props = {
  onSubmit: (values: ApplicationFormValues) => void;
  disabled?: boolean;
  savedCv?: SavedCv | null;
  /** Shows the "save this CV" choice. Off when nothing can store the CV. */
  canSaveCv?: boolean;
  onRemoveSavedCv?: () => void;
};

type FetchState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "done"; truncated: boolean; sourceUrl: string };

const FETCH_TIMEOUT_MS = 30_000;
const FETCH_ERROR = "Something went wrong. Please try again.";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function ApplicationForm({
  onSubmit,
  disabled = false,
  savedCv = null,
  canSaveCv = false,
  onRemoveSavedCv,
}: Props) {
  const [cvFile, setCvFile] = useState<File | null>(null);
  // The saved CV being replaced. A newly saved CV has another date, so it is shown again.
  const [replacing, setReplacing] = useState<string | null>(null);
  const [saveCv, setSaveCv] = useState(true);
  const usesSavedCv = savedCv !== null && replacing !== savedCv.uploadedAt;
  const [jobText, setJobText] = useState("");
  const [includePhoto, setIncludePhoto] = useState(true);
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [jobUrl, setJobUrl] = useState("");
  const [fetchState, setFetchState] = useState<FetchState>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  async function handleFetch() {
    const url = jobUrl.trim();
    if (!url) {
      setFetchState({ phase: "error", message: "Paste the link of the job offer." });
      return;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, FETCH_TIMEOUT_MS);

    setFetchState({ phase: "loading" });
    try {
      const fetched = await fetchJobText(url, controller.signal);
      setJobText(fetched.text);
      setErrors((current) => ({ ...current, jobText: undefined }));
      setFetchState({ phase: "done", truncated: fetched.truncated, sourceUrl: fetched.sourceUrl });
    } catch (error) {
      if (isAbortError(error)) {
        if (timedOut) {
          setFetchState({ phase: "error", message: "The request took too long. Try again." });
        }
        return;
      }
      const message = error instanceof ApiError ? error.message : FETCH_ERROR;
      setFetchState({ phase: "error", message });
    } finally {
      clearTimeout(timer);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validateApplication({ cvFile, jobText, usesSavedCv });
    setErrors(found);
    if (found.cvFile || found.jobText) return;
    if (usesSavedCv) {
      onSubmit({ cvFile: null, jobText: jobText.trim(), includePhoto, saveCv: false });
    } else if (cvFile) {
      onSubmit({ cvFile, jobText: jobText.trim(), includePhoto, saveCv: canSaveCv && saveCv });
    }
  }

  const fetching = fetchState.phase === "loading";

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-6">
      {usesSavedCv ? (
        <section aria-label="Your CV" className="rounded border border-gray-300 p-3 text-sm">
          <p>
            Your saved CV: <span className="font-medium">{savedCv.filename}</span>
          </p>
          <p className="text-gray-500">Saved on {formatDay(savedCv.uploadedAt)}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => setReplacing(savedCv.uploadedAt)}
              disabled={disabled}
              className="rounded border border-gray-400 px-3 py-1 font-medium disabled:opacity-50"
            >
              Change my CV
            </button>
            {onRemoveSavedCv && (
              <button
                type="button"
                onClick={onRemoveSavedCv}
                disabled={disabled}
                className="rounded px-3 py-1 text-red-700 underline disabled:opacity-50"
              >
                Delete my saved CV
              </button>
            )}
          </div>
        </section>
      ) : (
        <div>
          <label htmlFor="cv-file" className="block text-sm font-medium">
            CV file (.docx or .pdf)
          </label>
          <input
            id="cv-file"
            type="file"
            accept=".docx,.pdf"
            disabled={disabled}
            aria-invalid={errors.cvFile ? true : undefined}
            aria-describedby={errors.cvFile ? "cv-file-error" : undefined}
            onChange={(event) => setCvFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm"
          />
          {errors.cvFile && (
            <p id="cv-file-error" role="alert" className="mt-1 text-sm text-red-600">
              {errors.cvFile}
            </p>
          )}
          {canSaveCv && (
            <div className="mt-2 flex items-center gap-2">
              <input
                id="save-cv"
                type="checkbox"
                checked={saveCv}
                disabled={disabled}
                onChange={(event) => setSaveCv(event.target.checked)}
              />
              <label htmlFor="save-cv" className="text-sm">
                Save this CV for my next applications
              </label>
            </div>
          )}
          {savedCv !== null && (
            <button
              type="button"
              onClick={() => setReplacing(null)}
              disabled={disabled}
              className="mt-2 text-sm underline disabled:opacity-50"
            >
              Keep my saved CV ({savedCv.filename})
            </button>
          )}
        </div>
      )}

      <div>
        <label htmlFor="job-url" className="block text-sm font-medium">
          Link to the job offer (optional)
        </label>
        <div className="mt-1 flex gap-2">
          <input
            id="job-url"
            type="url"
            value={jobUrl}
            disabled={disabled || fetching}
            onChange={(event) => setJobUrl(event.target.value)}
            placeholder="https://company.example/careers/software-engineer"
            className="block w-full rounded border border-gray-300 p-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void handleFetch()}
            disabled={disabled || fetching}
            className="shrink-0 rounded border border-gray-400 px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {fetching ? "Fetching…" : "Fetch the offer"}
          </button>
        </div>
        {fetchState.phase === "error" && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {fetchState.message}
          </p>
        )}
        {fetchState.phase === "done" && (
          <p role="status" className="mt-1 text-sm text-green-700">
            Offer fetched from {fetchState.sourceUrl}. Read the text below and fix anything that is
            missing.
            {fetchState.truncated &&
              ` The page was longer than ${MAX_JOB_CHARS} characters, so the end was cut.`}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="job-text" className="block text-sm font-medium">
          Job offer
        </label>
        <textarea
          id="job-text"
          rows={10}
          value={jobText}
          disabled={disabled}
          onChange={(event) => setJobText(event.target.value)}
          aria-invalid={errors.jobText ? true : undefined}
          aria-describedby={errors.jobText ? "job-text-error" : undefined}
          placeholder="Paste the full text of the job offer here"
          className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
        />
        <p className="mt-1 text-xs text-gray-500">
          {jobText.length} / {MAX_JOB_CHARS}
        </p>
        {errors.jobText && (
          <p id="job-text-error" role="alert" className="mt-1 text-sm text-red-600">
            {errors.jobText}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <input
          id="include-photo"
          type="checkbox"
          checked={includePhoto}
          disabled={disabled}
          onChange={(event) => setIncludePhoto(event.target.checked)}
        />
        <label htmlFor="include-photo" className="text-sm">
          Include my photo
        </label>
      </div>

      <button
        type="submit"
        disabled={disabled}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Create my application
      </button>
    </form>
  );
}
