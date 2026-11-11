// Quotas reset at midnight UTC, so the date is shown in UTC for every user.
const RESET_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function formatResetDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : RESET_DATE.format(date);
}
