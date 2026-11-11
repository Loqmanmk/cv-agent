"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ApiError } from "@/lib/api";
import { fetchMe, login as loginRequest, logout as logoutRequest } from "@/lib/authApi";
import { setCsrfToken, setUnauthorizedHandler } from "@/lib/session";

type Status = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: Status;
  email: string | null;
  startupError: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const GENERIC_ERROR = "Something went wrong. Please try again.";
const AuthContext = createContext<AuthContextValue | null>(null);

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("loading");
  const [email, setEmail] = useState<string | null>(null);
  const [startupError, setStartupError] = useState<string | null>(null);
  const statusRef = useRef<Status>("loading");

  const update = useCallback((next: Status, nextEmail: string | null) => {
    statusRef.current = next;
    setStatus(next);
    setEmail(nextEmail);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchMe(controller.signal)
      .then((user) => {
        setCsrfToken(user.csrfToken);
        update("authenticated", user.email);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        if (!(error instanceof ApiError && error.status === 401)) {
          setStartupError(error instanceof ApiError ? error.message : GENERIC_ERROR);
        }
        update("anonymous", null);
      });
    return () => controller.abort();
  }, [update]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (statusRef.current !== "authenticated") return;
      setCsrfToken(null);
      update("anonymous", null);
      router.replace("/login");
    });
    return () => setUnauthorizedHandler(null);
  }, [router, update]);

  const login = useCallback(
    async (emailValue: string, password: string) => {
      const user = await loginRequest(emailValue, password);
      setCsrfToken(user.csrfToken);
      setStartupError(null);
      update("authenticated", user.email);
    },
    [update],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // The session is dropped on this side anyway.
    }
    setCsrfToken(null);
    update("anonymous", null);
    router.replace("/login");
  }, [router, update]);

  const value = useMemo(
    () => ({ status, email, startupError, login, logout }),
    [status, email, startupError, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth must be used inside an AuthProvider.");
  return value;
}
