import { describe, expect, it } from "vitest";

import {
  buildEditedCv,
  buildEditedLetter,
  findProblems,
  fromSkillDrafts,
  parseItems,
  setExperienceBullet,
  setHeaderField,
  setLetterParagraph,
  setProfile,
  setProjectBullet,
  toSkillDrafts,
} from "@/lib/cvEdit";

import { makeCv, makeLetter } from "./fixtures";

describe("skills as text", () => {
  it("splits on commas, trims and drops empty items", () => {
    expect(parseItems("Python,  FastAPI ,, Docker, ")).toEqual(["Python", "FastAPI", "Docker"]);
    expect(parseItems("  ")).toEqual([]);
  });

  it("turns skill groups into text and back", () => {
    const drafts = toSkillDrafts(makeCv().skills);

    expect(drafts[0]).toEqual({ category: "Back-end", items: "Python, FastAPI" });
    expect(fromSkillDrafts(drafts)).toEqual(makeCv().skills);
  });

  it("drops groups without items and trims names", () => {
    const groups = fromSkillDrafts([
      { category: " Tools ", items: "Git, " },
      { category: "Empty", items: " " },
    ]);

    expect(groups).toEqual([{ category: "Tools", items: ["Git"] }]);
  });

  it("reports a group that has items but no name", () => {
    expect(findProblems([{ category: " ", items: "Git" }])).toEqual([
      "Every skills group that has items needs a name.",
    ]);
    expect(findProblems([{ category: "", items: "" }])).toEqual([]);
    expect(findProblems([{ category: "Tools", items: "Git" }])).toEqual([]);
  });
});

describe("editing without mutation", () => {
  it("changes the profile", () => {
    const cv = makeCv();

    expect(setProfile(cv, "New").profile).toBe("New");
    expect(cv.profile).toBe("Original profile.");
  });

  it("changes one header field only", () => {
    const next = setHeaderField(makeCv(), "headline", "Data Engineer");

    expect(next.header.headline).toBe("Data Engineer");
    expect(next.header.target_line).toBe("Looking for an internship");
    expect(next.header.email).toBe("jane@example.com");
  });

  it("changes one experience bullet only", () => {
    const cv = makeCv();
    const next = setExperienceBullet(cv, 0, 1, "Changed");

    expect(next.experiences[0]?.bullets).toEqual(["Built an Android app", "Changed"]);
    expect(cv.experiences[0]?.bullets[1]).toBe("Integrated a REST API");
  });

  it("changes one project bullet only", () => {
    const next = setProjectBullet(makeCv(), 0, 0, "Changed");

    expect(next.projects[0]?.bullets).toEqual(["Changed"]);
  });

  it("changes one letter paragraph only", () => {
    const next = setLetterParagraph(makeLetter(), 1, "Changed");

    expect(next.paragraphs).toEqual([
      "Opening paragraph.",
      "Changed",
      "Motivation paragraph.",
      "Fixed closing.",
    ]);
  });
});

describe("building the documents to render", () => {
  it("removes empty bullets and trims the text", () => {
    const cv = setExperienceBullet(makeCv(), 0, 1, "   ");
    const trimmed = setProfile(setHeaderField(cv, "headline", "  Engineer  "), "  Profile  ");

    const edited = buildEditedCv(trimmed, toSkillDrafts(trimmed.skills));

    expect(edited.experiences[0]?.bullets).toEqual(["Built an Android app"]);
    expect(edited.header.headline).toBe("Engineer");
    expect(edited.profile).toBe("Profile");
  });

  it("uses the edited skills", () => {
    const edited = buildEditedCv(makeCv(), [{ category: "Main", items: "Python, Docker" }]);

    expect(edited.skills).toEqual([{ category: "Main", items: ["Python", "Docker"] }]);
  });

  it("never touches the locked facts", () => {
    const cv = makeCv();

    const edited = buildEditedCv(cv, toSkillDrafts(cv.skills));

    expect(edited.header.email).toBe(cv.header.email);
    expect(edited.education).toEqual(cv.education);
    expect(edited.languages).toEqual(cv.languages);
    expect(edited.experiences[0]?.company).toBe("Acme");
  });

  it("drops empty letter paragraphs and keeps the rest in order", () => {
    const letter = setLetterParagraph(makeLetter(), 0, " ");

    expect(buildEditedLetter(letter).paragraphs).toEqual([
      "Experience paragraph.",
      "Motivation paragraph.",
      "Fixed closing.",
    ]);
  });
});
