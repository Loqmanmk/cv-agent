import { describe, expect, it } from "vitest";

import { apiOrigin, buildContentSecurityPolicy, buildSecurityHeaders } from "@/lib/securityHeaders";

const production = { isProduction: true, apiUrl: "http://127.0.0.1:8000/" };
const development = { isProduction: false, apiUrl: "http://127.0.0.1:8000" };

function directive(policy: string, name: string): string[] {
  const found = policy.split("; ").find((item) => item.startsWith(`${name} `));
  return found ? found.split(" ").slice(1) : [];
}

describe("content security policy", () => {
  it("only trusts the site itself by default", () => {
    expect(directive(buildContentSecurityPolicy(production), "default-src")).toEqual(["'self'"]);
  });

  it("refuses to be framed, to embed objects or frames, or to change the base address", () => {
    const policy = buildContentSecurityPolicy(production);

    expect(directive(policy, "frame-ancestors")).toEqual(["'none'"]);
    expect(directive(policy, "object-src")).toEqual(["'none'"]);
    expect(directive(policy, "frame-src")).toEqual(["'none'"]);
    expect(directive(policy, "base-uri")).toEqual(["'self'"]);
    expect(directive(policy, "form-action")).toEqual(["'self'"]);
  });

  it("lets the site talk to its own API and nowhere else", () => {
    expect(directive(buildContentSecurityPolicy(production), "connect-src")).toEqual([
      "'self'",
      "http://127.0.0.1:8000",
    ]);
  });

  it("keeps only the site itself when the API address is not valid", () => {
    const policy = buildContentSecurityPolicy({ isProduction: true, apiUrl: "not a url" });

    expect(directive(policy, "connect-src")).toEqual(["'self'"]);
  });

  it("allows the images the app really uses: its own, inline photos and PDF previews", () => {
    expect(directive(buildContentSecurityPolicy(production), "img-src")).toEqual([
      "'self'",
      "data:",
      "blob:",
    ]);
  });

  it("allows no eval and no websockets in production", () => {
    const policy = buildContentSecurityPolicy(production);

    expect(policy).not.toContain("'unsafe-eval'");
    expect(policy).not.toContain("ws:");
  });

  it("allows what the development server needs, and only in development", () => {
    const policy = buildContentSecurityPolicy(development);

    expect(directive(policy, "script-src")).toContain("'unsafe-eval'");
    expect(directive(policy, "connect-src")).toContain("ws:");
  });

  it("does not force https, so a production build can be tried on localhost", () => {
    expect(buildContentSecurityPolicy(production)).not.toContain("upgrade-insecure-requests");
  });
});

describe("security headers", () => {
  it("sends the full set", () => {
    const headers = Object.fromEntries(
      buildSecurityHeaders(production).map((header) => [header.key, header.value]),
    );

    expect(Object.keys(headers)).toEqual([
      "Content-Security-Policy",
      "X-Content-Type-Options",
      "X-Frame-Options",
      "Referrer-Policy",
      "Permissions-Policy",
      "Cross-Origin-Opener-Policy",
    ]);
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Referrer-Policy"]).toBe("no-referrer");
    expect(headers["Permissions-Policy"]).toContain("camera=()");
  });
});

describe("apiOrigin", () => {
  it("keeps only the scheme, the host and the port", () => {
    expect(apiOrigin("https://api.example.com:8443/v1/path?x=1")).toBe(
      "https://api.example.com:8443",
    );
  });

  it("returns nothing for an invalid address", () => {
    expect(apiOrigin("")).toBe("");
  });
});
