import { describe, expect, it } from "vitest";

import { base64ToPdfBlob, documentFileName, namePart } from "@/lib/pdf";

describe("base64ToPdfBlob", () => {
  it("creates a PDF blob with the decoded size", () => {
    const blob = base64ToPdfBlob(btoa("%PDF-test"));

    expect(blob.type).toBe("application/pdf");
    expect(blob.size).toBe(9);
  });
});

describe("namePart", () => {
  it.each([
    ["Loqman MAKOURI", "Loqman_Makouri"],
    ["  jean-pierre   dupont ", "Jean_Pierre_Dupont"],
    ["Hélène Müller", "Helene_Muller"],
    ["Ronald McDonald", "Ronald_McDonald"],
    ['Evil"; filename="x', "Evil_Filename_X"],
    ["لقمان", ""],
  ])("turns %j into %j", (name, expected) => {
    expect(namePart(name)).toBe(expected);
  });
});

describe("documentFileName", () => {
  it.each([
    ["cv", "fr", "CV_Loqman_Makouri.pdf"],
    ["letter", "fr", "Lettre_de_motivation_Loqman_Makouri.pdf"],
    ["letter", "de", "Anschreiben_Loqman_Makouri.pdf"],
    ["letter", "en", "Cover_Letter_Loqman_Makouri.pdf"],
    ["letter", "ar", "Cover_Letter_Loqman_Makouri.pdf"],
  ] as const)("names a %s in %s as %s", (kind, language, expected) => {
    expect(documentFileName(kind, "Loqman MAKOURI", language)).toBe(expected);
  });

  it("keeps a clean name when the name has no Latin letters", () => {
    expect(documentFileName("cv", "لقمان", "ar")).toBe("CV.pdf");
  });
});
