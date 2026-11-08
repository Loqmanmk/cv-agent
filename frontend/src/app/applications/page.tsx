import Link from "next/link";

import { TrackerList } from "@/components/TrackerList";

export default function ApplicationsPage() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-3xl font-bold">My applications</h1>
        <Link href="/" className="text-sm underline">
          Back to the form
        </Link>
      </div>
      <TrackerList />
    </main>
  );
}
