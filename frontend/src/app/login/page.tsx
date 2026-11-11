import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-3xl font-bold">CV Agent</h1>
      <p className="mt-2 text-gray-600">Log in to create tailored CVs and cover letters.</p>
      <LoginForm />
    </main>
  );
}
