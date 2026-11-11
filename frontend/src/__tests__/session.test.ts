import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getCsrfToken,
  notifyUnauthorized,
  setCsrfToken,
  setUnauthorizedHandler,
} from "@/lib/session";

afterEach(() => {
  setCsrfToken(null);
  setUnauthorizedHandler(null);
});

describe("session", () => {
  it("keeps the CSRF token in memory only", () => {
    expect(getCsrfToken()).toBeNull();

    setCsrfToken("abc");

    expect(getCsrfToken()).toBe("abc");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("can forget the token", () => {
    setCsrfToken("abc");
    setCsrfToken(null);

    expect(getCsrfToken()).toBeNull();
  });

  it("tells the registered handler about an unauthorized answer", () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);

    notifyUnauthorized();

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does nothing without a handler, or after it was removed", () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    setUnauthorizedHandler(null);

    expect(() => notifyUnauthorized()).not.toThrow();
    expect(handler).not.toHaveBeenCalled();
  });
});
