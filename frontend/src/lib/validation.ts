export const MAX_CV_BYTES = 5_000_000;
export const MAX_JOB_CHARS = 20_000;
export const ALLOWED_EXTENSIONS = [".docx", ".pdf"] as const;

export type ApplicationInput = {
  cvFile: File | null;
  jobText: string;
  /** True when the saved CV is used, so no file has to be chosen. */
  usesSavedCv?: boolean;
};

export type ValidationErrors = {
  cvFile?: string;
  jobText?: string;
};

function validateCvFile(file: File | null): string | null {
  if (!file) return "Choose your CV file.";
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "The CV must be a .docx or .pdf file.";
  }
  if (file.size === 0) return "The CV file is empty.";
  if (file.size > MAX_CV_BYTES) return "The CV file is too large (5 MB maximum).";
  return null;
}

function validateJobText(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return "Paste the job offer.";
  if (trimmed.length > MAX_JOB_CHARS) {
    return `The job offer is too long (${MAX_JOB_CHARS} characters maximum).`;
  }
  return null;
}

export function validateApplication(input: ApplicationInput): ValidationErrors {
  const errors: ValidationErrors = {};
  const cvError = input.usesSavedCv ? null : validateCvFile(input.cvFile);
  const jobError = validateJobText(input.jobText);
  if (cvError) errors.cvFile = cvError;
  if (jobError) errors.jobText = jobError;
  return errors;
}
