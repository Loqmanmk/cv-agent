import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppHeader } from "@/components/AppHeader";
import { AuthGate } from "@/components/AuthGate";

type Status = "loading" | "anonymous" | "authenticated";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const auth = vi.hoisted(() => ({
  value: {
    status: "loading" as Status,
    email: null as string | null,
    startupError: null as string | null,
    login: vi.fn(),
    logout: vi.fn(),
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/components/AuthProvider", () => ({ useAuth: () => auth.value }));

beforeEach(() => {
  router.replace.mockReset();
  auth.value.logout.mockReset();
  auth.value.status = "loading";
  auth.value.email = null;
});

describe("AuthGate", () => {
  it("shows a loading message and hides the page while the session is checked", () => {
    render(
      <AuthGate>
        <p>secret page</p>
      </AuthGate>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("sends an anonymous visitor to the login page and hides the page", () => {
    auth.value.status = "anonymous";

    render(
      <AuthGate>
        <p>secret page</p>
      </AuthGate>,
    );

    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("shows the page to a logged-in user", () => {
    auth.value.status = "authenticated";

    render(
      <AuthGate>
        <p>secret page</p>
      </AuthGate>,
    );

    expect(screen.getByText("secret page")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("AppHeader", () => {
  it("shows the email of the user and the navigation", () => {
    auth.value.status = "authenticated";
    auth.value.email = "jane@example.com";

    render(<AppHeader />);

    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My applications" })).toHaveAttribute(
      "href",
      "/applications",
    );
    expect(screen.getByRole("link", { name: "CV Agent" })).toHaveAttribute("href", "/");
  });

  it("logs out when the button is clicked", async () => {
    auth.value.status = "authenticated";
    const user = userEvent.setup();
    render(<AppHeader />);

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(auth.value.logout).toHaveBeenCalledTimes(1);
  });
});
