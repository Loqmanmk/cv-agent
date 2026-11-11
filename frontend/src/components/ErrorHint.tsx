import Link from "next/link";

import type { ApiError } from "@/lib/api";

// The backend starts its "incomplete profile" message with these words.
export const INCOMPLETE_PROFILE_MESSAGE = "Complete your profile";

export function ErrorHint({ error }: { error: ApiError }) {
  if (error.status === 402) {
    return (
      <p className="mt-2">
        Your plan summary above shows when your monthly applications reset. Paid plans with more
        applications are coming soon.
      </p>
    );
  }
  if (error.status === 422 && error.message.startsWith(INCOMPLETE_PROFILE_MESSAGE)) {
    return (
      <p className="mt-2">
        <Link href="/profile" className="font-medium underline">
          Open my profile
        </Link>
      </p>
    );
  }
  return null;
}
