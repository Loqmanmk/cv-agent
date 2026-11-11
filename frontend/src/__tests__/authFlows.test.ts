import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import {
  forgotPassword,
  register,
  resendVerification,
  resetPassword,
  verifyEmail,
} from "@/lib/authApi";
import { newPasswordProblems } from "@/lib/passwordRules";

import { jsonResponse, sentBody } from "./helpers/http";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("account requests", () => {
  it.each([
    [
      "/auth/register",
      () => register("jane@example.com", "pw"),
      { email: "jane@example.com", password: "pw" },
    ],
    [
      "/auth/resend-verification",
      () => resendVerification("jane@example.com"),
      { email: "jane@example.com" },
    ],
    ["/auth/verify-email", () => verifyEmail("tok"), { token: "tok" }],
    [
      "/auth/forgot-password",
      () => forgotPassword("jane@example.com"),
      { email: "jane@example.com" },
    ],
    ["/auth/reset-password", () => resetPassword("tok", "pw"), { token: "tok", password: "pw" }],
  ])("%s posts its JSON body and returns the message", async (path, call, body) => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Done." }, 202));

    expect(await call()).toBe("Done.");
    expect(sentBody(fetchMock, path)).toEqual(body);
  });

  it("lists the problems of a refused password", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { detail: "Choose a stronger password.", problems: ["This password is too common."] },
        422,
      ),
    );

    const failure = await register("jane@example.com", "pw").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).message).toBe("Choose a stronger password.");
    expect((failure as ApiError).violations).toEqual(["This password is too common."]);
  });

  it("shows the message of an expired link", async () => {
    const detail = "This link is invalid or has expired. Ask for a new one.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 400));

    await expect(verifyEmail("tok")).rejects.toMatchObject({ message: detail, status: 400 });
  });

  it("refuses an answer without a message", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, 202));

    await expect(forgotPassword("jane@example.com")).rejects.toMatchObject({
      message: "The server sent an unexpected answer.",
    });
  });
});

describe("newPasswordProblems", () => {
  it("accepts a long password typed twice", () => {
    expect(newPasswordProblems("correct horse battery", "correct horse battery")).toEqual([]);
  });

  it("reports a short password and a different repetition together", () => {
    expect(newPasswordProblems("short", "other")).toEqual([
      "Use at least 12 characters.",
      "The two passwords differ.",
    ]);
  });

  it("reports a password that is too long", () => {
    const long = "x".repeat(129);

    expect(newPasswordProblems(long, long)).toEqual(["Use at most 128 characters."]);
  });
});
