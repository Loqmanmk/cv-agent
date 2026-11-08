import { describe, expect, it } from "vitest";

import {
  buildEditedLetter,
  findLetterProblems,
  setLetterSubject,
  setRecipientField,
} from "@/lib/cvEdit";

import { makeLetter } from "./fixtures";

describe("letter header editing", () => {
  it("changes the subject without touching the original", () => {
    const letter = makeLetter();

    expect(setLetterSubject(letter, "New subject").subject).toBe("New subject");
    expect(letter.subject).toBe("Objet : Candidature pour le poste de Stagiaire");
  });

  it("changes one recipient field only", () => {
    const next = setRecipientField(makeLetter(), "company", "Coface");

    expect(next.recipient).toEqual({ contact: "", company: "Coface", address: "" });
  });

  it("requires a subject", () => {
    expect(findLetterProblems(setLetterSubject(makeLetter(), "   "))).toEqual([
      "The letter needs a subject line.",
    ]);
    expect(findLetterProblems(makeLetter())).toEqual([]);
  });

  it("trims the subject and the recipient when building the letter", () => {
    const edited = buildEditedLetter(
      setRecipientField(setLetterSubject(makeLetter(), "  Subject  "), "company", "  Coface  "),
    );

    expect(edited.subject).toBe("Subject");
    expect(edited.recipient.company).toBe("Coface");
  });

  it("never touches the sender, the date or the greeting", () => {
    const letter = makeLetter();

    const edited = buildEditedLetter(setLetterSubject(letter, "Another subject"));

    expect(edited.sender).toEqual(letter.sender);
    expect(edited.place_date).toBe(letter.place_date);
    expect(edited.greeting).toBe(letter.greeting);
  });
});
