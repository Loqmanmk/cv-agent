import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { tokenFromHash, useLinkToken } from "@/lib/linkToken";

describe("tokenFromHash", () => {
  it.each([
    ["#token=abc_DEF-123", "abc_DEF-123"],
    ["token=abc", "abc"],
    ["#other=1&token=abc", "abc"],
  ])("reads %s", (hash, expected) => {
    expect(tokenFromHash(hash)).toBe(expected);
  });

  it.each([
    "",
    "#",
    "#token=",
    "#token=has%20space",
    "#token=<script>",
    `#token=${"x".repeat(129)}`,
  ])("refuses %s", (hash) => {
    expect(tokenFromHash(hash)).toBeNull();
  });
});

describe("useLinkToken", () => {
  it("keeps the token and removes it from the address bar", () => {
    window.history.replaceState(null, "", "/verify-email?lang=fr#token=abc123");

    const { result } = renderHook(() => useLinkToken());

    expect(result.current()).toBe("abc123");
    expect(window.location.hash).toBe("");
    expect(window.location.pathname + window.location.search).toBe("/verify-email?lang=fr");
  });

  it("gives nothing without a token", () => {
    window.history.replaceState(null, "", "/verify-email");

    const { result } = renderHook(() => useLinkToken());

    expect(result.current()).toBeNull();
  });
});
