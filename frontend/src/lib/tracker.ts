export const STATUSES = [
  "saved",
  "applied",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
] as const;

export type ApplicationStatus = (typeof STATUSES)[number];

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function isStatus(value: string): value is ApplicationStatus {
  return (STATUSES as readonly string[]).includes(value);
}

export type TrackedApplication = {
  id: number;
  createdAt: string;
  jobTitle: string;
  company: string;
  language: string;
  sourceUrl: string;
  status: ApplicationStatus;
  notes: string;
  /** false when the application was made without a cover letter. */
  hasLetter: boolean;
};
