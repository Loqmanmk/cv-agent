import { AuthCard } from "@/components/AuthCard";
import { ResetPasswordForm } from "@/components/ResetPasswordForm";

export default function ResetPasswordPage() {
  return (
    <AuthCard
      title="Choose a new password"
      intro="Every device will be logged out once it is changed."
    >
      <ResetPasswordForm />
    </AuthCard>
  );
}
