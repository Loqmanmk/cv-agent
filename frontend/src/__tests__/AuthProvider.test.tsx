import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { getCsrfToken, setCsrfToken, setUnauthorizedHandler } from "@/lib/session";
import { listApplications } from "@/lib/trackerApi";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const fetchMock = vi.fn();

type Handlers = Record<string, () => Response>;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function route(handlers: Handlers) {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(url).pathname}`;
    const handler = handlers[key];
    return Promise.resolve(handler ? handler() : new Response("missing", { status: 404 }));
  });
}

function callTo(path: string): [string, RequestInit] | undefined {
  return fetchMock.mock.calls.find(([url]) => (url as string).endsWith(path)) as
    [string, RequestInit] | undefined;
}

function Probe() {
  const auth = useAuth();
  const [message, setMessage] = useState("none");
  return (
    <div>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="email">{auth.email ?? "none"}</p>
      <p data-testid="startup">{auth.startupError ?? "none"}</p>
      <p data-testid="message">{message}</p>
      <button
        type="button"
        onClick={() =>
          void auth
            .login("jane@example.com", "pw")
            .catch((error: Error) => setMessage(error.message))
        }
      >
        login
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        logout
      </button>
      <button type="button" onClick={() => void listApplications().catch(() => undefined)}>
        ping
      </button>
    </div>
  );
}

function renderProbe() {
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

async function expectStatus(expected: string) {
  await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent(expected));
}

const SESSION = { email: "jane@example.com", csrf_token: "tok" };

beforeEach(() => {
  fetchMock.mockReset();
  router.replace.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  setCsrfToken(null);
  setUnauthorizedHandler(null);
});

describe("AuthProvider", () => {
  it("restores an existing session when the page loads", async () => {
    route({ "GET /auth/me": () => jsonResponse(SESSION) });

    renderProbe();

    await expectStatus("authenticated");
    expect(screen.getByTestId("email")).toHaveTextContent("jane@example.com");
    expect(getCsrfToken()).toBe("tok");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("is anonymous without a session, and says nothing about it", async () => {
    route({ "GET /auth/me": () => jsonResponse({ detail: "Please log in." }, 401) });

    renderProbe();

    await expectStatus("anonymous");
    expect(screen.getByTestId("startup")).toHaveTextContent("none");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("reports a server that cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    renderProbe();

    await expectStatus("anonymous");
    expect(screen.getByTestId("startup")).toHaveTextContent("Cannot reach the server");
  });

  it("logs in with the email and the password and keeps the CSRF token", async () => {
    route({
      "GET /auth/me": () => jsonResponse({ detail: "Please log in." }, 401),
      "POST /auth/login": () => jsonResponse({ email: "jane@example.com", csrf_token: "tok2" }),
    });
    const user = userEvent.setup();
    renderProbe();
    await expectStatus("anonymous");

    await user.click(screen.getByRole("button", { name: "login" }));

    await expectStatus("authenticated");
    expect(getCsrfToken()).toBe("tok2");
    const call = callTo("/auth/login");
    expect(JSON.parse(call?.[1].body as string)).toEqual({
      email: "jane@example.com",
      password: "pw",
    });
    expect(call?.[1].credentials).toBe("include");
  });

  it("stays anonymous and passes the message on when the login is refused", async () => {
    route({
      "GET /auth/me": () => jsonResponse({ detail: "Please log in." }, 401),
      "POST /auth/login": () => jsonResponse({ detail: "Invalid email or password." }, 401),
    });
    const user = userEvent.setup();
    renderProbe();
    await expectStatus("anonymous");

    await user.click(screen.getByRole("button", { name: "login" }));

    await waitFor(() =>
      expect(screen.getByTestId("message")).toHaveTextContent("Invalid email or password."),
    );
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(getCsrfToken()).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("logs out on the server, forgets the token and goes to the login page", async () => {
    route({
      "GET /auth/me": () => jsonResponse(SESSION),
      "POST /auth/logout": () => new Response(null, { status: 204 }),
    });
    const user = userEvent.setup();
    renderProbe();
    await expectStatus("authenticated");

    await user.click(screen.getByRole("button", { name: "logout" }));

    await expectStatus("anonymous");
    expect(callTo("/auth/logout")?.[1].headers).toEqual({ "X-CSRF-Token": "tok" });
    expect(getCsrfToken()).toBeNull();
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("logs out on this side even when the server cannot be reached", async () => {
    route({ "GET /auth/me": () => jsonResponse(SESSION) });
    const user = userEvent.setup();
    renderProbe();
    await expectStatus("authenticated");
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await user.click(screen.getByRole("button", { name: "logout" }));

    await expectStatus("anonymous");
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("sends the user back to the login page when the session ends", async () => {
    route({
      "GET /auth/me": () => jsonResponse(SESSION),
      "GET /tracker/applications": () => jsonResponse({ detail: "Please log in." }, 401),
    });
    const user = userEvent.setup();
    renderProbe();
    await expectStatus("authenticated");

    await user.click(screen.getByRole("button", { name: "ping" }));

    await expectStatus("anonymous");
    expect(getCsrfToken()).toBeNull();
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("refuses to be used outside the provider", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);

    expect(() => render(<Probe />)).toThrow("useAuth must be used inside an AuthProvider.");

    error.mockRestore();
  });
});
