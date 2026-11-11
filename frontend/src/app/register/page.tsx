import { AuthCard } from "@/components/AuthCard";
import { RegisterForm } from "@/components/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthCard
      title="Create your account"
      intro="Tailored CVs and cover letters for every job offer."
    >
      <RegisterForm />
    </AuthCard>
  );
}
