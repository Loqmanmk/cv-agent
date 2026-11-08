import Link from "next/link";

import { ApplicationPanel } from "@/components/ApplicationPanel";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-3xl font-bold">CV Agent</h1>
        <Link href="/applications" className="text-sm underline">
          My applications
        </Link>
      </div>
      <p className="mt-2 text-gray-600">
        Upload your CV and a job offer. Get a tailored one-page CV and a cover letter.
      </p>
      <ApplicationPanel />
    </main>
  );
}
