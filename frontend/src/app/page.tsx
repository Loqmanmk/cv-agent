import { AppShell } from "@/components/AppShell";
import { NewApplication } from "@/components/NewApplication";

export default function Home() {
  return (
    <AppShell>
      <h1 className="text-3xl font-bold">New application</h1>
      <p className="mt-2 text-gray-600">
        Upload your CV and a job offer. Get a tailored one-page CV and a cover letter.
      </p>
      <NewApplication />
    </AppShell>
  );
}
