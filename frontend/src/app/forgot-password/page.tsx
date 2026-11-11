import { AuthCard } from "@/components/AuthCard";
import { ForgotPasswordForm } from "@/components/ForgotPasswordForm";

export default function ForgotPasswordPage() {
  return (
    <AuthCard
      title="Forgot your password?"
      intro="Enter your email address and we will send you a link to choose a new password."
    >
      <ForgotPasswordForm />
    </AuthCard>
  );
}
