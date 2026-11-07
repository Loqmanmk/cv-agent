import { describe, expect, it } from "vitest";

import { base64ToPdfBlob, fileSlug } from "@/lib/pdf";

describe("base64ToPdfBlob", () => {
  it("creates a PDF blob with the decoded size", () => {
    const blob = base64ToPdfBlob(btoa("%PDF-test"));

    expect(blob.type).toBe("application/pdf");
    expect(blob.size).toBe(9);
  });
});

describe("fileSlug", () => {
  it("makes a safe file name part", () => {
    expect(fileSlug("Coface")).toBe("coface");
    expect(fileSlug("Société Générale & Co.")).toBe("societe-generale-co");
  });

  it("never returns an empty name", () => {
    expect(fileSlug("")).toBe("application");
    expect(fileSlug("???")).toBe("application");
  });
});
