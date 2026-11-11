import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "@/app/page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({
    status: "authenticated",
    email: "jane@example.com",
    startupError: null,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("Home page", () => {
  it("shows the application form to a logged-in user", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "New application" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create my application" })).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });
});
