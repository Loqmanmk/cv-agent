"use client";

import { useEffect, useState, type FormEvent } from "react";

import {
  CV_LANGUAGES,
  CV_LANGUAGE_LABELS,
  fetchProfile,
  isCvLanguage,
  isGender,
  saveProfile,
  type CvLanguage,
  type Gender,
} from "@/lib/accountApi";
import { ApiError } from "@/lib/api";

type Load = { phase: "loading" } | { phase: "error"; message: string } | { phase: "ready" };

const GENERIC_ERROR = "Something went wrong. Please try again.";
const FIELD = "mt-1 block w-full rounded border border-gray-300 p-2 text-sm";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : GENERIC_ERROR;
}

export function ProfileForm() {
  const [load, setLoad] = useState<Load>({ phase: "loading" });
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [gender, setGender] = useState<Gender>("m");
  const [cvLanguage, setCvLanguage] = useState<CvLanguage>("fr");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchProfile(controller.signal)
      .then((profile) => {
        setAddress(profile.address);
        setCity(profile.city);
        setGender(profile.gender);
        setCvLanguage(profile.cvLanguage);
        setLoad({ phase: "ready" });
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught)) return;
        setLoad({ phase: "error", message: messageOf(caught) });
      });
    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    if (!city.trim()) {
      setError("Enter your city: your cover letters need it.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const profile = await saveProfile({ address, city, gender, cvLanguage });
      setAddress(profile.address);
      setCity(profile.city);
      setSaved(true);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setSaving(false);
    }
  }

  if (load.phase === "loading") {
    return (
      <p role="status" className="mt-6 text-sm text-gray-600">
        Loading your profile…
      </p>
    );
  }
  if (load.phase === "error") {
    return (
      <p role="alert" className="mt-6 rounded bg-red-50 p-3 text-sm text-red-800">
        {load.message}
      </p>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} noValidate className="mt-6 space-y-5">
      <div>
        <label htmlFor="profile-address" className="block text-sm font-medium">
          Address
        </label>
        <input
          id="profile-address"
          type="text"
          autoComplete="street-address"
          maxLength={300}
          value={address}
          disabled={saving}
          onChange={(event) => setAddress(event.target.value)}
          className={FIELD}
        />
      </div>

      <div>
        <label htmlFor="profile-city" className="block text-sm font-medium">
          City
        </label>
        <input
          id="profile-city"
          type="text"
          autoComplete="address-level2"
          maxLength={100}
          aria-required="true"
          value={city}
          disabled={saving}
          onChange={(event) => setCity(event.target.value)}
          className={FIELD}
        />
      </div>

      <div>
        <label htmlFor="profile-gender" className="block text-sm font-medium">
          Grammatical gender in letters
        </label>
        <select
          id="profile-gender"
          value={gender}
          disabled={saving}
          aria-describedby="profile-gender-help"
          onChange={(event) => {
            const value = event.target.value;
            if (isGender(value)) setGender(value);
          }}
          className={FIELD}
        >
          <option value="m">Masculine (heureux, motivé)</option>
          <option value="f">Feminine (heureuse, motivée)</option>
        </select>
        <p id="profile-gender-help" className="mt-1 text-xs text-gray-500">
          Used for grammatical agreement in French and Arabic letters.
        </p>
      </div>

      <div>
        <label htmlFor="profile-cv-language" className="block text-sm font-medium">
          Language of the CV you upload
        </label>
        <select
          id="profile-cv-language"
          value={cvLanguage}
          disabled={saving}
          aria-describedby="profile-cv-language-help"
          onChange={(event) => {
            const value = event.target.value;
            if (isCvLanguage(value)) setCvLanguage(value);
          }}
          className={FIELD}
        >
          {CV_LANGUAGES.map((language) => (
            <option key={language} value={language}>
              {CV_LANGUAGE_LABELS[language]}
            </option>
          ))}
        </select>
        <p id="profile-cv-language-help" className="mt-1 text-xs text-gray-500">
          When an offer is in another language, your CV is translated.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-green-700">
          Profile saved.
        </p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save my profile"}
      </button>
    </form>
  );
}
