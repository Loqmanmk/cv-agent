import { ApplicationPanel } from "@/components/ApplicationPanel";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">CV Agent</h1>
      <p className="mt-2 text-gray-600">
        Upload your CV and a job offer. Get a tailored one-page CV and a cover letter.
      </p>
      <ApplicationPanel />
    </main>
  );
}
