import { describe, expect, it } from "vitest";

import { MAX_CV_BYTES, MAX_JOB_CHARS, validateApplication } from "@/lib/validation";

function fileOfSize(name: string, size: number): File {
  const file = new File(["x"], name);
  Object.defineProperty(file, "size", { value: size });
  return file;
}

const validFile = fileOfSize("cv.docx", 1000);

describe("validateApplication", () => {
  it("accepts a docx or pdf file with a job offer", () => {
    expect(validateApplication({ cvFile: validFile, jobText: "A job offer" })).toEqual({});
    expect(
      validateApplication({ cvFile: fileOfSize("CV.PDF", 1000), jobText: "A job offer" }),
    ).toEqual({});
  });

  it("requires a file", () => {
    expect(validateApplication({ cvFile: null, jobText: "A job offer" }).cvFile).toBe(
      "Choose your CV file.",
    );
  });

  it("refuses other file types", () => {
    const errors = validateApplication({ cvFile: fileOfSize("cv.exe", 1000), jobText: "x" });

    expect(errors.cvFile).toBe("The CV must be a .docx or .pdf file.");
  });

  it("refuses an empty file", () => {
    const errors = validateApplication({ cvFile: fileOfSize("cv.pdf", 0), jobText: "x" });

    expect(errors.cvFile).toBe("The CV file is empty.");
  });

  it("refuses a file over 5 MB but accepts exactly 5 MB", () => {
    const tooBig = validateApplication({
      cvFile: fileOfSize("cv.pdf", MAX_CV_BYTES + 1),
      jobText: "x",
    });
    const limit = validateApplication({ cvFile: fileOfSize("cv.pdf", MAX_CV_BYTES), jobText: "x" });

    expect(tooBig.cvFile).toBe("The CV file is too large (5 MB maximum).");
    expect(limit.cvFile).toBeUndefined();
  });

  it("requires a job offer that is not only spaces", () => {
    expect(validateApplication({ cvFile: validFile, jobText: "   \n " }).jobText).toBe(
      "Paste the job offer.",
    );
  });

  it("refuses a job offer over the limit", () => {
    const errors = validateApplication({
      cvFile: validFile,
      jobText: "x".repeat(MAX_JOB_CHARS + 1),
    });

    expect(errors.jobText).toContain("too long");
  });

  it("reports both errors at once", () => {
    const errors = validateApplication({ cvFile: null, jobText: "" });

    expect(Object.keys(errors)).toEqual(["cvFile", "jobText"]);
  });
});
