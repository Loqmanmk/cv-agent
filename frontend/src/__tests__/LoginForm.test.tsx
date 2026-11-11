import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/LoginForm";
import { ApiError } from "@/lib/api";

type Status = "loading" | "anonymous" | "authenticated";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  value: {
    status: "anonymous" as Status,
    email: null as string | null,
    startupError: null as string | null,
    login: vi.fn(),
    logout: vi.fn(),
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/components/AuthProvider", () => ({ useAuth: () => auth.value }));

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email"), "  jane@example.com ");
  await user.type(screen.getByLabelText("Password"), "my passphrase");
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

beforeEach(() => {
  router.replace.mockReset();
  auth.value.login.mockReset();
  auth.value.status = "anonymous";
  auth.value.startupError = null;
});

describe("LoginForm", () => {
  it("asks for both fields and sends nothing when one is missing", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText("Email"), "jane@example.com");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter your email and your password.");
    expect(auth.value.login).not.toHaveBeenCalled();
  });

  it("logs in with the trimmed email and the password as typed", async () => {
    auth.value.login.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user);

    expect(auth.value.login).toHaveBeenCalledWith("jane@example.com", "my passphrase");
  });

  it("shows the message of the server when the login is refused", async () => {
    auth.value.login.mockRejectedValue(new ApiError("Invalid email or password.", 401));
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });

  it("shows how long to wait when the attempts are limited", async () => {
    auth.value.login.mockRejectedValue(
      new ApiError("Too many requests. Please try again in about 10 minutes.", 429),
    );
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("about 10 minutes");
  });

  it("shows a generic message for an unexpected error", async () => {
    auth.value.login.mockRejectedValue(new Error("boom with internal detail"));
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong. Please try again.");
    expect(alert).not.toHaveTextContent("boom");
  });

  it("locks the form while logging in", async () => {
    auth.value.login.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    render(<LoginForm />);

    await fillAndSubmit(user);

    expect(await screen.findByRole("button", { name: "Logging in…" })).toBeDisabled();
    expect(screen.getByLabelText("Email")).toBeDisabled();
  });

  it("shows a problem that stopped the session check, such as an unreachable server", () => {
    auth.value.startupError = "Cannot reach the server. Check that the backend is running.";

    render(<LoginForm />);

    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("waits while the session is being checked", () => {
    auth.value.status = "loading";

    render(<LoginForm />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  it("leaves the login page when the user is logged in", () => {
    auth.value.status = "authenticated";

    render(<LoginForm />);

    expect(router.replace).toHaveBeenCalledWith("/");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });
});
