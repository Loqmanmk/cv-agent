"use client";

import { useState, type ReactNode } from "react";

import { LetterHeaderEditor } from "@/components/LetterHeaderEditor";
import { MatchReportPanel } from "@/components/MatchReportPanel";
import type { ApplicationResult } from "@/lib/api";
import {
  addSkill,
  buildEditedCv,
  buildEditedLetter,
  findLetterProblems,
  findProblems,
  hasSkill,
  removeSkill,
  setExperienceBullet,
  setHeaderField,
  setLetterParagraph,
  setLetterSubject,
  setProfile,
  setProjectBullet,
  setRecipientField,
  toSkillDrafts,
  type SkillDraft,
} from "@/lib/cvEdit";
import { imageDataUri } from "@/lib/pdf";
import type { CoverLetter, Cv } from "@/lib/types";

export type EditedDocuments = {
  cv: Cv;
  letter: CoverLetter;
  photoBase64: string | null;
};

type Props = {
  result: ApplicationResult;
  busy: boolean;
  error: string | null;
  onRegenerate: (edited: EditedDocuments) => void;
  onSave?: (edited: EditedDocuments) => void;
  saving?: boolean;
  saveMessage?: string | null;
  saveError?: string | null;
};

const FIELD = "mt-1 block w-full rounded border border-gray-300 p-2 text-sm";

function OriginalText({ text }: { text: string }) {
  return (
    <div className="rounded bg-gray-50 p-3 text-sm text-gray-600">
      <p className="text-xs font-semibold uppercase">Original</p>
      <p className="mt-1 whitespace-pre-line">{text.trim() || "—"}</p>
    </div>
  );
}

