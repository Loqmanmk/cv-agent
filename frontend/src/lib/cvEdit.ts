import type { CoverLetter, Cv, SkillGroup } from "@/lib/types";

export type SkillDraft = { category: string; items: string };

export function parseItems(text: string): string[] {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function toSkillDrafts(groups: SkillGroup[]): SkillDraft[] {
  return groups.map((group) => ({ category: group.category, items: group.items.join(", ") }));
}

export function fromSkillDrafts(drafts: SkillDraft[]): SkillGroup[] {
  return drafts
    .map((draft) => ({ category: draft.category.trim(), items: parseItems(draft.items) }))
    .filter((group) => group.items.length > 0);
}

// The group that receives the skills the user adds from the offer, in the language of the CV.
const ADDED_SKILLS_GROUP: Record<string, string> = {
  fr: "Autres compétences",
  en: "Other skills",
  de: "Weitere Kenntnisse",
  ar: "مهارات أخرى",
};

export function addedSkillsGroup(language: string): string {
  return ADDED_SKILLS_GROUP[language] ?? ADDED_SKILLS_GROUP.en;
}

function sameSkill(a: string, b: string): boolean {
  return a.trim().toLocaleLowerCase() === b.trim().toLocaleLowerCase();
}

export function hasSkill(drafts: SkillDraft[], name: string): boolean {
  return drafts.some((draft) => parseItems(draft.items).some((item) => sameSkill(item, name)));
}

/**
 * Adds a skill to its group (React with the front-end skills). A group that is not in the CV
 * yet is created with its own name ("Business & Strategy"). Only a skill without any group
 * goes to the group of added skills.
 */
export function addSkill(
  drafts: SkillDraft[],
  name: string,
  language: string,
  group: string | null = null,
): SkillDraft[] {
  if (hasSkill(drafts, name)) return drafts;
  const wanted = group?.trim() || addedSkillsGroup(language);
  const index = drafts.findIndex((draft) => sameSkill(draft.category, wanted));
  if (index === -1) return [...drafts, { category: wanted, items: name }];
  return drafts.map((draft, position) =>
    position === index ? { ...draft, items: [...parseItems(draft.items), name].join(", ") } : draft,
  );
}

/** Removes a skill from every group. A group left empty disappears from the CV. */
export function removeSkill(drafts: SkillDraft[], name: string): SkillDraft[] {
  return drafts.map((draft) => ({
    ...draft,
    items: parseItems(draft.items)
      .filter((item) => !sameSkill(item, name))
      .join(", "),
  }));
}

export function findProblems(drafts: SkillDraft[]): string[] {
  const unnamed = drafts.some(
    (draft) => draft.category.trim() === "" && parseItems(draft.items).length > 0,
  );
  return unnamed ? ["Every skills group that has items needs a name."] : [];
}

function replaceAt<T>(items: T[], index: number, value: T): T[] {
  return items.map((item, position) => (position === index ? value : item));
}

export function setHeaderField(cv: Cv, field: "headline" | "target_line", value: string): Cv {
  return { ...cv, header: { ...cv.header, [field]: value } };
}

export function setProfile(cv: Cv, value: string): Cv {
  return { ...cv, profile: value };
}

export function setExperienceBullet(cv: Cv, entry: number, index: number, value: string): Cv {
  return {
    ...cv,
    experiences: cv.experiences.map((experience, position) =>
      position === entry
        ? { ...experience, bullets: replaceAt(experience.bullets, index, value) }
        : experience,
    ),
  };
}

export function setProjectBullet(cv: Cv, entry: number, index: number, value: string): Cv {
  return {
    ...cv,
    projects: cv.projects.map((project, position) =>
      position === entry
        ? { ...project, bullets: replaceAt(project.bullets, index, value) }
        : project,
    ),
  };
}

export function setLetterParagraph(letter: CoverLetter, index: number, value: string): CoverLetter {
  return { ...letter, paragraphs: replaceAt(letter.paragraphs, index, value) };
}

function withoutEmpty(lines: string[]): string[] {
  return lines.map((line) => line.trim()).filter((line) => line.length > 0);
}

export function buildEditedCv(cv: Cv, drafts: SkillDraft[]): Cv {
  return {
    ...cv,
    header: {
      ...cv.header,
      headline: cv.header.headline.trim(),
      target_line: cv.header.target_line.trim(),
    },
    profile: cv.profile.trim(),
    experiences: cv.experiences.map((experience) => ({
      ...experience,
      bullets: withoutEmpty(experience.bullets),
    })),
    projects: cv.projects.map((project) => ({
      ...project,
      bullets: withoutEmpty(project.bullets),
    })),
    skills: fromSkillDrafts(drafts),
  };
}

export function buildEditedLetter(letter: CoverLetter): CoverLetter {
  return {
    ...letter,
    subject: letter.subject.trim(),
    recipient: {
      contact: letter.recipient.contact.trim(),
      company: letter.recipient.company.trim(),
      address: letter.recipient.address.trim(),
    },
    paragraphs: withoutEmpty(letter.paragraphs),
  };
}

export type RecipientField = "contact" | "company" | "address";

export function setLetterSubject(letter: CoverLetter, value: string): CoverLetter {
  return { ...letter, subject: value };
}

export function setRecipientField(
  letter: CoverLetter,
  field: RecipientField,
  value: string,
): CoverLetter {
  return { ...letter, recipient: { ...letter.recipient, [field]: value } };
}

export function findLetterProblems(letter: CoverLetter): string[] {
  return letter.subject.trim() === "" ? ["The letter needs a subject line."] : [];
}
