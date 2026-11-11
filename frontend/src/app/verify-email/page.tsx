import { AuthCard } from "@/components/AuthCard";
import { VerifyEmail } from "@/components/VerifyEmail";

export default function VerifyEmailPage() {
  return (
    <AuthCard title="Confirm your email address">
      <VerifyEmail />
    </AuthCard>
  );
}
