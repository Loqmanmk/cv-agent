import { describe, expect, it } from "vitest";

import { addedSkillsGroup, addSkill, hasSkill, removeSkill, type SkillDraft } from "@/lib/cvEdit";

const drafts: SkillDraft[] = [
  { category: "Back-end", items: "Python, FastAPI" },
  { category: "Front-end", items: "React" },
];

describe("adding the skills of the offer", () => {
  it("finds a skill in any group, ignoring the case", () => {
    expect(hasSkill(drafts, "python")).toBe(true);
    expect(hasSkill(drafts, "Kubernetes")).toBe(false);
  });

  it("creates the group of added skills in the language of the CV", () => {
    expect(addSkill(drafts, "Kubernetes", "fr").at(-1)).toEqual({
      category: "Autres compétences",
      items: "Kubernetes",
    });
    expect(addSkill(drafts, "Kubernetes", "de").at(-1)?.category).toBe("Weitere Kenntnisse");
  });

  it("adds the next skills to the same group", () => {
    const once = addSkill(drafts, "Kubernetes", "en");

    const twice = addSkill(once, "Terraform", "en");

    expect(twice).toHaveLength(3);
    expect(twice[2]).toEqual({ category: "Other skills", items: "Kubernetes, Terraform" });
  });

  it("puts a skill in the group of related skills", () => {
    const added = addSkill(drafts, "Django", "fr", "Back-end");

    expect(added).toHaveLength(2);
    expect(added[0]).toEqual({ category: "Back-end", items: "Python, FastAPI, Django" });
  });

  it("uses the group of added skills when the related group was removed", () => {
    expect(addSkill(drafts, "Kubernetes", "en", "DevOps").at(-1)).toEqual({
      category: "Other skills",
      items: "Kubernetes",
    });
  });

  it("never adds a skill twice", () => {
    expect(addSkill(drafts, "PYTHON", "en")).toBe(drafts);
  });

  it("removes a skill from every group", () => {
    const added = addSkill(drafts, "Kubernetes", "en");

    const removed = removeSkill(added, "kubernetes");

    expect(hasSkill(removed, "Kubernetes")).toBe(false);
    expect(removed[0]).toEqual(drafts[0]);
  });

  it("uses English for a language without its own name", () => {
    expect(addedSkillsGroup("other")).toBe("Other skills");
  });
});
