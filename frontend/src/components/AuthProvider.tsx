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
import {
  fetchMe,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
} from "@/lib/authApi";
import { setCsrfToken, setUnauthorizedHandler } from "@/lib/session";

type Status = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: Status;
  email: string | null;
  emailVerified: boolean | null;
  startupError: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
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
  const [emailVerified, setEmailVerified] = useState<boolean | null>(null);
  const [startupError, setStartupError] = useState<string | null>(null);
  const statusRef = useRef<Status>("loading");

  const signIn = useCallback((user: AuthUser) => {
    setCsrfToken(user.csrfToken);
    statusRef.current = "authenticated";
    setStatus("authenticated");
    setEmail(user.email);
    setEmailVerified(user.emailVerified);
  }, []);

  const signOut = useCallback(() => {
    setCsrfToken(null);
    statusRef.current = "anonymous";
    setStatus("anonymous");
    setEmail(null);
    setEmailVerified(null);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchMe(controller.signal)
      .then(signIn)
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        if (!(error instanceof ApiError && error.status === 401)) {
          setStartupError(error instanceof ApiError ? error.message : GENERIC_ERROR);
        }
        signOut();
      });
    return () => controller.abort();
  }, [signIn, signOut]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (statusRef.current !== "authenticated") return;
      signOut();
      router.replace("/login");
    });
    return () => setUnauthorizedHandler(null);
  }, [router, signOut]);

  const login = useCallback(
    async (emailValue: string, password: string) => {
      const user = await loginRequest(emailValue, password);
      setStartupError(null);
      signIn(user);
    },
    [signIn],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // The session is dropped on this side anyway.
    }
    signOut();
    router.replace("/login");
  }, [router, signOut]);

  const refresh = useCallback(async () => {
    try {
      signIn(await fetchMe());
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) signOut();
    }
  }, [signIn, signOut]);

  const value = useMemo(
    () => ({ status, email, emailVerified, startupError, login, logout, refresh }),
    [status, email, emailVerified, startupError, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth must be used inside an AuthProvider.");
  return value;
}