function OriginalList({ items }: { items: string[] }) {
  return (
    <div className="rounded bg-gray-50 p-3 text-sm text-gray-600">
      <p className="text-xs font-semibold uppercase">Original</p>
      {items.length === 0 ? (
        <p className="mt-1">—</p>
      ) : (
        <ul className="mt-1 list-disc space-y-1 pl-4">
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({ original, children }: { original: ReactNode; children: ReactNode }) {
  return (
    <div className="mt-2 grid gap-4 md:grid-cols-2">
      {original}
      <div className="space-y-2">{children}</div>
    </div>
  );
}

export function ReviewEditor({
  result,
  busy,
  error,
  onRegenerate,
  onSave,
  saving = false,
  saveMessage = null,
  saveError = null,
}: Props) {
  const [cv, setCv] = useState<Cv>(result.cv);
  const [letter, setLetter] = useState<CoverLetter>(result.letter);
  const [drafts, setDrafts] = useState<SkillDraft[]>(() => toSkillDrafts(result.cv.skills));
  const [includePhoto, setIncludePhoto] = useState(true);
  const problems = [...findProblems(drafts), ...findLetterProblems(letter)];
  const original = result.originalCv;
  const editableParagraphs = letter.paragraphs.slice(0, -1);
  const closing = letter.paragraphs.at(-1);

  function currentEdits(): EditedDocuments {
    return {
      cv: buildEditedCv(cv, drafts),
      letter: buildEditedLetter(letter),
      photoBase64: includePhoto ? result.photoBase64 : null,
    };
  }

  function handleRegenerate() {
    onRegenerate(currentEdits());
  }

  function handleSave() {
    onSave?.(currentEdits());
  }

  return (
    <section aria-label="Review" className="mt-8 border-t pt-6">
      <h2 className="text-xl font-semibold">Review and edit</h2>
      <p className="mt-1 text-sm text-gray-600">
        On the left, your original CV. On the right, the tailored text: edit anything you could not
        defend in an interview. Clear a bullet to remove it.
      </p>

      <MatchReportPanel
        report={result.report}
        isAdded={(skill) => hasSkill(drafts, skill)}
        onToggle={(skill, added) =>
          setDrafts((current) =>
            added
              ? addSkill(current, skill.name, result.language, skill.group)
              : removeSkill(current, skill.name),
          )
        }
      />

      {result.photoBase64 && (
        <div className="mt-4 flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageDataUri(result.photoBase64)}
            alt="Your photo"
            className="h-24 w-20 rounded object-cover"
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includePhoto}
              onChange={(event) => setIncludePhoto(event.target.checked)}
            />
            Keep the photo in the CV
          </label>
        </div>
      )}

      <h3 className="mt-6 font-semibold">Headline and target line</h3>
      <Row
        original={
          <OriginalText text={`${original.header.headline}\n${original.header.target_line}`} />
        }
      >
        <div>
          <label htmlFor="review-headline" className="text-sm font-medium">
            Headline
          </label>
          <input
            id="review-headline"
            type="text"
            value={cv.header.headline}
            onChange={(event) => {
              const value = event.target.value;
              setCv((current) => setHeaderField(current, "headline", value));
            }}
            className={FIELD}
          />
        </div>
        <div>
          <label htmlFor="review-target-line" className="text-sm font-medium">
            Target line
          </label>
          <textarea
            id="review-target-line"
            rows={2}
            value={cv.header.target_line}
            onChange={(event) => {
              const value = event.target.value;
              setCv((current) => setHeaderField(current, "target_line", value));
            }}
            className={FIELD}
          />
        </div>
      </Row>

      <h3 className="mt-6 font-semibold">Profile</h3>
      <Row original={<OriginalText text={original.profile} />}>
        <label htmlFor="review-profile" className="text-sm font-medium">
          Profile
        </label>
        <textarea
          id="review-profile"
          rows={5}
          value={cv.profile}
          onChange={(event) => {
            const value = event.target.value;
            setCv((current) => setProfile(current, value));
          }}
          className={FIELD}
        />
      </Row>

      <h3 className="mt-6 font-semibold">Experience</h3>
      {cv.experiences.map((experience, entry) => (
        <div key={entry} className="mt-3">
          <h4 className="text-sm font-medium">
            {experience.title} — {experience.company}
          </h4>
          <Row original={<OriginalList items={original.experiences[entry]?.bullets ?? []} />}>
            {experience.bullets.map((bullet, index) => (
              <textarea
                key={index}
                aria-label={`${experience.title} bullet ${index + 1}`}
                rows={2}
                value={bullet}
                onChange={(event) => {
                  const value = event.target.value;
                  setCv((current) => setExperienceBullet(current, entry, index, value));
                }}
                className={FIELD}
              />
            ))}
          </Row>
        </div>
      ))}

      <h3 className="mt-6 font-semibold">Projects</h3>
      {cv.projects.map((project, entry) => (
        <div key={entry} className="mt-3">
          <h4 className="text-sm font-medium">{project.title}</h4>
          <Row
            original={
              <OriginalList
                items={
                  original.projects.find((item) => item.title === project.title)?.bullets ?? []
                }
              />
            }
          >
            {project.bullets.map((bullet, index) => (
              <textarea
                key={index}
                aria-label={`${project.title} bullet ${index + 1}`}
                rows={2}
                value={bullet}
                onChange={(event) => {
                  const value = event.target.value;
                  setCv((current) => setProjectBullet(current, entry, index, value));
                }}
                className={FIELD}
              />
            ))}
          </Row>
        </div>
      ))}

      <h3 className="mt-6 font-semibold">Skills</h3>
      <Row
        original={
          <OriginalList
            items={original.skills.map((group) => `${group.category}: ${group.items.join(", ")}`)}
          />
        }
      >
        {drafts.map((draft, index) => (
          <div key={index} className="grid gap-2 md:grid-cols-[1fr_2fr]">
            <input
              type="text"
              aria-label={`Skills group ${index + 1} name`}
              value={draft.category}
              onChange={(event) => {
                const value = event.target.value;
                setDrafts((current) =>
                  current.map((item, position) =>
                    position === index ? { ...item, category: value } : item,
                  ),
                );
              }}
              className={FIELD}
            />
            <input
              type="text"
              aria-label={`Skills group ${index + 1} items`}
              value={draft.items}
              onChange={(event) => {
                const value = event.target.value;
                setDrafts((current) =>
                  current.map((item, position) =>
                    position === index ? { ...item, items: value } : item,
                  ),
                );
              }}
              className={FIELD}
            />
          </div>
        ))}
        <p className="text-xs text-gray-500">
          Separate skills with commas. Clear a group&apos;s skills to remove the group.
        </p>
      </Row>

      <h3 className="mt-6 font-semibold">Cover letter</h3>
      <LetterHeaderEditor
        letter={letter}
        onSubjectChange={(value) => setLetter((current) => setLetterSubject(current, value))}
        onRecipientChange={(field, value) =>
          setLetter((current) => setRecipientField(current, field, value))
        }
      />
      <div className="mt-2 space-y-3">
        {editableParagraphs.map((paragraph, index) => (
          <div key={index}>
            <label htmlFor={`review-paragraph-${index}`} className="text-sm font-medium">
              Letter paragraph {index + 1}
            </label>
            <textarea
              id={`review-paragraph-${index}`}
              rows={5}
              value={paragraph}
              onChange={(event) => {
                const value = event.target.value;
                setLetter((current) => setLetterParagraph(current, index, value));
              }}
              className={FIELD}
            />
          </div>
        ))}
        {closing && (
          <p className="text-sm text-gray-600">
            <span className="font-medium">Closing (fixed):</span> {closing}
          </p>
        )}
      </div>

      {problems.map((problem) => (
        <p key={problem} role="alert" className="mt-4 text-sm text-red-700">
          {problem}
        </p>
      ))}
      {error && (
        <p role="alert" className="mt-4 rounded bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={handleRegenerate}
        disabled={busy || problems.length > 0}
        className="mt-4 rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? "Regenerating…" : "Regenerate PDFs"}
      </button>

      {onSave && (
        <div className="mt-6 border-t pt-4">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || problems.length > 0}
            className="rounded border border-gray-400 px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save to my applications"}
          </button>
          <p className="mt-1 text-xs text-gray-500">
            Saves the text as you see it here, with both PDFs. Each click adds a new entry.
          </p>
          {saveMessage && (
            <p role="status" className="mt-2 text-sm text-green-700">
              {saveMessage}
            </p>
          )}
          {saveError && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {saveError}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
