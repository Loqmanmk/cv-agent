"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";
import {
  STATUSES,
  STATUS_LABELS,
  isStatus,
  type ApplicationStatus,
  type TrackedApplication,
} from "@/lib/tracker";
import {
  applicationFileUrl,
  deleteApplication,
  listApplications,
  updateApplication,
} from "@/lib/trackerApi";

type LoadState = { phase: "loading" } | { phase: "error"; message: string } | { phase: "ready" };

type RowProps = {
  application: TrackedApplication;
  busy: boolean;
  onStatus: (id: number, status: ApplicationStatus) => void;
  onNotes: (id: number, notes: string) => void;
  onDelete: (id: number) => void;
};

const GENERIC_ERROR = "Something went wrong. Please try again.";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : GENERIC_ERROR;
}

function ApplicationRow({ application, busy, onStatus, onNotes, onDelete }: RowProps) {
  const [notes, setNotes] = useState(application.notes);
  const [confirming, setConfirming] = useState(false);
  const title = application.jobTitle;
  const changed = notes.trim() !== application.notes;

  return (
    <li className="rounded border border-gray-200 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">
          {title}
          {application.company ? ` — ${application.company}` : ""}
        </h2>
        <p className="text-xs text-gray-500">
          {application.createdAt.slice(0, 10)} · {application.language.toUpperCase()}
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select
          aria-label={`Status of ${title}`}
          value={application.status}
          disabled={busy}
          onChange={(event) => {
            const value = event.target.value;
            if (isStatus(value)) onStatus(application.id, value);
          }}
          className="rounded border border-gray-300 p-1 text-sm"
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </select>
        <a href={applicationFileUrl(application.id, "cv")} className="text-sm underline">
          CV (PDF)
        </a>
        <a href={applicationFileUrl(application.id, "letter")} className="text-sm underline">
          Letter (PDF)
        </a>
        {application.sourceUrl && (
          <a
            href={application.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline"
          >
            Job offer
          </a>
        )}
      </div>

      <label htmlFor={`notes-${application.id}`} className="mt-3 block text-sm font-medium">
        Notes for {title}
      </label>
      <textarea
        id={`notes-${application.id}`}
        rows={2}
        value={notes}
        disabled={busy}
        onChange={(event) => setNotes(event.target.value)}
        className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy || !changed}
          onClick={() => onNotes(application.id, notes)}
          className="rounded border border-gray-400 px-3 py-1 text-sm disabled:opacity-50"
        >
          Save notes
        </button>
        {confirming ? (
          <>
            <span className="text-sm">Delete this application?</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => onDelete(application.id)}
              className="rounded bg-red-700 px-3 py-1 text-sm text-white disabled:opacity-50"
            >
              Yes, delete
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded border border-gray-400 px-3 py-1 text-sm"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            aria-label={`Delete ${title}`}
            disabled={busy}
            onClick={() => setConfirming(true)}
            className="text-sm text-red-700 underline disabled:opacity-50"
          >
            Delete
          </button>
        )}
      </div>
    </li>
  );
}

export function TrackerList() {
  const [load, setLoad] = useState<LoadState>({ phase: "loading" });
  const [applications, setApplications] = useState<TrackedApplication[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listApplications(controller.signal)
      .then((items) => {
        setApplications(items);
        setLoad({ phase: "ready" });
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setLoad({ phase: "error", message: messageOf(error) });
      });
    return () => controller.abort();
  }, []);

  async function run(id: number, action: () => Promise<void>) {
    setBusyId(id);
    setActionError(null);
    try {
      await action();
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setBusyId(null);
    }
  }

  async function change(id: number, changes: { status?: ApplicationStatus; notes?: string }) {
    await run(id, async () => {
      const updated = await updateApplication(id, changes);
      setApplications((current) => current.map((item) => (item.id === id ? updated : item)));
    });
  }

  async function remove(id: number) {
    await run(id, async () => {
      await deleteApplication(id);
      setApplications((current) => current.filter((item) => item.id !== id));
    });
  }

  if (load.phase === "loading") {
    return (
      <p role="status" className="mt-6 text-sm text-gray-600">
        Loading your applications…
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
    <>
      {actionError && (
        <p role="alert" className="mt-6 rounded bg-red-50 p-3 text-sm text-red-800">
          {actionError}
        </p>
      )}
      {applications.length === 0 ? (
        <p className="mt-6 text-sm text-gray-600">
          No saved applications yet. Create one on the home page, then click &ldquo;Save to my
          applications&rdquo; in the review section.
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {applications.map((application) => (
            <ApplicationRow
              key={application.id}
              application={application}
              busy={busyId === application.id}
              onStatus={(id, status) => void change(id, { status })}
              onNotes={(id, notes) => void change(id, { notes })}
              onDelete={(id) => void remove(id)}
            />
          ))}
        </ul>
      )}
    </>
  );
}
