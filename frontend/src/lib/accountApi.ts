import { ApiError, post } from "@/lib/api";

export const GENDERS = ["m", "f"] as const;
export const CV_LANGUAGES = ["fr", "en", "de", "ar"] as const;
export const PLANS = ["free", "plus", "pro", "premium"] as const;

export type Gender = (typeof GENDERS)[number];
export type CvLanguage = (typeof CV_LANGUAGES)[number];
export type Plan = (typeof PLANS)[number];

export const PLAN_LABELS: Record<Plan, string> = {
  free: "Free",
  plus: "Plus",
  pro: "Pro",
  premium: "Premium",
};

export const CV_LANGUAGE_LABELS: Record<CvLanguage, string> = {
  fr: "Français",
  en: "English",
  de: "Deutsch",
  ar: "العربية",
};

export type ProfileInput = {
  address: string;
  city: string;
  gender: Gender;
  cvLanguage: CvLanguage;
};

export type Profile = ProfileInput & { isComplete: boolean };

export type Usage = { plan: Plan; used: number; limit: number; resetsAt: string };

type ProfileBody = {
  address: string;
  city: string;
  gender: Gender;
  cv_language: CvLanguage;
  is_complete: boolean;
};

type UsageBody = { plan: Plan; used: number; limit: number; resets_at: string };

const JSON_HEADERS = { "Content-Type": "application/json" };

export function isGender(value: string): value is Gender {
  return (GENDERS as readonly string[]).includes(value);
}

export function isCvLanguage(value: string): value is CvLanguage {
  return (CV_LANGUAGES as readonly string[]).includes(value);
}

function isPlan(value: string): value is Plan {
  return (PLANS as readonly string[]).includes(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isProfileBody(value: unknown): value is ProfileBody {
  return (
    isObject(value) &&
    typeof value.address === "string" &&
    typeof value.city === "string" &&
    typeof value.gender === "string" &&
    isGender(value.gender) &&
    typeof value.cv_language === "string" &&
    isCvLanguage(value.cv_language) &&
    typeof value.is_complete === "boolean"
  );
}

function isUsageBody(value: unknown): value is UsageBody {
  return (
    isObject(value) &&
    typeof value.plan === "string" &&
    isPlan(value.plan) &&
    Number.isInteger(value.used) &&
    Number.isInteger(value.limit) &&
    typeof value.resets_at === "string"
  );
}

function unexpected(): ApiError {
  return new ApiError("The server sent an unexpected answer.", 200);
}

function toProfile(body: ProfileBody): Profile {
  return {
    address: body.address,
    city: body.city,
    gender: body.gender,
    cvLanguage: body.cv_language,
    isComplete: body.is_complete,
  };
}

export async function fetchProfile(signal?: AbortSignal): Promise<Profile> {
  const data = await post("/me/profile", { method: "GET" }, signal);
  if (!isProfileBody(data)) throw unexpected();
  return toProfile(data);
}

export async function saveProfile(input: ProfileInput, signal?: AbortSignal): Promise<Profile> {
  const data = await post(
    "/me/profile",
    {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        address: input.address,
        city: input.city,
        gender: input.gender,
        cv_language: input.cvLanguage,
      }),
    },
    signal,
  );
  if (!isProfileBody(data)) throw unexpected();
  return toProfile(data);
}

export async function fetchUsage(signal?: AbortSignal): Promise<Usage> {
  const data = await post("/me/usage", { method: "GET" }, signal);
  if (!isUsageBody(data)) throw unexpected();
  return { plan: data.plan, used: data.used, limit: data.limit, resetsAt: data.resets_at };
}
