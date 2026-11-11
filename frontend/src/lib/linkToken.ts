"use client";

import { useCallback, useEffect, useRef } from "react";

const TOKEN_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;

export function tokenFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash).get("token");
  return value !== null && TOKEN_SHAPE.test(value) ? value : null;
}

/** Reads the token of an email link once, then removes it from the address bar. */
export function useLinkToken(): () => string | null {
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    // In development React runs effects twice: keep the token read the first time.
    if (tokenRef.current === null) tokenRef.current = tokenFromHash(window.location.hash);
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }, []);

  return useCallback(() => tokenRef.current, []);
}
