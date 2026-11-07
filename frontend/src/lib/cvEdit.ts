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
  return { ...letter, paragraphs: withoutEmpty(letter.paragraphs) };
}
