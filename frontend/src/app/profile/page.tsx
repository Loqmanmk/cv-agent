import { AppShell } from "@/components/AppShell";
import { ProfileForm } from "@/components/ProfileForm";

export default function ProfilePage() {
  return (
    <AppShell>
      <h1 className="text-3xl font-bold">My profile</h1>
      <p className="mt-2 text-gray-600">
        These details go into your cover letters. Your address and city are added by the app and are
        never sent to the AI.
      </p>
      <ProfileForm />
    </AppShell>
  );
}
