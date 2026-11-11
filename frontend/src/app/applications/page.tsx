import { AppShell } from "@/components/AppShell";
import { TrackerList } from "@/components/TrackerList";

export default function ApplicationsPage() {
  return (
    <AppShell wide>
      <h1 className="text-3xl font-bold">My applications</h1>
      <TrackerList />
    </AppShell>
  );
}
