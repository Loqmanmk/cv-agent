"use client";

import type { RecipientField } from "@/lib/cvEdit";
import type { CoverLetter } from "@/lib/types";

type Props = {
  letter: CoverLetter;
  onSubjectChange: (value: string) => void;
  onRecipientChange: (field: RecipientField, value: string) => void;
};

const FIELD = "mt-1 block w-full rounded border border-gray-300 p-2 text-sm";

const RECIPIENT_FIELDS: { field: RecipientField; label: string }[] = [
  { field: "contact", label: "Recipient contact" },
  { field: "company", label: "Company" },
  { field: "address", label: "Company address" },
];

export function LetterHeaderEditor({ letter, onSubjectChange, onRecipientChange }: Props) {
  return (
    <div className="mt-2 space-y-3">
      <div>
        <label htmlFor="review-subject" className="text-sm font-medium">
          Subject
        </label>
        <input
          id="review-subject"
          type="text"
          value={letter.subject}
          onChange={(event) => onSubjectChange(event.target.value)}
          className={FIELD}
        />
      </div>
      {RECIPIENT_FIELDS.map(({ field, label }) => (
        <div key={field}>
          <label htmlFor={`review-recipient-${field}`} className="text-sm font-medium">
            {label}
          </label>
          <input
            id={`review-recipient-${field}`}
            type="text"
            value={letter.recipient[field]}
            onChange={(event) => onRecipientChange(field, event.target.value)}
            className={FIELD}
          />
        </div>
      ))}
      <p className="text-xs text-gray-500">
        The date line and the greeting are generated from the language of the offer and stay fixed.
      </p>
    </div>
  );
}
