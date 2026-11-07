"use client";

import { useState, type FormEvent } from "react";

import { MAX_JOB_CHARS, validateApplication, type ValidationErrors } from "@/lib/validation";

export type ApplicationFormValues = {
  cvFile: File;
  jobText: string;
  includePhoto: boolean;
};

type Props = {
  onSubmit: (values: ApplicationFormValues) => void;
  disabled?: boolean;
};

export function ApplicationForm({ onSubmit, disabled = false }: Props) {
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [jobText, setJobText] = useState("");
  const [includePhoto, setIncludePhoto] = useState(true);
  const [errors, setErrors] = useState<ValidationErrors>({});

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validateApplication({ cvFile, jobText });
    setErrors(found);
    if (found.cvFile || found.jobText || !cvFile) return;
    onSubmit({ cvFile, jobText: jobText.trim(), includePhoto });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-6">
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
